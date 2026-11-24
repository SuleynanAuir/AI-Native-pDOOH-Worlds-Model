<template>
<section class="ad-setup panel" aria-label="第二步 广告设置">
  <h2>第二步 · 广告设置</h2><p>设置广告内容，再进入人群模拟。物料与车流估算按本项目保存。</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="progress" role="status">{{ progress }}</p>
  <div class="fields"><label>品牌<input v-model="draft.brand" aria-label="广告品牌"></label><label>广告标题<input v-model="draft.title" aria-label="广告标题"></label></div>
  <div class="creative"><div><img v-if="asset" :src="assetUrl" alt="已上传的广告物料"><div v-else class="placeholder">{{ draft.title }}<p>{{ draft.message }}</p></div><label>导入广告物料图片<input type="file" accept="image/png,image/jpeg,image/webp" :disabled="busy" @change="upload"></label><small>PNG / JPG / WebP，最大 8 MB</small><p v-if="asset">{{ asset.name }} · {{ asset.status==='analyzed'?'已提取物料内容':'已上传' }}</p><button v-if="asset" :disabled="busy" @click="analyze">{{ asset.status==='analyzed'?'重新识别图片':'识别物料内容' }}</button></div>
    <div><label>播放内容 / 诉求<textarea v-model="draft.message" aria-label="广告播放内容" rows="5" maxlength="1000" /></label><p v-if="asset?.description" class="description">图片观察：{{ asset.description }}</p><details><summary>广告检索资料 · 可修改</summary><label>检索主题<input v-model="draft.topic"></label><label>官方资料 / 新闻页<input v-model="draft.source_url" type="url"></label></details></div></div>
  <h3>核心区域 · 24 小时车流</h3><p>按屏幕经纬度，将中心周围 400 米内的屏幕归为一个核心区域。{{ regions.length }} 个区域覆盖 {{ validFrames.length }} 块屏幕；每个区域独立预测当地普通工作日 00–23 时的车流。区域范围可能重叠，不可相加当作城市去重车流。</p>
  <p v-if="flow!==''">当前已启用人工车流覆盖：{{ flow }} 辆/小时基准。清空下方人工覆盖值后，回放才会使用区域24小时预测。</p>
  <label>核心区域<select v-model="screenId" aria-label="车流估算地点"><option v-for="r in regions" :key="r.id" :value="r.representative_id">{{ r.name }} · {{ r.screen_ids.length }} 块屏幕</option></select></label>
  <div class="buttons"><button :disabled="busy||!screenId" @click="estimate([screenId])">按路网与计数重新估算</button><button :disabled="busy||!regions.length" @click="estimate(regions.filter(r=>!isHourly(estimates[r.representative_id])).map(r=>r.representative_id))">补齐全部区域（{{ regions.filter(r=>!isHourly(estimates[r.representative_id])).length }} 个待估算）</button></div>
  <TrafficProfileChart :regions="regions" :estimates="estimates" :selected-id="screenId" @select="screenId=$event" />
  <p v-if="current"><strong>{{ isHourly(current)?'路网与历史计数约束的 24 小时推测 · 非实测':'旧版估算缺少道路计数依据，请重新估算' }}</strong><br>{{ current.reason }}<br><small>{{ current.uncertainties?.join('；') }} · {{ current.model }}</small></p>
  <details v-if="current?.evidence"><summary>估算依据 · {{ current.evidence.roads.length }} 条入口道路 · {{ current.evidence.references.length }} 条历史计数</summary><p>{{ current.formula }}</p><p>地图查询：{{ current.evidence.map_queried_at }} · {{ current.evidence.attribution }}</p><div v-for="r in current.evidence.references" :key="r.id"><a :href="r.source_url" target="_blank" rel="noopener">{{ r.year }} · {{ r.location }} · {{ r.direction }} · {{ r.daily_vehicles.toLocaleString() }} 辆/日</a><p>{{ r.limitation }}</p></div><p v-if="!current.evidence.references.length">暂无匹配的官方计数，仅依据路网推测，尚未实测校准。</p><table><thead><tr><th>道路</th><th>驶入入口</th><th>模型日进入次数</th></tr></thead><tbody><tr v-for="r in current.evidence.roads" :key="r.id"><td>{{ r.name }}</td><td>{{ r.incoming_portals }}</td><td>{{ current.road_estimates.find(x=>x.road_id===r.id)?.daily_entries ?? '未知' }}</td></tr></tbody></table><p v-for="note in current.evidence.limitations" :key="note">{{ note }}</p></details>
  <details><summary>人工覆盖车流 · 可选</summary><label>统一区域基准车流（辆/小时）<input v-model="flow" type="number" min="0" max="3000" step="1" placeholder="留空使用各地点估算" aria-label="统一区域基准车流"></label><p>填写后覆盖本项目各地点的模型估算；未估算或未知小时的回放会明确标为默认情景。逐小时曲线不再重复乘高峰/节日系数，普通工作日曲线逐日重复。</p></details>
  <div class="buttons footer"><button :disabled="busy" @click="$emit('back')">← 返回数据与设置</button><button class="primary" :disabled="busy" @click="save">保存广告，进入第三步 →</button></div>
