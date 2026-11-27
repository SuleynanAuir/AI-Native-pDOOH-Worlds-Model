<template>
 <section class="distribution" aria-label="投资金额与曝光分布">
  <header><h3>投资金额与曝光效率</h3><p>覆盖当前筛选的 {{ rows.length }} 块屏幕，包含所有分页。{{ days ? `投放周期 ${days} 天。` : '投放天数未提供。' }}Impression 为整个投放时段的累计机会，重复经过计次；不是去重人数或实测收入。</p></header>
  <div class="summary">
   <div><span>对应投放资金 {{ currency }}</span><strong>{{ money(totals.spend) }}</strong></div>
   <div><span>投放时段累计 Impression</span><strong>{{ number(totals.impressions) }}</strong></div>
   <div><span>每千次曝光成本 {{ currency }}</span><strong>{{ totals.cpm == null ? '暂无数据' : money(totals.cpm) }}</strong></div>
  </div>
  <article class="joint-chart">
   <h4>单屏投入与累计 Impression · 联合分布</h4>
   <p>上方为投资金额分布，右侧为累计 Impression 分布，共用中央散点图的金额轴和曝光轴。柱长代表屏幕数量；点击圆点查看屏幕依据。</p>
   <div class="chart-scroll"><svg v-if="points.length" viewBox="0 0 1040 490" role="group" aria-label="投资金额与累计曝光联合分布图">
    <text x="80" y="20">投资金额分布 · 屏幕数量</text>
    <g v-for="(b,i) in charts[0].bins" :key="'spend'+i">
     <rect :x="binX(b)" :y="125-b.count/charts[0].max*85" :width="binWidth(b)" :height="b.count/charts[0].max*85" fill="#26745a" tabindex="0" :aria-label="binLabel(b,charts[0])"><title>{{ binLabel(b,charts[0]) }}</title></rect>
     <text :x="binX(b)+binWidth(b)/2" :y="119-b.count/charts[0].max*85" text-anchor="middle">{{ b.count || '' }}</text>
    </g>
    <line x1="80" x2="800" y1="125" y2="125" class="grid"/>
    <text x="80" y="150">累计 Impression</text>
    <text x="835" y="145">曝光分布 · 屏幕数量</text>
    <g v-for="t in [0,.25,.5,.75,1]" :key="t">
     <line x1="80" x2="800" :y1="430-t*260" :y2="430-t*260" class="grid"/>
     <line :x1="80+t*720" :x2="80+t*720" y1="170" y2="430" class="grid"/>
     <text x="69" :y="434-t*260" text-anchor="end">{{ compact(maxExposure*t) }}</text>
     <text :x="80+t*720" y="452" text-anchor="middle">{{ compact(maxSpend*t) }}</text>
    </g>
    <g v-for="(b,i) in charts[1].bins" :key="'exposure'+i">
     <rect x="835" :y="binY(b)" :width="b.count/charts[1].max*145" :height="binHeight(b)" fill="#5c87b0" tabindex="0" :aria-label="binLabel(b,charts[1])"><title>{{ binLabel(b,charts[1]) }}</title></rect>
     <text :x="841+b.count/charts[1].max*145" :y="binY(b)+binHeight(b)/2+4">{{ b.count || '' }}</text>
    </g>
    <circle v-for="p in points" :key="p.row.key" :cx="80+p.spend/maxSpend*720" :cy="430-p.impressions/maxExposure*260" r="5" fill="#26745a" fill-opacity=".65" tabindex="0" role="button" :aria-label="pointLabel(p)" @click="$emit('select',p.row)" @keydown.enter="$emit('select',p.row)" @keydown.space.prevent="$emit('select',p.row)"><title>{{ pointLabel(p) }}</title></circle>
    <text x="440" y="480" text-anchor="middle">整个投放周期的资金 {{ currency }}</text>
   </svg><p v-else class="empty">暂无有效数据</p></div>
   <p>相同投入下圆点越高，曝光效率越高。每千次曝光成本衡量资金效率，收益 ROI 仍以收入情景计算。</p>
  </article>
 </section>
</template>
<script setup>
import { computed } from 'vue'
import { histogram, investmentTotals } from '../utils/investmentDisplay'
const props=defineProps({rows:{type:Array,default:()=>[]},currency:String,days:Number})
defineEmits(['select'])
const totals=computed(()=>investmentTotals(props.rows))
const charts=computed(()=>[
 {key:'price',title:'投资金额分布',unit:`投放资金 ${props.currency}`,color:'#26745a',values:points.value.map(p=>p.spend)},
 {key:'impressions',title:'累计 Impression 分布',unit:'投放时段累计 Impression',color:'#5c87b0',values:points.value.map(p=>p.impressions)}
].map(c=>{const bins=histogram(c.values);return {...c,bins,max:Math.max(2,...bins.map(b=>b.count))}}))
const points=computed(()=>props.rows.filter(r=>r.recommended_amount!=null&&r.recommended_exposures!=null&&Number.isFinite(Number(r.recommended_amount))&&Number.isFinite(Number(r.recommended_exposures))&&r.recommended_amount>=0&&r.recommended_exposures>=0).map(row=>({row,spend:Number(row.recommended_amount),impressions:Number(row.recommended_exposures)})))
const maxSpend=computed(()=>Math.max(1,...points.value.map(p=>p.spend))),maxExposure=computed(()=>Math.max(1,...points.value.map(p=>p.impressions)))
const binX=b=>Math.min(792,80+b.low/maxSpend.value*720)
const binWidth=b=>Math.max(3,(b.high-b.low)/maxSpend.value*720-3)
const binY=b=>Math.min(422,430-b.high/maxExposure.value*260)
const binHeight=b=>Math.max(3,(b.high-b.low)/maxExposure.value*260-3)
const money=n=>Number(n).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
const number=n=>Math.round(n).toLocaleString('zh-CN')
const compact=n=>new Intl.NumberFormat('zh-CN',{notation:'compact',maximumFractionDigits:1}).format(n)
const binLabel=(b,c)=>`${c.unit} ${money(b.low)} 至 ${money(b.high)}，${b.count} 块屏幕；区间左闭右开，最后一组包含上界`
const pointLabel=p=>`${p.row.address||p.row.screen_id}；投放资金 ${money(p.spend)} ${props.currency}；累计 Impression ${number(p.impressions)}；每千次曝光成本 ${p.impressions>0?money(p.spend*1000/p.impressions):'未知'} ${props.currency}`
</script>
<style scoped>
.distribution{margin:20px 0;padding:20px;background:#f7faf8;border:1px solid #dce7df;border-radius:12px}h3{margin:0;font-size:17px}h4{margin:0;font-size:14px}p{font-size:12px;color:#617267;line-height:1.8;margin:8px 0}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}.summary>div{background:white;padding:14px;border-radius:8px}.summary span{display:block;font-size:11px;color:#617267}.summary strong{display:block;font-size:22px;margin-top:8px}.chart-scroll{overflow-x:auto}.joint-chart svg{min-width:650px;max-width:1050px;margin:0 auto}article{background:white;padding:16px;border:1px solid #e0e9e3;border-radius:8px;min-width:0}.efficiency{margin-top:16px}svg{display:block;width:100%;overflow:visible}svg text{fill:#5b7063;font-size:11px}.grid{stroke:#e3ebe6;stroke-width:1}rect:focus,circle:focus{outline:2px solid #123e2c;stroke:#123e2c;stroke-width:2}circle{cursor:pointer}.empty{padding:50px;text-align:center}@media(max-width:760px){.summary{grid-template-columns:1fr}.distribution{padding:12px}.summary strong{font-size:20px}}
</style>
