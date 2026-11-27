<template><section class="coverage-task"><b>全天模拟总进度</b><p v-if="state?.simulation_mode==='policy_simulation_v1'" class="policy-note">快速策略仿真：模型生成个人策略，本地执行100位代表的24小时演化；非逐小时模型独立决策。已完成的历史结果保留，各屏幕记录实际计算方式。</p><div class="total-progress" role="status"><strong>{{ state?.done || 0 }} / {{ state?.total || 0 }} 块屏幕已处理</strong><span>{{ percent }}%</span></div><progress aria-label="屏幕处理总进度" :value="state?.done || 0" :max="state?.total || 1"></progress><p>逐屏查证地图 → 100个代表画像 → 24小时行为推演 → 广告好感与兴趣。会调用地图与大模型；仅续跑本轮，历史运行不计入。</p><button :disabled="state?.ready||busy||running||state?.status==='needs_campaign'" @click="start">{{ state?.ready?'✓ 本轮全天模拟完成':busy?'正在启动本轮模拟…':running?'本轮模拟进行中':state?.status==='interrupted'||state?.status==='failed'?'继续本轮模拟（重试未完成屏幕）':'开始本轮全天模拟' }}</button><p v-if="state">实际分析完成 {{ state.done }} / {{ state.total }} 块屏幕 · {{ state.message }}</p><p v-if="error">{{ error }}</p><details v-if="state?.failures?.length"><summary>失败记录</summary><p v-for="f in state.failures" :key="f.screen_id">{{ f.screen_id }}：{{ f.error }}</p></details><small>本轮全部屏幕完成24小时模拟后自动停止，可点击「生成屏幕分析报告」。</small></section></template>
<script setup>
import {ref,computed,watch,onBeforeUnmount} from 'vue'
import api from '../api'
const props=defineProps({projectId:String,campaignId:String}),state=ref(null),error=ref(''),busy=ref(false)
const emit=defineEmits(['completed','status','starting','started','start-failed'])
let timer,version=0
const percent=computed(()=>state.value?.total?Math.floor(state.value.done/state.value.total*100):0)
const running=computed(()=>state.value?.status==='running')
const url=()=>`/api/planning/${props.projectId}/coverage`
function apply(value){
 const wasReady=state.value?.ready===true;state.value=value;error.value='';emit('status',value)
 if(value.ready){clearTimeout(timer);if(!wasReady)emit('completed')}
}
async function read(){
 const v=version;if(!props.projectId)return
 try{const r=await api.get(url());if(v===version)apply(r.data)}
 catch(e){if(v===version)error.value=e.message}
 finally{if(v===version&&!state.value?.ready)timer=setTimeout(read,5000)}
}
async function start(){
 if(busy.value||state.value?.ready||!props.projectId)return
 error.value='';emit('starting',{reset:!state.value||state.value.status==='not_started'})
 if(running.value){emit('started',state.value);return}
 busy.value=true;const v=version
 try{const r=await api.post(url(),{});if(v===version){apply(r.data);emit('started',r.data)}}
 catch(e){if(v===version){error.value=e.message;emit('start-failed',e.message)}}
 finally{if(v===version)busy.value=false}
}
defineExpose({start})

watch(()=>[props.projectId,props.campaignId],()=>{version++;state.value=null;clearTimeout(timer);read()},{immediate:true})
onBeforeUnmount(()=>{version++;clearTimeout(timer)})

</script>
<style scoped>.coverage-task{padding:14px;background:#f3f8f5;border:1px solid #d4e2d8;border-radius:8px;margin-bottom:16px;font-size:12px}p,small{font-size:11px;line-height:1.8;color:#53695a}button{padding:10px;background:white;color:#235b40;border:1px solid #bed3c4;border-radius:5px;cursor:pointer}button:disabled{opacity:.5}summary{cursor:pointer}.total-progress{display:flex;justify-content:space-between;gap:16px;margin-top:16px;font-size:15px;color:#205b40}progress{width:100%;height:14px;accent-color:#257455;margin:12px 0}</style>
