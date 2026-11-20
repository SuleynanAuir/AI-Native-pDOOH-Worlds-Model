<template>
  <div class="day-config">
    <div class="config-title">全天时钟与节日 <span>每小时一轮</span></div>
    <div class="fields"><label>模拟天数<input type="number" min="1" max="3" v-model.number="value.days" :disabled="disabled"></label><label>起始日期（可选）<input type="date" v-model="value.start_date" :disabled="disabled"></label></div>
    <div v-for="(label,key) in labels" :key="key" class="period-input"><span>{{ label }}</span><input :aria-label="label+'开始小时'" type="number" min="0" max="23" v-model.number="value.periods[key].start" :disabled="disabled"><span>至</span><input :aria-label="label+'结束小时'" type="number" min="1" max="24" v-model.number="value.periods[key].end" :disabled="disabled"><small>点</small></div>
    <label>节日 / 活动<select aria-label="节日 / 活动" v-model="value.holiday.id" @change="chooseHoliday" :disabled="disabled"><option v-for="p in presets" :key="p.id" :value="p.id">{{ p.name }}</option></select></label>
    <details v-if="value.holiday.id!=='ordinary'" :open="value.holiday.id==='custom'" class="holiday-details"><summary>编辑节日情景与活动系数</summary>
      <label>活动名称<input v-model="value.holiday.name" maxlength="100" :disabled="disabled"></label>
      <label>节日场景说明<textarea v-model="value.holiday.description" rows="3" maxlength="1000" :disabled="disabled" /></label>
      <div class="fields"><label>通勤活动系数<input type="number" min="0.1" max="3" step="0.1" v-model.number="value.holiday.commute_factor" :disabled="disabled"></label><label>休闲消费系数<input type="number" min="0.1" max="3" step="0.1" v-model.number="value.holiday.leisure_factor" :disabled="disabled"></label><label>活动开始小时<input type="number" min="0" max="23" v-model.number="value.holiday.start_hour" :disabled="disabled"></label><label>活动结束小时<input type="number" min="1" max="24" v-model.number="value.holiday.end_hour" :disabled="disabled"></label></div>
    </details>
    <p>时段采用左闭右开区间，可跨午夜；节日按设定每日重复，不自动判定法定假日。活动系数是可修改的出场机会假设，不是客流增长或购买概率。</p>
  </div>
</template>
<script setup>
const value=defineModel({required:true})
const props=defineProps({presets:{type:Array,default:()=>[]},disabled:Boolean})
const labels={morning:'上班高峰',evening:'下班高峰',night:'夜间消费'}
function chooseHoliday(){const preset=props.presets.find(p=>p.id===value.value.holiday.id);if(preset)value.value.holiday={...preset,start_hour:0,end_hour:24}}
</script>
<style scoped>
.day-config{padding:15px 16px;border-top:1px solid #dce2e5}.config-title{font-size:13px;color:#191d21;margin-bottom:14px;display:flex;justify-content:space-between}.config-title span{font-size:10px;color:#525b65}.fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}.fields>*{min-width:0}label{display:block;font-size:11px;color:#525b65;margin-bottom:12px}input,select,textarea{display:block;width:100%;min-width:0;background:#ffffff;color:#191d21;border:1px solid #dce2e5;padding:8px;border-radius:5px;font:inherit;margin-top:6px;color-scheme:light}input:disabled,select:disabled,textarea:disabled{opacity:.5}.period-input{display:flex;gap:6px;align-items:center;color:#525b65;font-size:11px;margin-bottom:10px}.period-input>span:first-child{flex:1;white-space:nowrap}.period-input input{width:52px;margin:0;padding:7px 3px}p{font-size:10px;line-height:1.8;color:#525b65;margin:4px 0}.day-config textarea{resize:vertical}
.holiday-details{margin:6px 0 14px}.holiday-details summary{font-size:11px;color:#191d21;cursor:pointer;margin-bottom:12px}
</style>
