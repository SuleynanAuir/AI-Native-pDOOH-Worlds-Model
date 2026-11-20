<template>
  <article class="comparison-card" :data-slot="slot" :data-scene="sceneId" :data-round="frame?.round||0" :aria-label="`场景 ${slot}`">
    <header><span class="slot-number">{{ String(slot).padStart(2,'0') }}</span><label><select :aria-label="`场景 ${slot} 选择`" :value="sceneId" @change="$emit('select',$event.target.value)"><option value="">请选择地点</option><option v-for="item in catalog" :key="item.id" :value="item.id">{{ item.title.replace(/ 周边.*$/,'') }}{{ item.source_type==='oasis'?'':' · 预览' }}</option></select></label><button :aria-label="`放大场景 ${slot}`" @click="$emit('focus')">{{ focused?'返回四宫格':'放大' }}</button></header>
    <div v-if="base" class="card-context"><span>{{ base.meta.agent_count }} 个代表 · {{ number(base.meta.total_population) }} 人情景</span><span>{{ base.campaign?'广告模拟':base.meta.source_type==='oasis'?'OASIS 回放':'预览' }}</span></div>
    <div v-if="error" class="card-error" role="alert">{{ error }}<button @click="load">重试</button></div><div v-else-if="busy" class="card-placeholder" role="status">正在读取场景与当前小时…</div><div v-else-if="!sceneId" class="card-placeholder">从上方选择一个地点<br><small>可使用场景库，或从库存添加新地点</small></div><div v-else-if="!frame" class="card-placeholder">该场景没有此时段<br><small>不会将其他小时的记录复制到这里</small></div>
    <div v-if="base" v-show="frame && !busy && !error" class="scene-live-layout">
    <NeighborhoodMap compact map-only :network="base.network" :screens="base.screens" :agents="frame?.pedestrians || []" :vehicles="frame?.vehicles || []" :minute="minute" :hour="String((round-1)%24).padStart(2,'0')" :selected-agent="selectedAgent" :show-trails="showTrails" group-filter="all" :impressions="counts" :attitudes="attitudes" :attitude-metric="attitudeMetric" :campaign="base.campaign" traffic-ready @agent="openPerson" @screen="openScreen" />
    <aside class="scene-live-sidebar" aria-label="场景实时反馈">
      <div class="scene-live-metrics"><div><span>Impressions <small>模拟曝光</small></span><strong data-testid="total-impressions" :style="{color:attitudeColor(liveScore)}">{{ number(totalImpressions) }}</strong></div><div class="scene-interest"><span>{{ attitudeMetric==='interest'?'感兴趣程度':'好感度' }}</span><b :style="{color:attitudeColor(liveScore)}">{{ liveScore==null?'—':liveScore.toFixed(1) }}<small v-if="liveScore!=null"> / 100</small></b></div></div>
      <LiveAudienceComments :events="base.events" :narrative="narrative" :round="round" :minute="minute" :playing="playing && !busy" :active="active" :seen="seenComments" />
    </aside></div>
    <div v-if="selectedAgent!=null && selected && !base?.attitudes" class="card-person"><button @click="selectedAgent=null" aria-label="关闭画像">×</button><b>{{ selected.name }}</b><p>{{ group?.name }} · {{ group?.profile?.needs }} · {{ group?.profile?.mobility }}</p><p>代表画像权重 {{ number(selectedWeight) }} 人；此格的展开行人共享该画像。</p><template v-if="personAttitude"><p><b>对 {{ base.campaign.title }} 的模型推演</b></p><p>好感 {{ score(personAttitude.favorability) }} · 兴趣 {{ score(personAttitude.interest) }} · {{ personAttitude.confidence }} 置信度</p><p>{{ personAttitude.reason }}</p><small>依据 {{ personAttitude.source_ids.join("、") }} · 非真实个人调查</small></template></div>
    <div class="card-window-actions"><AudienceNarratives ref="analysisWindow" v-if="base?.attitudes && experimentId" :experiment-id="experimentId" :scene-id="sceneId" :selected-agent="selectedAgent" :scene-title="base.meta.title" @loaded="narrative=$event" /><button type="button" aria-haspopup="dialog" :aria-expanded="detailsOpen" :disabled="!base" @click="selectedScreen=null;detailsOpen=true">场景详情</button></div>
    <ModalWindow v-model="detailsOpen" title="场景详情" :subtitle="base?.meta.title"><div v-if="base" class="scene-details-body"><p>{{ sourceDate }} · {{ currentSlot?.period_label }} · {{ clock }} · {{ base.meta.group_count }} 类画像</p><p>{{ base.meta.source_label }}</p>
    <div v-if="base?.campaign" class="card-campaign"><b>{{ base.campaign.title }}</b><span>区域基准 {{ base.traffic.vehicles_per_hour }} 辆/h · 未实测校准</span><small>颜色：{{ attitudeMetric==='interest'?'兴趣':'好感' }} · 仅汇总有评分的行人曝光；车内人员态度未知</small></div>
    <details v-if="base?.attitudes" class="attitude-details" :open="selectedScreen!=null"><summary>人群态度与推演依据 · {{ base.attitudes.groups.length }} 类</summary><p>{{ base.attitude_caveat }}</p><div v-for="g in base.attitudes.groups" :key="g.id" class="attitude-group"><span>{{ g.name }}</span><b :style="{color:attitudeColor(g[attitudeMetric])}">{{ score(g[attitudeMetric]) }}</b></div><small>表中为全部代表画像加权分，地图颜色按实际回放经过的画像加权，两者可能不同。点击地图上的行人可看个人原因。</small><p v-if="base.traffic.policies.length">{{ base.traffic.policies.map(p=>p.road+'：'+p.note).join('；') }}</p></details>
