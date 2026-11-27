<template>
  <section class="scene-comparison" aria-label="二宫格场景对比">
    <header><h2>场景对比</h2><router-link v-if="!projectId" class="investment-link" :to="{path:'/planning',query:{...(scopedProject?{project:scopedProject}:{}),...(campaign?{campaign:campaign.id}:{})}}">全库存投资规划</router-link><button class="decision-compare-launch" @click="decisionOpen=true">量化选屏对比</button><details class="comparison-options"><summary>场景设置</summary><div class="options-content"><label v-if="!projectId" class="check"><input type="checkbox" v-model="synchronized" @change="toggleSync">同步时间</label><label v-if="!scopedProject" class="check"><input type="checkbox" v-model="loop">循环播放</label><div class="comparison-actions"><button @click="showAdd=!showAdd">{{ showAdd?'收起添加':'从库存添加场景' }}</button><button :disabled="importing" @click="refresh">刷新场景库</button></div><p>各场景独立统计，不能相加为去重覆盖。1× = 30 秒 / 模拟小时。</p></div></details></header>
    <div v-if="error" class="compare-error" role="alert">{{ error }}</div>
    <div v-if="showAdd" class="add-scene"><label>选择 FilteredFrames 地点 · {{ inventory?.filename }}<select aria-label="新增对比地点" v-model="newFrame" :disabled="adding"><option v-for="f in inventory?.frames||[]" :key="f.key" :value="f.key" :disabled="!!f.error">{{ f.address||f.screen_id }} · {{ f.screen_id }}</option></select></label><button :disabled="adding||!newFrame" @click="addScene">{{ adding?stage:'查证地图并添加人群预览' }}</button><label class="comparison-upload">更换工作簿<input type="file" accept=".xlsx" aria-label="上传对比场景工作簿" :disabled="adding" @change="uploadInventory"></label><small>将调用地图及大模型，生成该地点独立画像和全天出行。标记为预览；已完成的 OASIS 运行会自动加入场景库。</small></div>
    <CampaignControls v-if="!scopedProject" @edit="$emit('edit-ad')" :project-id="scopedProject" :scenes="selected" @apply="campaign=$event;$emit('campaign',$event)" @metric="attitudeMetric=$event" />
    <p v-if="scopedProject" class="comparison-note">自动展示两个不同地点；处理期间全天循环播放，全部屏幕处理完成后停止。地图预览不计入报告。</p>
    <div class="comparison-controls"><button v-if="(!projectId || playing) && !simulationRunning" class="play" :disabled="simulationComplete||!synchronized||!selected.some(Boolean)" @click="togglePlayback" :aria-label="playing?'暂停二宫格':'播放二宫格'">{{ playing?'Ⅱ 暂停':'▶ 播放' }}</button><span class="playback-label">回放时间</span><select aria-label="二宫格小时" v-model.number="round" :disabled="!synchronized||simulationRunning" @change="playing=false"><option v-for="r in maxRounds" :key="r" :value="r">第 {{ Math.floor((r-1)/24)+1 }} 天 {{ String((r-1)%24).padStart(2,'0') }}:{{ r===round?String(Math.floor(minute)).padStart(2,'0'):'00' }}</option></select><input aria-label="二宫格分钟" type="range" min="0" max="59.99" step="0.1" v-model.number="minute" :disabled="!synchronized||simulationRunning" @input="playing=false"><select aria-label="二宫格速度" v-model.number="speed"><option v-for="s in [.5,1,2,4,8,16,32]" :key="s" :value="s">{{ s }}×</option></select><span v-if="synchronized&&playing&&ready.some((v,i)=>selected[i]&&!v)" role="status">{{ failed.some(Boolean)?'部分场景加载失败，其余继续播放':bufferExpired?'个别场景缓冲中，其余继续播放':'正在同步时段（最多等候 2 秒）…' }}</span></div>
    <p v-if="dayPlaybackEnded&&!simulationComplete&&!loop" class="comparison-note" role="status">00:00–24:00 全天回放已结束，已自动停止。后台本轮全部屏幕模拟完成后即可生成报告。</p>
    <div :class="['comparison-grid',{focused:focus!=null}]"><ComparisonSceneCard ref="cards" v-for="(_,i) in selected" :key="i" v-show="focus==null||focus===i" :slot="i+1" :scene-id="selected[i]" :experiment-id="campaign?.spec.scene_ids.includes(selected[i])?campaign.id:null" :preview-only="!!scopedProject&&!campaign?.spec.scene_ids.includes(selected[i])" :attitude-metric="attitudeMetric" :catalog="catalog" :round="synchronized?round:clocks[i].round" :minute="synchronized?minute:clocks[i].minute" :synchronized="synchronized" :playing="synchronized ? playing && ready[i] : clocks[i].playing && ready[i]" :active="focus==null||focus===i" :seen-comments="seenComments" :focused="focus===i" @select="select(i,$event)" @focus="focus=focus===i?null:i" @ready="ready[i]=$event" @load-error="failed[i]=$event" @decision="summaries[i]=$event" @hour="clocks[i].round=$event;clocks[i].playing=false" @minute="clocks[i].minute=$event;clocks[i].playing=false" @play="playSlot(i)" /></div>
    <SceneDecisionComparison v-model="decisionOpen" :rows="summaries" @scene="showDecision" /><p class="comparison-footnote">模拟曝光机会 · 非实测观看；颜色仅反映有评分行人的模型态度。</p>
  </section>
