<template>
 <section class="investment-controls">
  <h2>广告效果与投入策略</h2>
  <label>关联已完成的广告实验<select v-model="options.campaign_id"><option value="">暂不关联 · 态度保持未知</option><option v-for="c in campaigns" :key="c.id" :value="c.id">{{ c.campaign.title }} · {{ c.scenes }} 场景 · {{ c.id.slice(0,8) }}</option></select></label>
  <label>本次投资目标<select v-model="value.objective"><option value="effect">综合广告效果</option><option value="exposure">库存曝光规模</option><option value="profit">基准增量毛利优先</option></select></label>
  <div class="fields"><label>单屏预算上限（0–1）<input v-model.number="value.max_screen_share" type="number" min="0.001" max="1" step="0.05"></label><label>无态度证据探索上限（0–1）<input v-model.number="value.exploration_share" type="number" min="0" max="1" step="0.05"></label></div>
  <p>默认单屏最多15%、探索合计最多20%，均为可调整政策。所有屏幕参与分析；没有直接模拟的屏幕不借用其他地点的好感/兴趣分。约束不允许追加时保留预算。</p>
  <details><summary>重要度权重与阈值</summary><div class="fields"><label v-for="(label,key) in labels" :key="key">{{ label }}<input v-model.number="value.weights[key]" type="number" min="0" max="100"></label><label>高好感 / 高兴趣阈值<input v-model.number="value.threshold" type="number" min="0" max="100"></label></div></details>
  <details><summary>投产比假设 · 可选</summary><p>以下金额使用 {{ options.currency }}。千次订单假设针对非去重曝光，不能用好感/兴趣分代替。未填时回报显示未知。</p>
   <div class="fields"><label>客单价<input v-model.number="value.roi.order_value" type="number" min="0.01"></label><label>毛利率（0–1）<input v-model.number="value.roi.margin" type="number" min="0" max="1" step="0.05"></label><label>增量归因比例（0–1）<input v-model.number="value.roi.incrementality" type="number" min="0" max="1" step="0.05"></label></div>
   <div class="fields"><label v-for="(label,key) in scenarios" :key="key">{{ label }}订单 / 千次曝光<input v-model.number="value.roi.rates[key]" type="number" min="0" max="1000" step="0.01"></label></div>
   <label>假设依据<textarea v-model="value.roi.source" rows="2" placeholder="历史数据周期、对照实验或明确标记为情景假设"></textarea></label>
   <details><summary>单独设置某块屏幕的转化假设</summary><select v-model="overrideId"><option value="">选择屏幕</option><option v-for="f in frames" :key="f.key" :value="f.screen_id">{{ f.fields.ADDRESS_THOROUGHFARE || f.screen_id }}</option></select><template v-if="overrideId"><button type="button" @click="addOverride">建立 / 重置为统一假设</button><button v-if="value.roi.overrides[overrideId]" type="button" @click="delete value.roi.overrides[overrideId]">恢复使用统一假设</button><div v-if="value.roi.overrides[overrideId]" class="fields"><label v-for="(label,key) in scenarios" :key="key">{{ label }}订单 / 千次<input v-model.number="value.roi.overrides[overrideId][key]" type="number" min="0" max="1000" step="0.01"></label></div></template></details>
   <p>ROI 衡量扣广告费后的增量毛利；ROAS 衡量增量收入。统一转化假设下，相同 CPM 屏幕的回报可能相同；不会伪造差异。</p>
  </details>
 </section>
</template>
<script setup>
import {computed,ref} from 'vue'
const options=defineModel({type:Object}),props=defineProps({campaigns:Array,frames:Array})
const value=computed(()=>options.value.investment),overrideId=ref('')
const labels={exposure:'曝光',favorability:'好感',interest:'兴趣',visibility:'可见性',location:'位置',market:'市场匹配',cost:'成本'}
const scenarios={low:'保守',base:'基准',high:'乐观'}
function addOverride(){value.value.roi.overrides[overrideId.value]={...value.value.roi.rates}}
</script>
<style scoped>
.investment-controls{font-size:12px;color:#25372e}h2{font-size:18px}label{display:block;font-size:12px;margin:10px 0}input,select,textarea{width:100%;box-sizing:border-box;padding:8px;border:1px solid #ccd9d0;border-radius:5px;background:white;font:inherit;color:inherit;margin-top:5px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}p{font-size:11px;line-height:1.8;color:#68766e}summary{cursor:pointer;font-size:12px;padding:12px 0}button{background:white;border:1px solid #ccd9d0;border-radius:5px;color:#285b43;padding:7px;font-size:11px;margin:5px 4px 5px 0}
</style>