</section>
</template>
<script setup>
import {ref,computed,onMounted} from 'vue'
import api from '../api'
import TrafficProfileChart from './TrafficProfileChart.vue'
const props=defineProps({project:Object}),emit=defineEmits(['back','saved'])
const draft=ref({brand:'Nike',title:'NIKE RUNNING',message:'Everyday miles. Your own pace. 日常跑步与舒适运动。',topic:'running everyday comfort community',source_url:'https://about.nike.com/en/newsroom'})
const regions=ref([])
const isHourly=value=>value?.method_version>=3&&value.hourly?.length===24
const asset=ref(null),estimates=ref({}),flow=ref(''),screenId=ref(''),busy=ref(false),error=ref(''),progress=ref('')
const validFrames=computed(()=>props.project.frames.filter(f=>Number.isFinite(f.lat)&&Number.isFinite(f.lon)&&f.screen_id))
const current=computed(()=>estimates.value[screenId.value])
const base=`/api/planning/${props.project.id}`
const assetUrl=computed(()=>asset.value?new URL(asset.value.url,api.defaults.baseURL||window.location.origin).href:'')
async function run(fn){busy.value=true;error.value='';try{await fn()}catch(e){error.value=e.message}finally{busy.value=false;progress.value=''}}
async function analyzeImage(){progress.value='正在识别广告物料…';asset.value=(await api.post(base+'/creative/analyze')).data}
async function analyze(){await run(analyzeImage)}
async function upload(event){const file=event.target.files[0];if(!file)return;await run(async()=>{const form=new FormData();form.append('image',file);asset.value=(await api.post(base+'/creative',form,{headers:{'Content-Type':'multipart/form-data'}})).data;await analyzeImage()});event.target.value=''}
async function estimate(ids){await run(async()=>{for(let i=0;i<ids.length;i+=1){progress.value=`正在估算区域24小时车流 ${i+1}–${Math.min(i+1,ids.length)} / ${ids.length}…`;Object.assign(estimates.value,(await api.post(base+'/traffic-estimate',{screen_ids:ids.slice(i,i+1)})).data)}})}
async function save(){await run(async()=>{await api.post(base+'/ad-setup',{campaign:draft.value,vehicles_per_hour:flow.value===''?null:Number(flow.value)});const linked=(await api.get(base+'/coverage')).data.campaign_id;localStorage.setItem('pdooh-campaign-experiment-'+props.project.id,linked||'none');localStorage.removeItem('pdooh-campaign-pending-'+props.project.id);emit('saved',linked)})}
onMounted(async()=>{await run(async()=>{const value=(await api.get(base+'/ad-setup')).data;if(value.campaign)draft.value=value.campaign;asset.value=value.creative||null;estimates.value=value.traffic_estimates||{};flow.value=value.vehicles_per_hour??'';regions.value=value.core_regions||[];screenId.value=regions.value[0]?.representative_id||''});if(!error.value&&screenId.value&&!isHourly(current.value))await estimate([screenId.value])})
</script>
<style scoped>
.ad-setup{background:white;border:1px solid #dbe2d7;border-radius:12px;padding:24px;color:#193c31}.fields,.creative{display:grid;grid-template-columns:1fr 1fr;gap:24px}.creative{margin:20px 0}.creative img{width:100%;max-height:300px;object-fit:contain;background:#f3f5ef;border-radius:8px}.placeholder{padding:25px;background:#193c31;color:white;border-radius:8px;font-size:24px}.placeholder p{color:white}label{display:block;font-size:13px;margin:12px 0}input,textarea,select{box-sizing:border-box;width:100%;padding:10px;margin-top:7px;border:1px solid #c9d5ca;border-radius:6px;font:inherit;color:inherit;background:white}p,small{font-size:12px;line-height:1.8;color:#627267}.buttons{display:flex;gap:12px;flex-wrap:wrap}button{padding:10px 16px;border:1px solid #b8cbbd;border-radius:6px;background:white;color:#194f3e;cursor:pointer}button:disabled{opacity:.5;cursor:wait}.primary{background:#205b40;color:white}.footer{justify-content:space-between;margin-top:24px}.error{color:#a53535}.description{max-height:180px;overflow:auto}summary{cursor:pointer;font-size:13px;padding:12px 0}@media(max-width:700px){.fields,.creative{grid-template-columns:1fr}}
</style>