<button @click="showTrails=!showTrails" :aria-pressed="showTrails">{{ showTrails?'隐藏轨迹':'显示轨迹' }}</button><small>{{ frame ? `${frame.pedestrians.length} 段步行 / ${frame.vehicles.length} 段车行 · 本小时` : '独立场景' }}</small></div></ModalWindow>
    <div v-if="!synchronized" class="independent-clock"><button @click="$emit('play')">{{ playing?'暂停':'播放' }}</button><select :aria-label="`场景 ${slot} 小时`" :value="round" @change="$emit('hour',Number($event.target.value))"><option v-for="s in base?.meta.schedule||[]" :key="s.round" :value="s.round">第 {{ s.day||1 }} 天 {{ s.time }}</option></select><input :aria-label="`场景 ${slot} 分钟`" type="range" min="0" max="59.99" step="0.1" :value="minute" @input="$emit('minute',Number($event.target.value))"></div>
  </article>
</template>
<script setup>
import {ref,shallowRef,computed,watch,onBeforeUnmount} from 'vue'
import api from '../api'
import NeighborhoodMap from './NeighborhoodMap.vue'
import AudienceNarratives from './AudienceNarratives.vue'
import ModalWindow from './ModalWindow.vue'
import LiveAudienceComments from './LiveAudienceComments.vue'
import {indexImpressions,impressionsAt} from '../utils/trafficPlayback'
import {indexAttitudes,attitudesAt,attitudeColor} from '../utils/campaignPlayback'
const props=defineProps({slot:Number,sceneId:String,catalog:Array,round:Number,minute:Number,synchronized:Boolean,playing:Boolean,focused:Boolean,active:{type:Boolean,default:true},seenComments:{type:Set,default:()=>new Set()},experimentId:String,attitudeMetric:{type:String,default:"interest"}})
const emit=defineEmits(['select','focus','play','hour','minute','ready'])
const base=shallowRef(null),frame=shallowRef(null),busy=ref(false),error=ref(''),selectedAgent=ref(null),showTrails=ref(false)
const narrative=shallowRef(null)
const selectedScreen=ref(null),detailsOpen=ref(false),analysisWindow=ref(null)
function openPerson(id){selectedAgent.value=id;selectedScreen.value=null;analysisWindow.value?.show(id)}
function openScreen(id){selectedAgent.value=null;selectedScreen.value=id;detailsOpen.value=true}
watch(()=>[props.sceneId,props.experimentId],()=>{detailsOpen.value=false;narrative.value=null})
let loadedEndpoint='',ticket=0,controller=null;const hours=new Map()
const index=computed(()=>indexImpressions(base.value?.events))
const counts=computed(()=>impressionsAt(index.value,props.round,props.minute))
const attitudeIndex=computed(()=>indexAttitudes(base.value?.events,base.value?.attitudes?.agents))
const attitudes=computed(()=>base.value?.attitudes?attitudesAt(attitudeIndex.value,props.round,props.minute):{})
const totalImpressions=computed(()=>Object.values(counts.value).reduce((sum,row)=>sum+row.total,0))
const liveScore=computed(()=>{
 const metric=props.attitudeMetric,rows=Object.values(attitudes.value),weight=rows.reduce((sum,row)=>sum+(row[metric+'Weight']||0),0)
 return weight?rows.reduce((sum,row)=>sum+(row[metric]??0)*(row[metric+'Weight']||0),0)/weight:null
})
const personAttitude=computed(()=>base.value?.attitudes?.agents[String(selectedAgent.value)])
const score=n=>n==null?'未知':Number(n).toFixed(1)+'/100'
const endpoint=computed(()=>props.experimentId?`/api/world/campaign-experiments/${props.experimentId}/scenes/${props.sceneId}`:'/api/world/comparison-scenes/'+props.sceneId)
const currentSlot=computed(()=>base.value?.meta.schedule.find(s=>s.round===props.round))
const sourceDate=computed(()=>currentSlot.value?.date||`模拟第 ${Math.floor((props.round-1)/24)+1} 天（未设日期）`)
const clock=computed(()=>`${String((props.round-1)%24).padStart(2,'0')}:${String(Math.floor(props.minute)).padStart(2,'0')}`)
const selected=computed(()=>frame.value?.pedestrians.find(a=>a.parent_agent_id===selectedAgent.value))
const group=computed(()=>base.value?.groups.find(g=>g.id===selected.value?.group))
const selectedWeight=computed(()=>frame.value?.pedestrians.filter(a=>a.parent_agent_id===selectedAgent.value).reduce((n,a)=>n+a.represented_population,0)||0)
const number=n=>Number(n).toLocaleString('zh-CN')
async function load(){const token=++ticket;controller?.abort();controller=new AbortController();const signal=controller.signal;frame.value=null;selectedAgent.value=null;selectedScreen.value=null;error.value='';busy.value=true;emit('ready',false)
 try{if(!props.sceneId){base.value=null;return}
  if(!base.value||loadedEndpoint!==endpoint.value){base.value=null;hours.clear();const url=endpoint.value;const r=await api.get(url,{signal});if(token!==ticket)return;base.value=r.data;loadedEndpoint=url}
  if(props.round<1||props.round>base.value.meta.rounds)return
  if(hours.has(props.round)){frame.value=hours.get(props.round);return}
  const round=props.round;const r=await api.get(`${endpoint.value}/hours/${round}`,{signal});if(token!==ticket)return;frame.value=r.data;hours.set(round,r.data);while(hours.size>3)hours.delete(hours.keys().next().value)
 }catch(e){if(token===ticket&&!signal.aborted)error.value=e.message}finally{if(token===ticket){busy.value=false;emit('ready',true)}}}
