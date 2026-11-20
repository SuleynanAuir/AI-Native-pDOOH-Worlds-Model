<template>
  <main>
    <header><strong>VIOOH / AUDIENCE LAB</strong><router-link to="/legacy">旧版项目</router-link></header>
    <section class="intro"><small>AI-NATIVE pDOOH · 代表性群体模拟</small><h1>从路人的视角，看见屏幕。</h1><p>比较通勤路人、购物消费者、候车观众与乘车经过者的观看机会。调整现场条件，观察各群体的反应差异。</p></section>
    <div class="layout">
      <section class="panel">
        <h2>01 / 屏幕现场</h2><p>初始数据为演示假设。请根据现场照片填写；尺寸单位为米，不是像素。</p>
        <article v-for="(s, i) in screens" :key="i">
          <div class="row"><label>屏幕 ID<input v-model="s.id" required></label><button v-if="screens.length > 1" @click="screens.splice(i, 1)">移除</button></div>
          <div class="fields"><label v-for="f in screenFields" :key="f.key">{{ f.label }}<input type="number" v-model.number="s[f.key]" :min="f.min" :max="f.max" :step="f.step"></label></div>
        </article>
        <button @click="addScreen">＋ 添加屏幕</button>
        <h2>02 / 群体与情景</h2><p>占比会自动归一化。注意力与兴趣为 0–1 参数；群体标签本身不决定反应。</p>
        <article v-for="g in groups" :key="g.id">
          <div class="row"><label>群体名称<input v-model="g.name"></label><button v-if="groups.length > 1" @click="groups = groups.filter(item => item.id !== g.id)">移除</button></div>
          <div class="fields"><label>移动方式<select v-model="g.mobility"><option value="walking">步行</option><option value="waiting">候车 / 停留</option><option value="vehicle">乘车经过</option></select></label><label>占比<input type="number" v-model.number="g.share" min="0" max="1" step="0.05"></label><label>观看机会（秒）<input type="number" v-model.number="g.dwell_seconds" min="0" max="600"></label><label>注意力<input type="number" v-model.number="g.attention" min="0" max="1" step="0.05"></label><label v-if="creative">条件兴趣概率<input type="number" v-model.number="g.interest" min="0" max="1" step="0.05"></label></div>
        </article>
        <button @click="addGroup">＋ 添加消费者群体</button>
        <label>资料与参数依据<textarea v-model="evidence" placeholder="填写国家/区域文献、调研来源及参数依据；留空则按情景假设处理。" /></label>
        <label class="check"><input type="checkbox" v-model="creative">已提供创意依据，启用假设兴趣反应</label>
        <div class="fields"><label>合成路人数<input type="number" v-model.number="population" min="1" max="10000"></label><label>随机种子<input type="number" v-model.number="seed" min="0" max="2147483647"></label></div>
        <button class="primary" :disabled="busy" @click="run">{{ busy ? '模拟中…' : '运行路人 × 屏幕模拟 →' }}</button><p v-if="error" role="alert" class="error">{{ error }}</p>
      </section>
      <section class="panel results" aria-live="polite">
        <h2>03 / 观看机会与群体反应</h2>
        <p v-if="!result">运行后，将显示各屏幕的注意率、完整观看机会及群体反应。相同输入与种子可复现结果。</p>
        <template v-else>
          <p>以下为上次运行快照 · {{ result.population }} 位合成路人 · 种子 {{ result.seed }}</p>
          <article v-for="s in result.screens" :key="s.screen_id"><h3>{{ s.screen_id }}</h3><div class="metrics"><div><b>{{ percent(s.notice_rate) }}</b><span>注意到屏幕</span></div><div><b>{{ percent(s.full_view_rate) }}</b><span>完整观看机会</span></div></div>
            <div class="table-wrap"><table><thead><tr><th>群体</th><th>经过</th><th>未注意</th><th>短暂注视</th><th>持续观看</th><th>兴趣*</th></tr></thead><tbody><tr v-for="g in s.groups" :key="g.group_id"><td>{{ g.name }}</td><td>{{ g.counts.encounters || 0 }}</td><td>{{ g.counts.ignored || 0 }}</td><td>{{ g.counts.glanced || 0 }}</td><td>{{ g.counts.watched || 0 }}</td><td>{{ result.inputs.creative_supplied ? (g.counts.interested || 0) : '—' }}</td></tr></tbody></table></div>
          </article>
          <p>* 反应列互斥；兴趣包含完整观看机会，不代表购买或转化。</p>
          <details><summary>相遇记录（最多 200 条）</summary><div class="events"><p v-for="(e, i) in result.examples" :key="i">#{{ e.agent_id }} · {{ e.group_id }} → {{ e.screen_id }}<br><strong>{{ labels[e.reaction] }}</strong> · {{ e.reason }}</p></div></details>
          <h3>模型假设与依据</h3><ul><li v-for="a in result.assumptions" :key="a">{{ a }}</li></ul><p>{{ result.inputs.evidence }}</p>
          <button @click="download">导出结果与参数 JSON</button>
        </template>
      </section>
    </div>
  </main>