</template>
<script setup>
import {ref,computed,onMounted,onBeforeUnmount,watch} from 'vue'
import api from '../api'
import ComparisonSceneCard from './ComparisonSceneCard.vue'
import CampaignControls from './CampaignControls.vue'
import SceneDecisionComparison from './SceneDecisionComparison.vue'
import {fillSceneSlots,advanceClock} from '../utils/comparisonPlayback'
const SCENE_COUNT=2
const seenComments=new Set()
const summaries=ref(Array(SCENE_COUNT).fill(null)),decisionOpen=ref(false),cards=ref([])
function showDecision(i){focus.value=i;cards.value.find(c=>c.slotNumber===i+1)?.showDecision()}
const props=defineProps({currentRunId:String,runComplete:Boolean,projectId:String,initialScene:String,simulationComplete:Boolean,simulationRunning:Boolean})
const emit=defineEmits(['campaign','edit-ad','request-start'])
const scopedProject=props.projectId||new URLSearchParams(window.location.search).get('project')
let requestedScene=props.initialScene||new URLSearchParams(window.location.search).get('scene')
let scopedIds=null,requestedApplied=false
const legacySelectionKey=scopedProject?'pdooh-four-scene-selection-'+scopedProject:'pdooh-four-scene-selection'
const selectionKey=scopedProject?'pdooh-two-scene-selection-'+scopedProject:'pdooh-two-scene-selection'
const campaign=ref(null),attitudeMetric=ref('interest')