watch(()=>[props.sceneId,props.round,props.experimentId],load,{immediate:true})
onBeforeUnmount(()=>{ticket++;controller?.abort()})
</script>
<style scoped>
.comparison-card{container-type:inline-size}
.scene-live-layout{display:grid;grid-template-columns:minmax(0,1fr) clamp(182px,34%,290px);height:var(--scene-body-height,440px);min-height:0;border-top:1px solid #e7ece9}
.scene-live-layout>.neighborhood{min-width:0;min-height:0;height:100%;overflow:hidden}
.scene-live-sidebar{min-width:0;min-height:0;display:flex;flex-direction:column;gap:12px;padding:14px 10px 10px;border-left:1px solid #e3eae6;background:#fcfdfc}
.scene-live-metrics{display:grid;gap:9px;flex-shrink:0}.scene-live-metrics span{font-size:11px;color:#27332d}.scene-live-metrics span>small{font-size:8px;color:#7b867f;margin-left:4px}.scene-live-metrics strong{display:block;margin-top:3px;font-size:28px;line-height:1.1;letter-spacing:-.6px;font-variant-numeric:tabular-nums;font-weight:650;transition:color .35s}.scene-interest{display:flex;align-items:center;justify-content:space-between;gap:6px}.scene-interest b{font-size:16px;font-weight:550;font-variant-numeric:tabular-nums}.scene-interest b>small{font-size:9px;font-weight:400;color:#7b867f}
@container(max-width:460px){.scene-live-layout{grid-template-columns:minmax(0,1fr);height:auto}.scene-live-layout>.neighborhood{height:350px}.scene-live-sidebar{border-left:0;border-top:1px solid #e3eae6;height:390px;padding:14px;gap:14px}.scene-live-metrics{grid-template-columns:1fr 1fr;align-items:center;gap:16px}.scene-interest{display:block}.scene-interest>b{display:block;margin-top:5px}.scene-live-metrics strong{font-size:28px}}

.card-window-actions{display:flex;gap:8px;padding:7px 10px;border-top:1px solid #e2e7e8;align-items:center}.comparison-card .card-window-actions>button,.scene-details-body>button{font:inherit;font-size:11px;padding:6px 10px;color:#284e3c;background:#fff;border:1px solid #cadbce;border-radius:5px;cursor:pointer}.card-window-actions>button:disabled{opacity:.5;cursor:wait}.card-window-actions>button:focus-visible{outline:2px solid #147d68;outline-offset:2px}

.scene-details{border-top:1px solid #e2e7e8;font-size:10px;color:#536159}.scene-details>summary{padding:9px 12px;cursor:pointer}.scene-details-body{padding:0 12px 12px;line-height:1.8}.scene-details-body>small{margin-left:10px}.scene-details-body .card-campaign{padding:8px 0}.card-context{display:flex;justify-content:space-between;gap:8px;font-size:10px}.comparison-card header label select{margin:0}

.comparison-card{min-width:0;background:#fff;border:1px solid #d4dfe0;border-radius:8px;overflow:hidden;color:#191d21}
.comparison-card>header{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid #e2e7e8}
.slot-number{font-size:16px;color:#38453f;font-variant-numeric:tabular-nums}
.comparison-card header label{flex:1;min-width:0;font-size:9px;color:#525b65}
.comparison-card select{display:block;width:100%;background:#fff;color:#20262b;border:1px solid #d2dbde;border-radius:4px;font-size:10px;padding:6px;margin-top:3px}
.comparison-card button{background:#f5f7f8;color:#20262b;border:1px solid #d2dbde;border-radius:4px;padding:6px 9px;cursor:pointer;font-size:10px}
.comparison-card button:hover{background:#e6f3ed;border-color:#9aafa7}
.card-context{padding:7px 10px;line-height:1.5}
.card-context>b{display:block;font-size:11px;font-weight:600;color:#191d21;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-context>div{display:flex;gap:8px;flex-wrap:wrap;font-size:10px;margin:3px 0;color:#525b65}
.card-context .oasis{color:#17634e}.card-context .preview{color:#86560d}.card-context small{font-size:10px;color:#525b65}
.card-placeholder{min-height:360px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#525b65;font-size:12px;line-height:2.5}.card-placeholder small{font-size:11px}
.card-error{padding:20px;color:#a33d2e;font-size:12px;line-height:1.8}.card-error button{margin-left:10px}
.comparison-card>footer{display:flex;align-items:center;justify-content:space-between;padding:6px 10px;color:#525b65;font-size:10px;border-top:1px solid #e2e7e8;gap:8px}
.independent-clock{display:flex;align-items:center;gap:8px;padding:8px 10px;border-top:1px solid #e2e7e8}.independent-clock select{width:135px;margin:0}.independent-clock input{min-width:40px;flex:1;accent-color:#147d68}
.card-person{padding:12px;background:#edf5f1;color:#20262b;font-size:12px}.card-person button{float:right}.card-person p{font-size:11px;line-height:1.7;margin:6px 0}
.card-campaign{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:8px 10px;background:#f1f6f3;font-size:10px;border-top:1px solid #dce2e5}.card-campaign b{color:#202e26}.card-campaign span{margin-left:auto}.card-campaign small{width:100%;color:#526059;font-size:9px}.attitude-details{padding:8px 10px;border-top:1px solid #e2e7e8;font-size:10px;color:#47544c;line-height:1.8}.attitude-details summary{cursor:pointer;color:#20262b}.attitude-details p,.attitude-details small{display:block;margin:7px 0}.attitude-group{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px solid #edf0ee}.attitude-group span{min-width:0}.attitude-group b{white-space:nowrap;font-variant-numeric:tabular-nums}
.card-window-actions :deep(.analysis-launch){font-size:11px;padding:6px 10px}
</style>
