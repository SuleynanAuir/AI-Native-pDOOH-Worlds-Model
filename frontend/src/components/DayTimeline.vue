<template>
  <section class="day-timeline" v-if="schedule.length">
    <div class="day-heading"><div><span class="clock">{{ slot?.time || '00:00' }}</span><b>{{ slot?.period_label }}</b><span v-if="slot?.holiday_active" class="festival">✦ {{ slot.holiday_name }}</span><small>{{ slot?.date }} · {{ cursor ? 'OASIS 逐小时回放' : '排程预览 · 尚未推演' }}</small></div><div class="day-tabs"><button v-for="d in days" :key="d" @click="selectedDay=d" :class="{selected:selectedDay===d}">第 {{ d }} 天</button></div></div>
    <div class="hour-grid">
      <button v-for="s in hours" :key="s.round" :disabled="busy" :class="[s.period,{active:slot?.round===s.round,pending:!record(s.round)}]" :aria-label="`第 ${s.day} 天 ${s.time} ${s.period_label}`" :title="`${s.time} ${s.period_label}；排程 ${s.scheduled_population.toLocaleString()} 人；${record(s.round)?'点击回放':'尚无决策记录'}`" @click="$emit('select',s)">
        <div class="bar-track"><i class="schedule-bar" :style="{height:Math.max(3,100*s.scheduled_population/maxPopulation)+'%'}"></i><i v-if="record(s.round)" class="notice-bar" :style="{height:100*record(s.round).summary.noticed_population/maxPopulation+'%'}"></i></div><span>{{ s.time.slice(0,2) }}</span>
      </button>
    </div>
    <div class="time-key"><span class="morning">● 上班高峰</span><span class="evening">● 下班高峰</span><span class="night">● 夜间消费</span><span>浅柱：排程人数 · 亮线：模型注意人数</span><span>未生成的小时保留待推演状态</span></div>
  </section>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
const props=defineProps({schedule:{type:Array,default:()=>[]},snapshots:{type:Array,default:()=>[]},cursor:Number,slot:Object,busy:Boolean})
defineEmits(['select'])
const selectedDay=ref(1)
const days=computed(()=>[...new Set(props.schedule.map(s=>s.day))])
const hours=computed(()=>props.schedule.filter(s=>s.day===selectedDay.value))
const maxPopulation=computed(()=>Math.max(1,...props.schedule.map(s=>s.scheduled_population)))
const record=round=>props.snapshots.find(s=>s.round===round)
watch(()=>props.slot?.day,v=>{if(v)selectedDay.value=v})
watch(days,v=>{if(!v.includes(selectedDay.value))selectedDay.value=1})
</script>
<style scoped>
.day-timeline{background:linear-gradient(115deg,#ffffff,#ffffff);border:1px solid #dce2e5;border-radius:10px;padding:20px 22px;margin-bottom:20px}.day-heading{display:flex;justify-content:space-between;gap:12px;align-items:start}.day-heading>div:first-child{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.clock{font-size:34px;color:#191d21;font-variant-numeric:tabular-nums;letter-spacing:1px}.day-heading b{font-size:14px;color:#191d21}.day-heading small{font-size:11px;color:#525b65}.festival{font-size:11px;color:#9a452b;border:1px solid #dce2e5;border-radius:12px;padding:5px 9px}.day-tabs{display:flex;gap:5px}.day-tabs button{background:transparent;color:#525b65;border:1px solid #dce2e5;border-radius:4px;padding:6px;white-space:nowrap;cursor:pointer}.day-tabs .selected{background:#e6f3ed;color:#191d21}.hour-grid{display:grid;grid-template-columns:repeat(24,minmax(0,1fr));gap:6px;margin-top:20px}.hour-grid button{background:transparent;color:#525b65;border:1px solid transparent;border-radius:5px;padding:4px 3px;cursor:pointer;min-width:0}.hour-grid button:hover,.hour-grid button.active{border-color:#dce2e5;background:#e6f3ed}.hour-grid button.active span{color:#191d21}.bar-track{height:60px;position:relative}.bar-track i{position:absolute;bottom:0;border-radius:3px 3px 0 0}.schedule-bar{left:8%;width:84%;background:currentColor;opacity:.35}.notice-bar{width:30%;left:35%;background:#a5ffe1}.hour-grid span{font-size:11px;display:block;margin-top:7px}.morning{color:#9a452b!important}.evening{color:#191d21!important}.night{color:#191d21!important}.time-key{display:flex;gap:16px;flex-wrap:wrap;font-size:10px;color:#525b65;margin-top:15px}.pending .schedule-bar{background:repeating-linear-gradient(135deg,currentColor,currentColor 3px,transparent 3px,transparent 6px)}@media(max-width:750px){.day-timeline{padding:14px 10px}.hour-grid{gap:1px}.hour-grid button{padding:3px 0}.hour-grid span{font-size:8px}.clock{font-size:28px}.day-heading{flex-wrap:wrap}.day-heading small{width:100%}.time-key{gap:8px;font-size:9px}.day-heading>div:first-child{gap:8px}.bar-track{height:45px}}
</style>
