<template>
  <div :class="['neighborhood',{compact,'map-only':mapOnly}]">
    <div v-if="trafficReady && !mapOnly" class="impression-banner"><div><small>模拟曝光机会</small><strong data-testid="total-impressions" :style="campaign?{color:attitudeColor(totalAttitude)}:{}">{{ number(totalImpressions) }}</strong></div><p>人群经过 + 车内人数的曝光机会<br>不是实测观看或去重人数</p><span>此刻 {{ visibleVehicles.length }} 辆车 · {{ visible.length }} 个行人样本</span></div>
    <div v-if="campaign && !mapOnly" class="map-attitude" :style="{color:attitudeColor(totalAttitude)}"><b>{{ attitudeMetric==='interest'?'兴趣程度':'好感度' }} {{ totalAttitude==null?'未知':totalAttitude.toFixed(1)+'/100' }}</b><span v-if="!compact">有评分的曝光权重 {{ number(ratedWeight) }} / {{ number(totalImpressions) }} · 非实测</span><span v-else>模型估计</span></div>
    <div class="walk-stats"><span>此刻 {{ visible.length }} 个{{ trafficReady?'步行样本':'代表' }}在场</span><span>本小时 {{ trips.length }} 次{{ trafficReady?"步行样本":"代表" }}出行</span><span>步行离开 {{ departures }} 次 · 交通接续 {{ trips.length-departures }} 次</span></div>
    <svg :viewBox="mapViewBox" class="world-map" role="img" aria-label="周边街区步行仿真：住宅、商店、公园、场所与步行出口">
      <defs><pattern :id="patternId" width="25" height="25" patternUnits="userSpaceOnUse"><path d="M25 0H0V25" fill="none" stroke="#dce3e5" stroke-width=".5"/></pattern><linearGradient v-for="(s,i) in screens" :key="s.id" :id="`${patternId}-attitude-${i}`"><stop offset="0%" :stop-color="attitudeColor(screenScore(s.id)==null?null:screenScore(s.id)-10)"/><stop offset="100%" :stop-color="attitudeColor(screenScore(s.id)==null?null:screenScore(s.id)+10)"/></linearGradient></defs>
      <rect width="1000" height="590" fill="#f7f9f9"/><rect width="1000" height="590" :fill="`url(#${patternId})`"/>
      <g v-if="!network.geographic"><path d="M0 360H1000" stroke="#dce3e5" stroke-width="60"/><path d="M0 360H1000" stroke="#fff" stroke-width="1" stroke-dasharray="14 15"/>
      <g class="blocks"><rect x="65" y="65" width="210" height="80" rx="8"/><text x="170" y="105">住宅与社区生活</text><rect x="410" y="65" width="210" height="80" rx="8"/><text x="515" y="105">办公与公共服务</text><rect class="park" x="765" y="65" width="170" height="80" rx="18"/><text x="850" y="105">公园 · 散步 · 休息</text>
        <rect x="55" y="205" width="105" height="65" rx="6"/><text x="107" y="240">社区小店</text><rect x="215" y="205" width="125" height="65" rx="6"/><text x="277" y="240">生活服务</text><rect x="395" y="205" width="125" height="65" rx="6"/><text x="457" y="240">沿街店铺</text><rect x="755" y="205" width="115" height="65" rx="6"/><text x="812" y="240">商业街</text>
        <rect x="55" y="450" width="105" height="65" rx="6"/><text x="108" y="485">目标场所</text><rect x="215" y="450" width="125" height="65" rx="6"/><text x="277" y="485">社区设施</text><rect x="395" y="450" width="125" height="65" rx="6"/><text x="457" y="485">交通接续</text><rect x="755" y="450" width="115" height="65" rx="6"/><text x="812" y="485">餐饮 · 咖啡</text></g>
      </g>
      <g v-if="network.geographic" class="geographic-map" v-memo="[network]"><path v-for="feature in network.features" :key="feature.id" :d="geometryPath(feature.points)" :fill="feature.tags.building?'#dce4e5':feature.tags.leisure==='park'?'#dcebdc':'none'" :stroke="feature.tags.highway?'#b2c1c6':'#b9c9cc'" :stroke-width="feature.tags.highway?5:1"/><text v-for="feature in namedFeatures" :key="'label'+feature.id" :x="feature.points[0].x" :y="feature.points[0].y-5" fill="#4a565c" font-size="9">{{ feature.tags.name }}</text></g>
      <g class="walkways" v-memo="[network]"><path v-for="(e,i) in network.edges" :key="i" :d="edgePath(e)" :class="e.kind" fill="none" :stroke-width="e.kind==='crossing'?12:9"/><path v-for="(e,i) in network.edges.filter(e=>e.kind==='crossing')" :key="'cross'+i" class="cross-stripes" :d="edgePath(e)" stroke="#a5b5bc" stroke-width="10" stroke-dasharray="3 6" opacity=".5"/></g>
      <g v-for="place in network.places.filter(p=>!network.geographic||p.kind!=='assumption')" :key="place.id" class="place"><circle :cx="node(place.node).x" :cy="node(place.node).y" :r="place.kind==='boundary'?8:4" :class="place.kind"/><text v-if="!network.geographic || place.kind==='boundary' || place.id==='venue'" :x="node(place.node).x" :y="node(place.node).y+(place.kind==='boundary'?27:-16)" :text-anchor="node(place.node).x<50?'start':node(place.node).x>950?'end':'middle'">{{ place.kind==='boundary'?'↗ ':'' }}{{ place.label }}</text></g>
      <g class="trails" v-if="showTrails || selectedAgent!=null"><path v-for="a in routeAgents" :key="a.id" :d="routePath(a.journey)" fill="none" :stroke="a.color" :stroke-width="isSelected(a)?3:1.4" :opacity="isSelected(a) ? .8 : .2" stroke-dasharray="4 5"/></g>
      <g v-for="car in visibleVehicles" :key="car.id" class="vehicle-node" :data-vehicle="car.id" :data-kind="car.kind" :transform="`translate(${car.position.x},${car.position.y}) rotate(${car.position.angle})`">
        <title>{{ car.label }} · 假设 {{ car.occupants }} 人 · {{ car.speed_kmh }} km/h</title><rect :x="-car.length/2" y="-7" :width="car.length" height="14" rx="4" :fill="car.color" stroke="#e8f0f4" stroke-width=".7"/><rect :x="car.length/2-9" y="-5" width="5" height="10" rx="1" fill="#274557"/><path v-if="car.kind==='bus'" :d="`M${-car.length/2+5} -4h18m-18 8h18`" stroke="#335c68" stroke-width="2"/><rect v-if="car.kind==='taxi'" x="-3" y="-3" width="6" height="6" rx="1" fill="#fff0a8"/><path :d="`M${-car.length/2+4} -8h5m-5 16h5m${car.length-18} -16h5m-5 16h5`" stroke="#080f18" stroke-width="2"/>
      </g>
      <g v-for="a in visible" :key="a.id" class="agent-node" :data-agent="a.id" :data-stage="a.position.stage" :transform="`translate(${a.position.x},${a.position.y})`" tabindex="0" role="button" :aria-label="`${a.name} ${a.position.activity}`" @click="selectActor(a)" @keydown.enter="selectActor(a)">
        <title>{{ a.name }} · {{ a.position.activity }} · {{ a.journey.mode_label }}</title>
        <circle v-if="isSelected(a)" r="15" fill="none" stroke="#202b27"/>
        <circle v-if="watching(a)" r="18" :stroke="a.color" fill="none" opacity=".6"/>
        <circle r="9" :fill="a.color" opacity=".12"/><circle cy="-4" r="3" :fill="a.color" stroke="#ecfff8" stroke-width=".7"/>
        <path d="M0 0v6M-4 3L0 0l4 3M-3 11l3-5 3 5" :stroke="a.color" stroke-width="1.7" fill="none" stroke-linecap="round"/>
        <path v-if="a.appearance==='backpack'" d="M-4 0v6h-3V1Z" fill="#d3ba84"/><rect v-if="a.appearance==='shopping'" x="4" y="4" width="4" height="5" rx="1" fill="#d9b9a3"/><rect v-if="a.appearance==='briefcase'" x="4" y="3" width="5" height="4" rx="1" fill="#9fadc9"/><path v-if="a.appearance==='phone'" d="M3 0l3-3" stroke="#d2efff" stroke-width="2"/>
        <path v-if="!a.position.stationary" d="M13 -2l4 2-4 2" :transform="`rotate(${a.position.angle})`" :stroke="a.color" fill="none" opacity=".8"/>
        <text v-if="isSelected(a)" y="-24" text-anchor="middle" fill="#171b1f" font-size="11">{{ a.position.activity }}</text>
      </g>
      <g v-for="(s,i) in screens" :key="s.id" class="screen-node" :class="{counting:impressions[s.id]?.recent}" :data-screen="s.id" tabindex="0" role="button" :aria-label="campaign?`${s.name} · ${campaign.title} · ${attitudeMetric==='interest'?'兴趣':'好感'} ${screenScore(s.id)==null?'未知':screenScore(s.id).toFixed(1)}`:s.name" @click="$emit('screen',s.id)" @keydown.enter="$emit('screen',s.id)">
        <title>{{ campaign?campaign.message+' · '+(attitudeMetric==='interest'?'兴趣':'好感')+'：'+(screenScore(s.id)==null?'未知':screenScore(s.id).toFixed(1))+' / 100 · 点击查看依据':s.name }}</title><circle :cx="s.x" :cy="s.y" :r="s.view_radius||network.view_radius" fill="#69ddb3" opacity=".035" stroke="#69ddb3" stroke-dasharray="4 7"/>
        <path :d="`M${s.x} ${s.y}V${boardY(s)+20}`" stroke="#8bb7ac" stroke-width="3"/>
        <rect :x="s.x-36" :y="boardY(s)" width="72" height="36" rx="4" :fill="campaign?'#ffffff':s.creative?'#274e62':'#1d5145'" :stroke="campaign?attitudeColor(screenScore(s.id)):'#82dfbd'"/>
        <text :x="s.x" :y="boardY(s)+13" text-anchor="middle" :fill="campaign?'#263d30':'#d9fff3'" font-size="8">{{ campaign?campaign.title:s.creative ? '城市生活 · 示例广告' : s.name }}</text>
        <text :x="s.x" :y="boardY(s)+29" text-anchor="middle" :fill="campaign?`url(#${patternId}-attitude-${i})`:'#a4ffdc'" data-testid="billboard-impressions" font-size="13" font-weight="700">{{ trafficReady?number(impressions[s.id]?.total||0):'AD' }}</text>
      </g>
      <text v-if="!compact" x="290" y="584" fill="#525b65" font-size="10">{{ network.geographic ? "OSM 地图几何 · 代用通行路线与行为仍为假设" : "合成步行网络 · 连续路线 / 过街等候 / 停留 / 出场 · 非真实街区地图" }}</text>
    </svg>
