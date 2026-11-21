<template>
 <ModalWindow v-model="opened" title="量化选屏对比" subtitle="相同广告下的完整周期模拟结果；不是投资回报预测">
  <p class="comparison-method">高兴趣阈值统一为 ≥60/100；已评占比的分母包含行人及车辆载客机会，未知车内态度不补为零分；覆盖率不表示模型可信度。小时均值便于对照不同周期，但时段、地点与人群假设仍需核查。</p>
  <div class="decision-comparison-table"><table><thead><tr><th>场景</th><th>周期</th><th>模拟曝光</th><th>行人占比</th><th>已评占比</th><th>兴趣 /100</th><th>高兴趣机会 /小时</th><th>最大机会时段</th></tr></thead><tbody><tr v-for="(row,i) in rows" :key="i"><template v-if="row"><td><button @click="openScene(i)">{{ row.title.replace(/ 周边.*$/,'') }}</button></td><td>{{ row.durationHours }}h</td><td>{{ num(row.total) }}</td><td>{{ pct(row.pedestrianShare) }}</td><td>{{ pct(row.coverage) }}</td><td>{{ row.interest==null?'未知':row.interest.toFixed(1) }}</td><td>{{ row.rated&&row.durationHours?num(row.high/row.durationHours):'未知' }}</td><td>{{ row.peak[0]?.name||'—' }}</td></template><td v-else colspan="8">场景 {{ i+1 }} 尚未载入</td></tr></tbody></table></div>
  <p class="comparison-method">曝光多不等于适合目标人群；优先同时核对评分覆盖、目标群体和通行任务。点击场景可打开该屏幕的详细依据及报价测算；不同场景的机会不能相加当作独立覆盖人数。</p>
 </ModalWindow>
</template>
<script setup>
import ModalWindow from './ModalWindow.vue'
const opened=defineModel({type:Boolean}),props=defineProps({rows:Array}),emit=defineEmits(['scene'])
const num=n=>Math.round(n).toLocaleString('zh-CN'),pct=n=>n==null?'—':n.toFixed(1)+'%'
function openScene(i){opened.value=false;emit('scene',i)}
</script>
<style scoped>
.comparison-method{font-size:12px;line-height:1.9;color:#586e60;margin:8px 0 18px}.decision-comparison-table{overflow:auto}.decision-comparison-table table{width:100%;border-collapse:collapse;font-size:12px}.decision-comparison-table th,.decision-comparison-table td{text-align:left;padding:12px 8px;border-bottom:1px solid #e0e8e2;white-space:nowrap}.decision-comparison-table th{background:#f4f8f5;font-weight:500}.decision-comparison-table button{background:none;border:0;color:#176b4e;font:inherit;cursor:pointer;text-align:left;max-width:230px;white-space:normal;padding:0}
</style>