</template>
<script setup>
import { ref } from 'vue'
import api from '../api'
const screens = ref([{ id: 'DEMO-01', visibility: 0.8, obstruction: 0.1, viewing_distance: 12, physical_height: 2, slot_seconds: 10 }])
const screenFields = [{key:'visibility',label:'自然视线可见性',min:0,max:1,step:0.05},{key:'obstruction',label:'遮挡比例',min:0,max:1,step:0.05},{key:'viewing_distance',label:'观看距离（米）',min:0.1,max:1000,step:0.1},{key:'physical_height',label:'屏幕物理高度（米）',min:0.01,max:100,step:0.1},{key:'slot_seconds',label:'展示时长（秒）',min:0.1,max:600,step:0.1}]
const groups = ref([
  {id:'commuter',name:'通勤路人',share:0.4,mobility:'walking',dwell_seconds:4,attention:0.35,interest:0.3},
  {id:'shopper',name:'购物消费者',share:0.3,mobility:'walking',dwell_seconds:15,attention:0.65,interest:0.6},
  {id:'waiting',name:'候车观众',share:0.2,mobility:'waiting',dwell_seconds:40,attention:0.7,interest:0.4},
  {id:'passenger',name:'乘车经过者',share:0.1,mobility:'vehicle',dwell_seconds:2,attention:0.25,interest:0.2}
])
const population = ref(1000), seed = ref(42), creative = ref(false), evidence = ref(''), result = ref(null), busy = ref(false), error = ref('')
const labels = {ignored:'未注意',glanced:'短暂注视',watched:'持续观看',interested:'产生兴趣（假设）'}
let nextId = 2, nextGroupId = 1
function addGroup() { groups.value.push({id:`custom-${nextGroupId++}`,name:'自定义消费者',share:0.1,mobility:'walking',dwell_seconds:10,attention:0.5,interest:0.3}) }
function addScreen() { screens.value.push({...screens.value[0], id:`DEMO-${String(nextId++).padStart(2,'0')}`}) }
const percent = n => `${(n * 100).toFixed(1)}%`
async function run() {
  busy.value = true; error.value = ''
  try { const response = await api.post('/api/audience/run', {screens:screens.value, groups:groups.value, population:population.value, seed:seed.value, creative_supplied:creative.value, evidence:evidence.value || '未提供资料，参数为情景假设'}); result.value = response.data }
  catch (e) { error.value = e.message || '模拟失败，请重试' }
  finally { busy.value = false }
}
function download() {
  const url = URL.createObjectURL(new Blob([JSON.stringify(result.value, null, 2)], {type:'application/json'}))
  const a = document.createElement('a'); a.href = url; a.download = 'audience-simulation.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
<style scoped>
main{background:#f4f5f0;min-height:100vh;padding:28px 5%;color:#183c33;font-family:Arial,sans-serif}header,.row{display:flex;justify-content:space-between;align-items:center;gap:16px}header{border-bottom:1px solid #ccd5cd;padding-bottom:24px}a{color:inherit}.intro{max-width:800px;margin:50px 0 34px}small{letter-spacing:2px}h1{font-size:clamp(28px,4vw,48px);margin:16px 0}p{line-height:1.7;color:#5b6c63;margin:12px 0}.layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:24px;align-items:start}.panel{background:white;border:1px solid #dce2d8;border-radius:16px;padding:24px;min-width:0}h2{font-size:18px;margin:10px 0 20px}h3{margin:16px 0}article{padding:16px;background:#f7f9f5;border-radius:10px;margin:16px 0}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:12px 0}label{display:block;font-size:13px;color:#52675c}input,select,textarea{display:block;width:100%;padding:10px;border:1px solid #cdd6cf;border-radius:6px;margin-top:6px;background:white;font:inherit;color:#183c33}textarea{min-height:86px}.check{display:flex;align-items:center;gap:10px;margin:18px 0}.check input{width:auto;margin:0}button{border:1px solid #b5c5b9;background:white;color:#183c33;border-radius:8px;padding:10px 14px;cursor:pointer}.primary{width:100%;background:#194f3e;color:white;margin-top:16px}button:disabled{opacity:.5;cursor:wait}.metrics{display:flex;gap:40px;margin:24px 0}.metrics b{display:block;font-size:32px}.metrics span{font-size:12px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}td,th{text-align:left;padding:12px 8px;border-bottom:1px solid #dce2d8}li{margin:10px 0;line-height:1.6;font-size:13px}ul{padding-left:18px}.events{max-height:350px;overflow:auto;font-size:12px}summary{cursor:pointer;padding:16px 0}.error{color:#ad342e}@media(max-width:850px){.layout{grid-template-columns:1fr}main{padding:20px}.panel{padding:18px}}
</style>