<p v-if="network.geographic" class="map-attribution"><a :href="network.map_url" target="_blank" rel="noopener noreferrer">{{ network.attribution }}</a><span v-if="!compact"> · {{ network.source }}</span></p>
    <div v-if="trafficReady" class="billboard-totals"><button v-for="s in screens" :key="s.id" class="billboard-total" :data-total-screen="s.id" @click="$emit('screen',s.id)"><span>{{ s.name }}</span><b>{{ number(impressions[s.id]?.total||0) }}</b><small>行人 {{ number(impressions[s.id]?.pedestrian||0) }} · 车内 {{ number(impressions[s.id]?.vehicle||0) }}</small></button></div>
    <p v-if="trafficReady" class="impression-note">每趟行程 × 每块牌仅计一次；车辆按假设载客人数计。展开行人分摊原人数权重。回放倒退或全天循环会重新计算，暂停不累加。1× = 30 秒 / 模拟小时。</p>
    <div class="minute-control"><b>{{ hour }}:{{ String(Math.min(59,Math.floor(minute))).padStart(2,'0') }}</b><input aria-label="小时内分钟回放" type="range" min="0" max="59.99" step="0.1" :value="minute" @input="$emit('minute',Number($event.target.value))"><span>小时内连续步行</span></div>
    <p class="route-detail" v-if="selectedTrip"><b>{{ selectedTrip.mode_label }} · {{ selectedTrip.purpose }}</b><br>{{ selectedTrip.origin }} → {{ [...selectedTrip.stops,selectedTrip.destination].join(' → ') }}<br>{{ selectedPosition?.activity || (minute<selectedTrip.start_minute?'尚未进入街区':'已离开当前街区') }} · {{ selectedTrip.distance_m }} 米（情景尺度） · {{ selectedTrip.start_minute.toFixed(1) }}–{{ selectedTrip.end_minute.toFixed(1) }} 分</p>
  </div>
