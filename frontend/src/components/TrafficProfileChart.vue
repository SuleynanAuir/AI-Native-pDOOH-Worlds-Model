<template>
<section class="traffic-chart" aria-label="核心区域24小时车流可视化">
  <header><strong>全天车流对比</strong><span>{{ ready.length }} / {{ regions.length }} 个区域已生成 · {{ hourLabel(hour) }}</span></header>
  <p v-if="!ready.length">尚无完整 24 小时数据。估算后显示曲线与区域热力表，未知值不会画成零。</p>
  <template v-else>
    <div class="legend"><label v-for="(r,i) in compared" :key="r.id"><i :style="{background:colors[i]}"/>{{ short(r.name) }}</label></div>
    <svg viewBox="0 0 960 280" role="img" aria-label="区域24小时车流曲线，辆每小时">
      <title>当地普通工作日24小时车流模型估算；阴影为当前区域区间，非统计置信区间</title>
      <g v-for="n in 5" :key="n"><line x1="65" x2="930" :y1="y(max*(n-1)/4)" :y2="y(max*(n-1)/4)" stroke="#e3e9e6"/><text x="54" :y="y(max*(n-1)/4)+4" text-anchor="end">{{ Math.round(max*(n-1)/4).toLocaleString() }}</text></g>
      <path v-for="(path,i) in bands(selectedEstimate?.hourly||[])" :key="'band'+i" :d="path" fill="#188879" opacity=".1"/>
      <g v-for="(r,i) in compared" :key="r.id"><path v-for="(path,j) in paths(estimates[r.representative_id].hourly)" :key="j" :d="path" fill="none" :stroke="colors[i]" :stroke-width="r.representative_id===selectedId?3:2"/><circle v-for="v in estimates[r.representative_id].hourly.filter(v=>v.vehicles_per_hour!=null)" :key="v.hour" :cx="x(v.hour)" :cy="y(v.vehicles_per_hour)" r="3" :fill="colors[i]"><title>{{ r.name }} · {{ hourLabel(v.hour) }} · {{ v.vehicles_per_hour }} 辆 · 区间 {{ v.low }}–{{ v.high }}</title></circle></g>
      <line :x1="x(hour)" :x2="x(hour)" y1="20" y2="235" stroke="#7d8f89" stroke-dasharray="4 4"/>
      <text v-for="h in [0,3,6,9,12,15,18,21,23]" :key="h" :x="x(h)" y="258" text-anchor="middle">{{ hourLabel(h) }}</text><text x="65" y="12">辆 / 小时</text>
    </svg>
    <label class="hour-control">查看小时 <input aria-label="查看车流小时" type="range" min="0" max="23" step="1" v-model.number="hour"><b>{{ hourLabel(hour) }}</b></label>
    <div class="metrics" v-if="selectedEstimate"><span>当前区域 {{ valueAt(selectedEstimate,hour) }} 辆/小时</span><span>高峰 {{ peak(selectedEstimate) }}</span><span>全天进入次数 {{ daily(selectedEstimate) }}</span></div>
    <p>默认对比当前区域及最多三个其他已估算区域。阴影为当前区域的模型估算范围，非统计置信区间；灰色表示未知。</p>
  </template>
  <div class="heat-scroll"><table class="heatmap"><caption>各核心区域全天车流 · 点击区域切换曲线</caption><thead><tr><th>核心区域</th><th v-for="h in 24" :key="h">{{ h-1 }}</th></tr></thead><tbody><tr v-for="r in regions" :key="r.id" :class="{selected:r.representative_id===selectedId}"><th><button @click="$emit('select',r.representative_id)" :title="r.name">{{ short(r.name) }}</button></th><td v-for="h in 24" :key="h" :style="{background:heat(estimates[r.representative_id],h-1)}" :title="`${r.name} · ${hourLabel(h-1)} · ${valueAt(estimates[r.representative_id],h-1)} 辆/小时`">{{ valueAt(estimates[r.representative_id],h-1)==='未知'?'—':'' }}</td></tr></tbody></table></div>
  <small>浅色 → 深色：低车流 → 高车流，同一色标比较所有区域；路网与可用历史计数约束下的模型推测。回放每小时最多显示 3000 个带权重的车辆样本，保留完整预测车流，非实测。</small>
  <details v-if="selectedEstimate"><summary>查看当前区域的 24 个数据</summary><table class="values"><thead><tr><th>当地小时</th><th>估算辆次</th><th>估算区间</th></tr></thead><tbody><tr v-for="v in selectedEstimate.hourly" :key="v.hour"><td>{{ hourLabel(v.hour) }}</td><td>{{ v.vehicles_per_hour??'未知' }}</td><td>{{ v.low??'未知' }} – {{ v.high??'未知' }}</td></tr></tbody></table></details>
