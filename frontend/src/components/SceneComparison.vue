<template>
  <section class="scene-comparison" aria-label="四宫格场景对比">
    <header><h2>场景对比</h2><details class="comparison-options"><summary>场景设置</summary><div class="options-content"><label class="check"><input type="checkbox" v-model="synchronized" @change="toggleSync">同步时间</label><label class="check"><input type="checkbox" v-model="loop">循环播放</label><div class="comparison-actions"><button @click="showAdd=!showAdd">{{ showAdd?'收起添加':'从库存添加场景' }}</button><button :disabled="importing" @click="refresh">刷新场景库</button></div><p>各场景独立统计，不能相加为去重覆盖。1× = 30 秒 / 模拟小时。</p></div></details></header>
    <div v-if="error" class="compare-error" role="alert">{{ error }}</div>
    <div v-if="showAdd" class="add-scene"><label>选择 FilteredFrames 地点 · {{ inventory?.filename }}<select aria-label="新增对比地点" v-model="newFrame" :disabled="adding"><option v-for="f in inventory?.frames||[]" :key="f.key" :value="f.key" :disabled="!!f.error">{{ f.address||f.screen_id }} · {{ f.screen_id }}</option></select></label><button :disabled="adding||!newFrame" @click="addScene">{{ adding?stage:'查证地图并添加人群预览' }}</button><label class="comparison-upload">更换工作簿<input type="file" accept=".xlsx" aria-label="上传对比场景工作簿" :disabled="adding" @change="uploadInventory"></label><small>将调用地图及大模型，生成该地点独立画像和全天出行。标记为预览；已完成的 OASIS 运行会自动加入场景库。</small></div>
    <CampaignControls :scenes="selected" @apply="campaign=$event" @metric="attitudeMetric=$event" />
    <div class="comparison-controls"><button class="play" :disabled="!synchronized||!selected.some(Boolean)" @click="playing=!playing" :aria-label="playing?'暂停四宫格':'播放四宫格'">{{ playing?'Ⅱ 暂停':'▶ 播放' }}</button><select aria-label="四宫格小时" v-model.number="round" :disabled="!synchronized" @change="playing=false"><option v-for="r in maxRounds" :key="r" :value="r">第 {{ Math.floor((r-1)/24)+1 }} 天 {{ String((r-1)%24).padStart(2,'0') }}:{{ r===round?String(Math.floor(minute)).padStart(2,'0'):'00' }}</option></select><input aria-label="四宫格分钟" type="range" min="0" max="59.99" step="0.1" v-model.number="minute" :disabled="!synchronized" @input="playing=false"><select aria-label="四宫格速度" v-model.number="speed"><option v-for="s in [.5,1,2,4,8,16,32]" :key="s" :value="s">{{ s }}×</option></select><span v-if="synchronized&&playing&&ready.some((v,i)=>selected[i]&&!v)" role="status">等候各格时段载入…</span></div>
    <div :class="['comparison-grid',{focused:focus!=null}]"><ComparisonSceneCard v-for="(_,i) in selected" :key="i" v-show="focus==null||focus===i" :slot="i+1" :scene-id="selected[i]" :experiment-id="campaign?.spec.scene_ids.includes(selected[i])?campaign.id:null" :attitude-metric="attitudeMetric" :catalog="catalog" :round="synchronized?round:clocks[i].round" :minute="synchronized?minute:clocks[i].minute" :synchronized="synchronized" :playing="synchronized ? playing && ready.every((v,j)=>!selected[j]||v) : clocks[i].playing && ready[i]" :active="focus==null||focus===i" :seen-comments="seenComments" :focused="focus===i" @select="select(i,$event)" @focus="focus=focus===i?null:i" @ready="ready[i]=$event" @hour="clocks[i].round=$event;clocks[i].playing=false" @minute="clocks[i].minute=$event;clocks[i].playing=false" @play="clocks[i].playing=!clocks[i].playing" /></div>
    <p class="comparison-footnote">模拟曝光机会 · 非实测观看；颜色仅反映有评分行人的模型态度。</p>
  </section>
