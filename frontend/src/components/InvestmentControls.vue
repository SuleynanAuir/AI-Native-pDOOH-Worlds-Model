<template>
 <section class="investment-controls">
  <h2>广告效果与投入策略</h2><label>分配方式<select v-model="value.complete_report"><option :value="true">自适应全屏试投 · 不固定投入比例</option><option :value="false">严格SOT步长 · 保留探索上限</option></select></label>
  <label>本次投资目标<select v-model="value.objective"><option value="effect">综合广告效果</option><option value="exposure">库存曝光规模</option><option value="profit">基准增量毛利优先</option></select></label>
  <details><summary>预算分配与评分参数 · 默认即可</summary><label>追加投资最低重要度<input v-model.number="value.minimum_importance" type="number" min="0" max="100" placeholder="40"></label><div class="fields"><label>单屏预算上限（0–1）<input v-model.number="value.max_screen_share" type="number" min="0.001" max="1" step="0.05"></label><label>旧方案探索上限（全屏试投不适用）<input v-model.number="value.exploration_share" type="number" min="0" max="1" step="0.05"></label></div>
  <p>默认单屏最多15%；旧方案探索合计最多20%，全屏试投不设此探索上限。所有屏幕参与分析；没有直接模拟的屏幕不借用其他地点的好感/兴趣分。约束不允许追加时保留预算。</p>
  <details><summary>重要度权重与阈值</summary><div class="fields"><label v-for="(label,key) in labels" :key="key">{{ label }}<input v-model.number="value.weights[key]" type="number" min="0" max="100"></label><label>高好感 / 高兴趣阈值<input v-model.number="value.threshold" type="number" min="0" max="100"></label></div></details>
  </details><details><summary>投产比与逐屏历史校准</summary>
   <p>校准优先使用同周期、同曝光口径的投放组和可比对照组。不会根据好感/兴趣制造转化率差异。</p>
   <label>导入逐屏校准 CSV<input type="file" accept=".csv" @change="uploadCalibration"></label><button type="button" @click="downloadTemplate">下载CSV字段模板</button><button type="button" v-if="Object.keys(value.roi.calibration||{}).length" @click="value.roi.calibration={}">清除校准数据</button>
   <p role="status">{{ calibrationMessage || `已导入 ${Object.keys(value.roi.calibration||{}).length} 块屏幕的历史数据` }}</p>
   <small>客单价和额外执行成本使用 {{ options.currency }}；周期和数据来源必填。额外执行成本会从总预算预留，进入ROI分母。</small><p>以下金额使用 {{ options.currency }}。千次订单假设针对非去重曝光，不能用好感/兴趣分代替。全屏试投未填项采用明确标记的演示值：客单价100、毛利45%、增量归因25%、千次订单0.05 / 0.1 / 0.2；不代表真实收益。</p>
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
import {parseCalibrationCSV} from '../utils/roiCalibration'
const options=defineModel({type:Object}),props=defineProps({campaigns:Array,frames:Array})
const value=computed(()=>options.value.investment),overrideId=ref('')
const labels={exposure:'曝光',favorability:'好感',interest:'兴趣',visibility:'可见性',location:'位置',market:'市场匹配',cost:'成本'}
const calibrationMessage=ref('')
async function uploadCalibration(e){const file=e.target.files[0];if(!file)return;try{if(file.size>2000000)throw Error('CSV最大2MB');const rows=parseCalibrationCSV(await file.text(),options.value.currency);const ids=new Set(props.frames.map(f=>f.screen_id));if(Object.keys(rows).some(id=>!ids.has(id)))throw Error('CSV包含不在当前库存中的屏幕ID');value.value.roi.calibration=rows;calibrationMessage.value=`已导入 ${Object.keys(rows).length} 块屏幕的历史数据，请重新生成报告`}catch(err){calibrationMessage.value=err.message}finally{e.target.value=''}}
function downloadTemplate(){const blob=new Blob(['screen_id,test_exposures,test_orders,control_exposures,control_orders,order_value,margin,extra_cost,currency,period,source\n'],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='screen-roi-calibration.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
const scenarios={low:'保守',base:'基准',high:'乐观'}
function addOverride(){value.value.roi.overrides[overrideId.value]={...value.value.roi.rates}}
</script>
<style scoped>
.investment-controls{font-size:12px;color:#25372e}h2{font-size:18px}label{display:block;font-size:12px;margin:10px 0}input,select,textarea{width:100%;box-sizing:border-box;padding:8px;border:1px solid #ccd9d0;border-radius:5px;background:white;font:inherit;color:inherit;margin-top:5px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}p{font-size:11px;line-height:1.8;color:#68766e}summary{cursor:pointer;font-size:12px;padding:12px 0}button{background:white;border:1px solid #ccd9d0;border-radius:5px;color:#285b43;padding:7px;font-size:11px;margin:5px 4px 5px 0}
</style>