const catalog=ref([]),selected=ref(Array(SCENE_COUNT).fill('')),ready=ref(Array(SCENE_COUNT).fill(false)),failed=ref(Array(SCENE_COUNT).fill(false)),bufferExpired=ref(false),error=ref(''),importing=ref(false),focus=ref(null)
const round=ref(1),minute=ref(0),speed=ref(1),playing=ref(false),synchronized=ref(true),loop=ref(false)
const clocks=ref(Array.from({length:SCENE_COUNT},()=>({round:1,minute:0,playing:false})))
const showAdd=ref(false),inventory=ref(null),regionId=ref(null),newFrame=ref(''),adding=ref(false),stage=ref('')
let timer,refreshTimer,bufferStarted=0,last=0,disposed=false,refreshing=false;const imported=new Set(),manualSlots=new Set()
const maxRounds=computed(()=>Math.max(24,...selected.value.map(id=>catalog.value.find(s=>s.id===id)?.rounds||0)))
const dayPlaybackEnded=computed(()=>synchronized.value?round.value===maxRounds.value&&minute.value>=59.99:clocks.value.every((c,i)=>!selected.value[i]||(c.round===(catalog.value.find(s=>s.id===selected.value[i])?.rounds||24)&&c.minute>=59.99)))
const clock=computed(()=>`${String((round.value-1)%24).padStart(2,'0')}:${String(Math.floor(minute.value)).padStart(2,'0')}`)
function startPlayback({reset=false}={}){
 if(props.simulationComplete)return
 if(reset||dayPlaybackEnded.value){round.value=1;minute.value=0;clocks.value.forEach(c=>Object.assign(c,{round:1,minute:0,playing:false}))}
 synchronized.value=true;loop.value=!!props.projectId;playing.value=true;bufferStarted=0;last=performance.now()
}
function playSlot(i){if(props.simulationComplete)return;if(clocks.value[i].playing){clocks.value[i].playing=false;return}if(props.projectId)emit('request-start');else clocks.value[i].playing=true}
function stopPlayback(){playing.value=false;clocks.value.forEach(c=>c.playing=false)}
function togglePlayback(){if(playing.value){stopPlayback();return}if(props.projectId)emit('request-start');else startPlayback()}
defineExpose({startPlayback,stopPlayback,refresh})
function persist(){localStorage.setItem(selectionKey,JSON.stringify({selected:selected.value,manual:[...manualSlots]}))}
function select(i,id){failed.value[i]=false;manualSlots.add(i);selected.value[i]=id;ready.value[i]=false;persist()}
function toggleSync(){playing.value=false;if(!synchronized.value)clocks.value=clocks.value.map(()=>({round:round.value,minute:minute.value,playing:false}));else clocks.value.forEach(c=>c.playing=false)}
async function refresh(){if(refreshing)return;refreshing=true;error.value='';try{
 if(props.currentRunId&&props.runComplete&&!imported.has(props.currentRunId)){importing.value=true;await api.post('/api/world/comparison-scenes/import',{run_id:props.currentRunId});imported.add(props.currentRunId)}
 const r=await api.get('/api/world/comparison-scenes');if(disposed)return;
 if(scopedProject){const batch=(await api.get(`/api/planning/${scopedProject}/coverage`)).data;r.data=r.data.map(s=>({...s,current_batch:batch.scene_ids.includes(s.id)})).sort((a,b)=>Number(b.current_batch)-Number(a.current_batch));if(batch.campaign_id){if(campaign.value?.id!==batch.campaign_id){if(!playing.value){round.value=props.simulationComplete?24:1;minute.value=props.simulationComplete?59.99:0}}const active=(await api.get('/api/world/campaign-experiments/'+batch.campaign_id)).data;active.spec.scene_ids=batch.scene_ids;campaign.value=active}else campaign.value=null;}

 if(scopedProject){if(!scopedIds){const inv=(await api.post('/api/world/geo-inventory',{project_id:scopedProject})).data;inventory.value=inv;scopedIds=new Map(inv.frames.filter(f=>!f.error).map(f=>[f.screen_id,f.coordinate]))}r.data=r.data.filter(s=>{const p=scopedIds.get(s.screen_id),q=s.coordinate;return p&&q&&Math.hypot(p.lat-q.lat,(p.lon-q.lon)*Math.cos(p.lat*Math.PI/180))*111320<=30});if(!requestedApplied&&requestedScene&&r.data.some(s=>s.id===requestedScene)&&!selected.value.includes(requestedScene)){selected.value[0]=requestedScene;manualSlots.add(0);requestedApplied=true}}
 catalog.value=r.data
 selected.value=fillSceneSlots(r.data,selected.value,SCENE_COUNT)
 persist();if(selected.value.some(id=>!id))void ensurePreviews()
 }catch(e){if(!disposed)error.value=e.message}finally{refreshing=false;importing.value=false}}