</template>
<script setup>
import {ref,computed,onMounted,onBeforeUnmount,watch} from 'vue'
import api from '../api'
import ComparisonSceneCard from './ComparisonSceneCard.vue'
import CampaignControls from './CampaignControls.vue'
import {distinctScenes,advanceClock} from '../utils/comparisonPlayback'
const seenComments=new Set()
const campaign=ref(null),attitudeMetric=ref('interest')
const props=defineProps({currentRunId:String,runComplete:Boolean})
const catalog=ref([]),selected=ref(['','','','']),ready=ref([false,false,false,false]),error=ref(''),importing=ref(false),focus=ref(null)
const round=ref(9),minute=ref(23.3),speed=ref(1),playing=ref(!window.matchMedia('(prefers-reduced-motion: reduce)').matches),synchronized=ref(true),loop=ref(true)
const clocks=ref(Array.from({length:4},()=>({round:9,minute:23.3,playing:false})))
const showAdd=ref(false),inventory=ref(null),regionId=ref(null),newFrame=ref(''),adding=ref(false),stage=ref('')
let timer,refreshTimer,last=0,disposed=false,refreshing=false;const imported=new Set(),manualSlots=new Set()
const maxRounds=computed(()=>Math.max(24,...selected.value.map(id=>catalog.value.find(s=>s.id===id)?.rounds||0)))
const clock=computed(()=>`${String((round.value-1)%24).padStart(2,'0')}:${String(Math.floor(minute.value)).padStart(2,'0')}`)
function persist(){localStorage.setItem('pdooh-four-scene-selection',JSON.stringify({selected:selected.value,manual:[...manualSlots]}))}
function select(i,id){manualSlots.add(i);selected.value[i]=id;ready.value[i]=false;persist()}
function toggleSync(){playing.value=false;if(!synchronized.value)clocks.value=clocks.value.map(()=>({round:round.value,minute:minute.value,playing:false}));else clocks.value.forEach(c=>c.playing=false)}
async function refresh(){if(refreshing)return;refreshing=true;error.value='';try{
 if(props.currentRunId&&props.runComplete&&!imported.has(props.currentRunId)){importing.value=true;await api.post('/api/world/comparison-scenes/import',{run_id:props.currentRunId});imported.add(props.currentRunId)}
 const r=await api.get('/api/world/comparison-scenes');if(disposed)return;catalog.value=r.data
 const ids=new Set(r.data.map(s=>s.id));selected.value=selected.value.map(id=>ids.has(id)?id:'')
 const defaults=distinctScenes(r.data);for(let i=0;i<4;i++)if(!selected.value[i]&&!manualSlots.has(i)){const used=new Set(selected.value.map(id=>r.data.find(s=>s.id===id)?.location_key));const candidate=defaults.find(id=>id&&!selected.value.includes(id)&&!used.has(r.data.find(s=>s.id===id)?.location_key));if(candidate)selected.value[i]=candidate}
 persist()
 }catch(e){if(!disposed)error.value=e.message}finally{refreshing=false;importing.value=false}}