</template>
<script setup>
import {computed,ref,watch,useId} from 'vue'
import {sampleJourney,routePath} from '../utils/neighborhoodPlayback'
import {attitudeColor} from '../utils/campaignPlayback'
const patternId='neighborhood-grid-'+useId()
const props=defineProps({compact:Boolean,mapOnly:Boolean,network:Object,agents:Array,screens:Array,minute:Number,hour:String,selectedAgent:Number,showTrails:Boolean,groupFilter:String,vehicles:{type:Array,default:()=>[]},impressions:{type:Object,default:()=>({})},trafficReady:Boolean,campaign:Object,attitudes:{type:Object,default:()=>({})},attitudeMetric:{type:String,default:"interest"}})
// Fit the actual walkable area, preserving the full network and screen labels.
// The original 1000×590 geometry and encounter coordinates remain unchanged.
const mapViewBox=computed(()=>{
 if(!props.mapOnly||!props.network?.geographic)return '0 0 1000 590'
 const points=[...(props.network.nodes||[]),...(props.screens||[])].filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y))
 if(!points.length)return '0 0 1000 590'
 const x=Math.min(...points.map(p=>p.x))-65,y=Math.min(...points.map(p=>p.y))-65
 const width=Math.max(...points.map(p=>p.x))-x+65,height=Math.max(...points.map(p=>p.y))-y+65
 return `${x} ${y} ${width} ${height}`
})
const emit=defineEmits(['agent','screen','minute'])
const focusedActor=ref(null)
const parent=a=>a.parent_agent_id ?? a.id
const isSelected=a=>focusedActor.value ? a.id===focusedActor.value : parent(a)===props.selectedAgent
function selectActor(a){focusedActor.value=a.id;emit('agent',parent(a))}
watch(()=>props.selectedAgent,id=>{if(!props.agents.some(a=>a.id===focusedActor.value&&parent(a)===id))focusedActor.value=null})
const boardY=s=>s.y<360?s.y-49:s.y+12
const number=n=>Number(n).toLocaleString('zh-CN')
const totalImpressions=computed(()=>Object.values(props.impressions).reduce((n,s)=>n+s.total,0))
const screenScore=id=>props.attitudes[id]?.[props.attitudeMetric]??null
const ratedWeight=computed(()=>Object.values(props.attitudes).reduce((n,a)=>n+(a[props.attitudeMetric+'Weight']||0),0))
const totalAttitude=computed(()=>ratedWeight.value?Object.values(props.attitudes).reduce((n,a)=>n+(a[props.attitudeMetric]??0)*(a[props.attitudeMetric+'Weight']||0),0)/ratedWeight.value:null)
const visibleVehicles=computed(()=>props.vehicles.map(v=>({...v,position:sampleJourney(v.journey,props.minute)})).filter(v=>v.position))
const geometryPath=points=>points.map((p,i)=>`${i?'L':'M'}${p.x},${p.y}`).join(' ')
const namedFeatures=computed(()=>{const picked=[];for(const f of props.network.features||[]){const p=f.points[0];if(!f.tags.name||p.x<30||p.x>970||p.y<35||p.y>550||picked.some(g=>g.tags.name===f.tags.name||Math.hypot(g.points[0].x-p.x,g.points[0].y-p.y)<60))continue;picked.push(f);if(picked.length===15)break}return picked})
const nodeIndex=computed(()=>Object.fromEntries(props.network.nodes.map(n=>[n.id,n])))
const node=id=>nodeIndex.value[id]
const edgePath=e=>`M${node(e.a).x},${node(e.a).y}L${node(e.b).x},${node(e.b).y}`
const trips=computed(()=>props.agents.filter(a=>a.journey))
const departures=computed(()=>trips.value.filter(a=>a.journey.departure_mode==='walking').length)
const routeAgents=computed(()=>trips.value.filter(a=>(props.groupFilter==='all'||a.group===props.groupFilter)&&(props.showTrails||isSelected(a))))
const visible=computed(()=>trips.value.filter(a=>props.groupFilter==='all'||a.group===props.groupFilter).map(a=>({...a,position:sampleJourney(a.journey,props.minute)})).filter(a=>a.position))
const selectedTrip=computed(()=>props.agents.find(a=>isSelected(a))?.journey)
const selectedPosition=computed(()=>sampleJourney(selectedTrip.value,props.minute))
const watching=a=>['watch','interest'].includes(a.reaction)&&Math.abs(props.minute-a.journey.encounter?.minute)<(a.dwell_seconds||0)/60
</script>
<style scoped>
.neighborhood.map-only{display:flex;flex-direction:column;background:#f7f9f9}
.neighborhood.map-only .world-map{flex:1 1 0;width:100%;height:0;min-height:0;aspect-ratio:auto}
.neighborhood.map-only .map-attribution{flex-shrink:0;line-height:1.6;padding:7px 10px;font-size:8px;border-top:1px solid #e7ece9;max-height:none}
.map-only .route-detail{display:none}


.compact .impression-banner{padding:8px 10px;gap:12px;flex-wrap:wrap}
.compact .impression-banner strong{font-size:24px}
.compact .impression-banner small{font-size:9px}
.compact .impression-banner p{display:none}
.compact .impression-banner>span{font-size:10px}
.compact .walk-stats{display:none}
/* Let each map use its full column width instead of a 300px letterboxed panel. */
.compact .world-map{min-height:320px;height:auto;aspect-ratio:1000/590}
.compact .billboard-totals,.compact .impression-note,.compact .minute-control{display:none}
.compact .map-attribution{font-size:9px;padding:5px 10px;max-height:40px;overflow:auto;margin:0}
.compact .route-detail{font-size:10px;padding:8px}
.geographic-map{pointer-events:none}
.map-attribution{font-size:10px;color:#525b65;padding:10px 16px;line-height:1.7}.map-attribution a{color:#31594e}
.walkways .road_proxy{stroke:#708a91;stroke-dasharray:3 3;opacity:.55}
.impression-banner{display:flex;gap:22px;align-items:center;padding:16px;background:#edf5f1;border-top:1px solid #dce7e0;border-bottom:1px solid #dce7e0}
.impression-banner small{font-size:10px;letter-spacing:1px;color:#465d52}
.impression-banner strong{display:block;font-size:30px;font-variant-numeric:tabular-nums;color:#171b1f}
.impression-banner p{font-size:11px;color:#465d52;line-height:1.8}
.impression-banner>span{margin-left:auto;color:#465d52;font-size:11px}
.billboard-totals{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;padding:12px}
.billboard-total{text-align:left;background:#f3f7f5;border:1px solid #d4e2da;color:#20262b;border-radius:6px;padding:10px;cursor:pointer;min-width:0}
.billboard-total span{font-size:10px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.billboard-total b{display:block;color:#171b1f;font-size:20px;margin:6px 0;font-variant-numeric:tabular-nums}
.billboard-total small{font-size:9px;line-height:1.8;display:block}.impression-note{font-size:10px;line-height:1.8;color:#525b65;margin:0;padding:0 16px 10px}
.counting>rect{stroke:#caff81;stroke-width:2}.vehicle-node{pointer-events:auto}
.agent-node text{paint-order:stroke;stroke:#f7f9f9;stroke-width:3px}
.world-map{display:block;width:100%;min-height:300px;background:#f7f9f9}
.walk-stats{display:flex;flex-wrap:wrap;gap:12px;padding:12px 16px;background:#f3f6f5;color:#3e5149;font-size:11px}
.blocks rect{fill:#e1e8e9;stroke:#bbc9ce}.blocks .park{fill:#dcebdc;stroke:#b4ccad}.blocks text{text-anchor:middle;fill:#424d53;font-size:12px}
.walkways path{stroke:#c5d1d4}.walkways .crossing{stroke:#afbec3}.walkways .cross-stripes{stroke:#fff}
.place circle{fill:#6e8d80}.place .boundary{fill:#e0efe8;stroke:#39846c}.place text{fill:#364d42;font-size:10px;paint-order:stroke;stroke:#f7f9f9;stroke-width:3px}
.agent-node,.screen-node{cursor:pointer}.agent-node:focus-visible,.screen-node:focus-visible{outline:2px solid #147d68}
.minute-control{display:flex;gap:12px;align-items:center;padding:12px 16px;color:#525b65;font-size:11px}.minute-control b{font-variant-numeric:tabular-nums;color:#171b1f;font-size:17px}.minute-control input{flex:1;min-width:60px;accent-color:#147d68}
.route-detail{margin:0;padding:12px 16px;background:#edf5f1;color:#303f36;font-size:12px;line-height:1.9}
@media(max-width:750px){.impression-banner{gap:10px;flex-wrap:wrap}.impression-banner>span{width:100%;margin-left:0}.billboard-totals{grid-template-columns:repeat(2,minmax(0,1fr))}.impression-banner strong{font-size:25px}.world-map{min-height:230px}.compact .world-map{min-height:260px}.minute-control span{display:none}}
.map-attitude{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 10px;background:#fff;font-size:10px;border-bottom:1px solid #e2e7e8}.map-attitude span{font-size:9px;color:#58655f}.impression-banner strong,.screen-node text,.screen-node stop{transition:color .35s,fill .35s,stop-color .35s}.screen-node:has([data-testid="billboard-impressions"]) text{font-variant-numeric:tabular-nums}@media(max-width:750px){.map-attitude{flex-wrap:wrap}}
</style>