let preparingPreviews=false
const attemptedPreviews=new Set()
async function ensurePreviews(){
 if(preparingPreviews||disposed)return;preparingPreviews=true
 try{
  if(!inventory.value)inventory.value=(await api.post('/api/world/geo-inventory',scopedProject?{project_id:scopedProject}:{})).data
  while(!disposed&&selected.value.some(id=>!id)){
   const frame=inventory.value.frames.find(f=>!f.error&&!attemptedPreviews.has(f.key)&&!catalog.value.some(s=>s.coordinate&&Math.hypot(s.coordinate.lat-f.coordinate.lat,s.coordinate.lon-f.coordinate.lon)<.0003))
   if(!frame)break
   attemptedPreviews.add(frame.key);stage.value='正在自动准备地点地图…'
   try{
    const context=(await api.post('/api/world/locate-frame',{inventory_id:inventory.value.id,frame_key:frame.key,radius_m:400})).data
    if(disposed)break
    const template=(await api.post('/api/world/local-audiences',{locality:context.locality,group_count:12})).data
    if(disposed)break
    await api.post('/api/world/comparison-scenes/preview',{agent_count:100,total_population:30000,seed:42,day_cycle:{days:1},locality:context.locality,template_id:template.id})
    if(disposed)break
    await refresh()
   }catch(e){error.value='自动准备地点失败：'+e.message;break}
  }
 }catch(e){if(!disposed)error.value=e.message}finally{preparingPreviews=false;stage.value=''}
}
watch(()=>[props.currentRunId,props.runComplete],refresh)
watch(()=>props.initialScene,value=>{requestedScene=value;requestedApplied=false;void refresh()})
watch(round,()=>{bufferStarted=0;bufferExpired.value=false})
watch(()=>props.simulationRunning,running=>{if(running)startPlayback();else stopPlayback()},{immediate:true})
watch(()=>props.simulationComplete,done=>{if(done){playing.value=false;round.value=maxRounds.value;minute.value=59.99;clocks.value.forEach((c,i)=>Object.assign(c,{round:catalog.value.find(s=>s.id===selected.value[i])?.rounds||24,minute:59.99,playing:false}));clearInterval(refreshTimer);void refresh()}},{immediate:true})
watch(showAdd,async value=>{if(!value||inventory.value)return;try{inventory.value=(await api.post('/api/world/geo-inventory',localStorage.getItem('pdooh-planning-project')?{project_id:localStorage.getItem('pdooh-planning-project')}:{})).data;newFrame.value=inventory.value.frames.find(f=>!f.error)?.key||'';regionId.value=(await api.get('/api/world/regions/latest/'+inventory.value.id)).data?.id}catch(e){error.value=e.message}})
async function uploadInventory(event){const file=event.target.files[0];if(!file)return;adding.value=true;stage.value='读取工作簿…';error.value='';try{const data=new FormData();data.append('file',file);inventory.value=(await api.post('/api/world/geo-inventory',data,{headers:{'Content-Type':'multipart/form-data'}})).data;newFrame.value=inventory.value.frames.find(f=>!f.error)?.key||'';regionId.value=(await api.get('/api/world/regions/latest/'+inventory.value.id)).data?.id}catch(e){error.value=e.message}finally{adding.value=false;event.target.value=''}}
async function addScene(){adding.value=true;error.value='';try{stage.value='查证坐标与周边地图…';const context=(await api.post('/api/world/locate-frame',{inventory_id:inventory.value.id,frame_key:newFrame.value,radius_m:400,region_id:regionId.value})).data;stage.value='生成本地人群画像…';const template=(await api.post('/api/world/local-audiences',{locality:context.locality,group_count:12})).data;stage.value='生成全天人车预览…';const item=(await api.post('/api/world/comparison-scenes/preview',{agent_count:100,total_population:30000,seed:42,day_cycle:{days:1},locality:context.locality,template_id:template.id})).data;if(disposed)return;await refresh();const slot=selected.value.findIndex(id=>!id);select(slot<0?SCENE_COUNT-1:slot,item.id);showAdd.value=false}catch(e){error.value=e.message}finally{adding.value=false}}
onMounted(()=>{try{const saved=JSON.parse(localStorage.getItem(selectionKey)||localStorage.getItem(legacySelectionKey)||'null');const slots=Array.isArray(saved)?saved:saved?.selected;if(Array.isArray(slots)&&slots.length>=SCENE_COUNT&&slots.every(x=>typeof x==='string'))selected.value=slots.slice(0,SCENE_COUNT);for(const i of saved?.manual||[])if(Number.isInteger(i)&&i>=0&&i<SCENE_COUNT)manualSlots.add(i)}catch{}refresh();if(!props.simulationComplete)refreshTimer=setInterval(refresh,15000);last=performance.now();timer=setInterval(()=>{const now=performance.now(),delta=Math.min(now-last,1000)*60*speed.value/30000;last=now;if(synchronized.value){const waiting=selected.value.some((id,i)=>id&&!ready.value[i]&&!failed.value[i]);
if(waiting){if(!bufferStarted)bufferStarted=now;bufferExpired.value=now-bufferStarted>=2000}else{bufferStarted=0;bufferExpired.value=false}
if(!props.simulationRunning&&selected.value.some(Boolean)&&selected.value.every((id,i)=>!id||failed.value[i]))playing.value=false;
if(playing.value&&selected.value.some(Boolean)&&(!waiting||bufferExpired.value)){const next=advanceClock(round.value,minute.value,delta,maxRounds.value,loop.value);round.value=next.round;minute.value=next.minute;playing.value=next.playing}}else clocks.value.forEach((c,i)=>{if(c.playing&&selected.value[i]&&ready.value[i])Object.assign(c,advanceClock(c.round,c.minute,delta,catalog.value.find(s=>s.id===selected.value[i])?.rounds||24,loop.value))})},100)})
onBeforeUnmount(()=>{disposed=true;clearInterval(timer);clearInterval(refreshTimer)})
</script>
<style scoped>
.investment-link{font-size:10px;color:#286246;text-decoration:none;border:1px solid #cfddd3;border-radius:5px;padding:7px 10px;margin-left:auto}

.scene-comparison .decision-compare-launch{margin-left:auto;font-size:10px;padding:5px 8px}

.comparison-options{position:relative;font-size:11px}.comparison-options>summary{cursor:pointer;color:#53635a;padding:7px 0}.options-content{position:absolute;right:0;top:32px;z-index:8;width:280px;background:#fff;padding:16px;border:1px solid #dce2e5;border-radius:7px;box-shadow:0 8px 24px #19332714}.options-content>.check{margin-bottom:12px}.options-content p{font-size:10px;color:#627168;line-height:1.7;margin-bottom:0}.options-content .comparison-actions{flex-wrap:wrap}@media(max-width:380px){.options-content{width:245px}}

.scene-comparison{--scene-body-height:clamp(300px,51cqw,780px);margin:8px 0 16px;background:#fff;border:1px solid #dce2e5;border-radius:10px;padding:10px;color:#191d21}
.scene-comparison>header{height:auto;min-height:30px;display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
.scene-comparison header small{font-size:9px;letter-spacing:1.5px;color:#525b65}
.scene-comparison h2{font-size:17px;font-weight:600;color:#171b1f;margin:2px 0}
.comparison-actions{display:flex;gap:8px}
.scene-comparison button{background:#fff;border:1px solid #d2dbde;border-radius:5px;color:#20262b;padding:7px 10px;font-size:11px;cursor:pointer}
.scene-comparison button:hover{background:#f1f5f4;border-color:#9aafa7}
.scene-comparison button:disabled{opacity:.5;cursor:not-allowed}
.comparison-note,.comparison-footnote{font-size:11px;color:#525b65;line-height:1.7}
.comparison-footnote{margin:10px 0 0}
.comparison-controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0;background:#f5f7f8;border:1px solid #e1e6e8;border-radius:6px;padding:5px;font-size:11px;color:#30373c}
.comparison-controls .play{background:#e6f3ed;color:#172c24;border-color:#bcd9cd;min-width:92px}
.comparison-controls select,.add-scene select{background:#fff;border:1px solid #d2dbde;border-radius:5px;color:#20262b;padding:5px 7px;font-size:11px}
.comparison-controls>b{color:#171b1f;font-size:17px;font-variant-numeric:tabular-nums}
.comparison-controls>input[type=range]{flex:1;min-width:100px;accent-color:#147d68}
.check{display:flex;align-items:center;gap:6px;white-space:nowrap}.check input{accent-color:#147d68}
.comparison-grid{align-items:start;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.comparison-grid.focused{grid-template-columns:minmax(0,1fr);--scene-body-height:clamp(420px,72dvh,960px)}

.comparison-upload{font-size:11px!important}.comparison-upload input{display:block;margin-top:8px;font-size:11px;max-width:220px}
.compare-error{color:#a33d2e;font-size:12px;margin:12px 0}
.add-scene{display:flex;align-items:end;gap:12px;flex-wrap:wrap;background:#f3f7f5;padding:15px;border:1px solid #dce5e0;border-radius:6px;margin:12px 0}
.add-scene label{flex:1;min-width:200px;font-size:11px;color:#30373c}.add-scene select{display:block;width:100%;margin-top:8px}
.add-scene small{width:100%;font-size:11px;line-height:1.8;color:#525b65}
@media(min-width:751px) and (max-width:1099px){.comparison-grid{grid-template-columns:minmax(0,1fr)}}
@media(max-width:750px){.scene-comparison{padding:10px}.comparison-grid{grid-template-columns:minmax(0,1fr)}.scene-comparison h2{font-size:17px}.comparison-controls{gap:8px}.comparison-actions{flex-wrap:wrap}}
</style>