watch(()=>[props.currentRunId,props.runComplete],refresh)
watch(showAdd,async value=>{if(!value||inventory.value)return;try{inventory.value=(await api.post('/api/world/geo-inventory',localStorage.getItem('pdooh-planning-project')?{project_id:localStorage.getItem('pdooh-planning-project')}:{})).data;newFrame.value=inventory.value.frames.find(f=>!f.error)?.key||'';regionId.value=(await api.get('/api/world/regions/latest/'+inventory.value.id)).data?.id}catch(e){error.value=e.message}})
async function uploadInventory(event){const file=event.target.files[0];if(!file)return;adding.value=true;stage.value='读取工作簿…';error.value='';try{const data=new FormData();data.append('file',file);inventory.value=(await api.post('/api/world/geo-inventory',data,{headers:{'Content-Type':'multipart/form-data'}})).data;newFrame.value=inventory.value.frames.find(f=>!f.error)?.key||'';regionId.value=(await api.get('/api/world/regions/latest/'+inventory.value.id)).data?.id}catch(e){error.value=e.message}finally{adding.value=false;event.target.value=''}}
async function addScene(){adding.value=true;error.value='';try{stage.value='查证坐标与周边地图…';const context=(await api.post('/api/world/locate-frame',{inventory_id:inventory.value.id,frame_key:newFrame.value,radius_m:400,region_id:regionId.value})).data;stage.value='生成本地人群画像…';const template=(await api.post('/api/world/local-audiences',{locality:context.locality,group_count:12})).data;stage.value='生成全天人车预览…';const item=(await api.post('/api/world/comparison-scenes/preview',{agent_count:100,total_population:30000,seed:42,day_cycle:{days:1},locality:context.locality,template_id:template.id})).data;if(disposed)return;await refresh();const slot=selected.value.findIndex(id=>!id);select(slot<0?3:slot,item.id);showAdd.value=false}catch(e){error.value=e.message}finally{adding.value=false}}
onMounted(()=>{try{const saved=JSON.parse(localStorage.getItem('pdooh-four-scene-selection')||'null');const slots=Array.isArray(saved)?saved:saved?.selected;if(Array.isArray(slots)&&slots.length===4&&slots.every(x=>typeof x==='string'))selected.value=slots;for(const i of saved?.manual||[])if(Number.isInteger(i)&&i>=0&&i<4)manualSlots.add(i)}catch{}refresh();refreshTimer=setInterval(refresh,15000);last=performance.now();timer=setInterval(()=>{const now=performance.now(),delta=Math.min(now-last,1000)*60*speed.value/30000;last=now;if(synchronized.value){if(playing.value&&ready.value.every((v,i)=>!selected.value[i]||v)){const next=advanceClock(round.value,minute.value,delta,maxRounds.value,loop.value);round.value=next.round;minute.value=next.minute;playing.value=next.playing}}else clocks.value.forEach((c,i)=>{if(c.playing&&selected.value[i]&&ready.value[i])Object.assign(c,advanceClock(c.round,c.minute,delta,catalog.value.find(s=>s.id===selected.value[i])?.rounds||24,loop.value))})},100)})
onBeforeUnmount(()=>{disposed=true;clearInterval(timer);clearInterval(refreshTimer)})
</script>
<style scoped>
.comparison-options{position:relative;font-size:11px}.comparison-options>summary{cursor:pointer;color:#53635a;padding:7px 0}.options-content{position:absolute;right:0;top:32px;z-index:8;width:280px;background:#fff;padding:16px;border:1px solid #dce2e5;border-radius:7px;box-shadow:0 8px 24px #19332714}.options-content>.check{margin-bottom:12px}.options-content p{font-size:10px;color:#627168;line-height:1.7;margin-bottom:0}.options-content .comparison-actions{flex-wrap:wrap}@media(max-width:380px){.options-content{width:245px}}

.scene-comparison{--scene-body-height:clamp(320px,calc(100dvh - 338px),680px);margin:8px 0 16px;background:#fff;border:1px solid #dce2e5;border-radius:10px;padding:10px;color:#191d21}
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
.comparison-grid.focused{grid-template-columns:minmax(0,1fr)}

.comparison-upload{font-size:11px!important}.comparison-upload input{display:block;margin-top:8px;font-size:11px;max-width:220px}
.compare-error{color:#a33d2e;font-size:12px;margin:12px 0}
.add-scene{display:flex;align-items:end;gap:12px;flex-wrap:wrap;background:#f3f7f5;padding:15px;border:1px solid #dce5e0;border-radius:6px;margin:12px 0}
.add-scene label{flex:1;min-width:200px;font-size:11px;color:#30373c}.add-scene select{display:block;width:100%;margin-top:8px}
.add-scene small{width:100%;font-size:11px;line-height:1.8;color:#525b65}
@media(min-width:751px) and (max-width:1099px){.comparison-grid{grid-template-columns:minmax(0,1fr)}}
@media(max-width:750px){.scene-comparison{padding:10px}.comparison-grid{grid-template-columns:minmax(0,1fr)}.scene-comparison h2{font-size:17px}.comparison-controls{gap:8px}.comparison-actions{flex-wrap:wrap}}
</style>
