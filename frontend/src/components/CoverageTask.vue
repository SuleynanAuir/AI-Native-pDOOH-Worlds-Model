<template><section class="coverage-task"><b>本轮全天模拟 · 00:00–24:00</b><p>逐屏查证地图 → 100个代表画像 → 24小时 OASIS → 广告好感与兴趣。会调用地图与大模型；仅续跑本轮，历史运行不计入。</p><button :disabled="state?.ready||busy||state?.status==='needs_campaign'" @click="start">{{ state?.ready?'✓ 本轮全天模拟完成':busy?'正在启动本轮模拟…':'开始本轮全天模拟' }}</button><p v-if="state">已关联 {{ state.direct||0 }} 块 · 本批完成 {{ state.done }} / {{ state.total }} · {{ state.message }}</p><p v-if="error">{{ error }}</p><details v-if="state?.failures?.length"><summary>失败记录</summary><p v-for="f in state.failures" :key="f.screen_id">{{ f.screen_id }}：{{ f.error }}</p></details><small>本轮全部屏幕完成24小时模拟后自动停止，可点击「生成屏幕分析报告」。</small></section></template>
<script setup>
import {ref,computed,watch,onBeforeUnmount} from 'vue'
import api from '../api'
const props=defineProps({projectId:String,campaignId:String}),state=ref(null),error=ref(''),busy=ref(false)
const emit=defineEmits(['completed','status','starting','started','start-failed'])
let timer,version=0
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
<style scoped>.coverage-task{padding:14px;background:#f3f8f5;border:1px solid #d4e2d8;border-radius:8px;margin-bottom:16px;font-size:12px}p,small{font-size:11px;line-height:1.8;color:#53695a}button{padding:10px;background:white;color:#235b40;border:1px solid #bed3c4;border-radius:5px;cursor:pointer}button:disabled{opacity:.5}summary{cursor:pointer}</style>