</section>
</template>
<script setup>
import {computed,ref} from 'vue'
const props=defineProps({regions:{type:Array,default:()=>[]},estimates:{type:Object,default:()=>({})},selectedId:String})
defineEmits(['select'])
const hour=ref(8),colors=['#188879','#367ec7','#b46a32','#9465ba']
const valid=e=>e?.schema_version===2&&e.hourly?.length===24
const ready=computed(()=>props.regions.filter(r=>valid(props.estimates[r.representative_id])))
const selectedEstimate=computed(()=>valid(props.estimates[props.selectedId])?props.estimates[props.selectedId]:null)
const compared=computed(()=>[...ready.value.filter(r=>r.representative_id===props.selectedId),...ready.value.filter(r=>r.representative_id!==props.selectedId)].slice(0,4))
const max=computed(()=>Math.max(1,...compared.value.flatMap(r=>props.estimates[r.representative_id].hourly.map(v=>v.high??0))))
const heatMax=computed(()=>Math.max(1,...ready.value.flatMap(r=>props.estimates[r.representative_id].hourly.map(v=>v.vehicles_per_hour??0))))
const x=h=>65+h*865/23,y=v=>235-v/max.value*210,hourLabel=h=>String(h).padStart(2,'0')+':00',short=s=>s.length>27?s.slice(0,27)+'…':s
const at=(e,h)=>valid(e)?e.hourly.find(v=>v.hour===h):null
const valueAt=(e,h)=>at(e,h)?.vehicles_per_hour??'未知'
function segments(rows){const out=[];let current=[];for(const v of rows){if(v.vehicles_per_hour==null){if(current.length)out.push(current);current=[]}else current.push(v)}if(current.length)out.push(current);return out}
const paths=rows=>segments(rows).map(seg=>seg.map((v,i)=>`${i?'L':'M'}${x(v.hour)},${y(v.vehicles_per_hour)}`).join(' '))
const bands=rows=>segments(rows).map(seg=>seg.map((v,i)=>`${i?'L':'M'}${x(v.hour)},${y(v.high)}`).join(' ')+' '+[...seg].reverse().map(v=>`L${x(v.hour)},${y(v.low)}`).join(' ')+' Z')
function heat(e,h){const n=at(e,h)?.vehicles_per_hour;return n==null?'#edf0ef':`hsl(166 40% ${96-60*n/heatMax.value}%)`}
function peak(e){const known=e.hourly.filter(v=>v.vehicles_per_hour!=null);if(!known.length)return '未知';const p=known.reduce((a,b)=>a.vehicles_per_hour>=b.vehicles_per_hour?a:b);return `${hourLabel(p.hour)} · ${p.vehicles_per_hour} 辆${known.length<24?'（已知小时）':''}`}
function daily(e){return e.hourly.some(v=>v.vehicles_per_hour==null)?'未知（存在缺失小时）':e.hourly.reduce((n,v)=>n+v.vehicles_per_hour,0).toLocaleString()}
</script>
<style scoped>
.traffic-chart{margin:20px 0;padding:18px;border:1px solid #dce5e0;border-radius:8px;background:#fbfdfc;color:#263b32}header,.legend,.metrics,.hour-control{display:flex;gap:18px;align-items:center;flex-wrap:wrap}header{justify-content:space-between}header span,p,small{font-size:12px;color:#61736a;line-height:1.8}.legend{margin-top:16px;font-size:11px}.legend label{display:flex;align-items:center;gap:6px}.legend i{width:10px;height:10px;border-radius:50%}svg{display:block;width:100%;min-height:180px;margin:18px 0 0}svg text{fill:#64766c;font-size:11px}.hour-control{font-size:12px}.hour-control input{flex:1;accent-color:#188879;min-width:150px}.metrics{margin:14px 0;font-size:13px}.heat-scroll{overflow:auto;max-height:320px;margin:15px 0}.heatmap{width:100%;min-width:760px;border-spacing:3px;font-size:10px;table-layout:fixed}.heatmap caption{text-align:left;padding-bottom:10px;font-size:12px}.heatmap th:first-child{width:175px;text-align:left}.heatmap thead{position:sticky;top:0;background:#fbfdfc}.heatmap td{text-align:center;border-radius:2px;height:17px;color:#8c9a93}.heatmap button{border:0;background:none;text-align:left;font:inherit;color:#34594b;cursor:pointer;padding:3px;max-width:100%;overflow:hidden;white-space:nowrap}.heatmap .selected th{border-left:3px solid #188879}.values{width:100%;font-size:12px;border-collapse:collapse}.values th,.values td{text-align:left;padding:7px;border-bottom:1px solid #e2e9e5}summary{cursor:pointer;font-size:12px;margin-top:15px}
</style>
