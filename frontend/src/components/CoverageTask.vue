<template><section class="coverage-task"><b>补齐全库存直接模拟</b><p>逐屏查证地图 → 100个代表画像 → 24小时 OASIS → 广告好感与兴趣。会调用地图与大模型；已有完成结果会保留。</p><button :disabled="!campaignId||running||busy" @click="start">{{ running?'逐屏模拟进行中':'开始 / 继续补齐未覆盖屏幕' }}</button><p v-if="state">新增完成 {{ state.done }} / {{ state.total }} · {{ state.message }}</p><p v-if="error">{{ error }}</p><details v-if="state?.failures?.length"><summary>失败记录</summary><p v-for="f in state.failures" :key="f.screen_id">{{ f.screen_id }}：{{ f.error }}</p></details><small>完成后点击页面计算按钮更新覆盖率与投资金额；正在生成或失败的屏幕不计入直接覆盖。</small></section></template>
<script setup>
import {ref,computed,watch,onBeforeUnmount} from 'vue'
import api from '../api'
const props=defineProps({projectId:String,campaignId:String}),state=ref(null),error=ref(''),busy=ref(false)
const emit=defineEmits(['completed'])
let timer,version=0
const running=computed(()=>state.value?.status==='running')
const url=()=>`/api/planning/${props.projectId}/coverage/${props.campaignId}`
async function read(){const v=version;if(!props.campaignId)return;try{const r=await api.get(url());if(v===version){const previous=state.value?.done||0;state.value=r.data;if(r.data.done>previous)emit('completed')}}catch(e){if(v===version)error.value=e.message}}
async function start(){busy.value=true;error.value='';const v=version;try{const r=await api.post(url(),{});if(v===version)state.value=r.data}catch(e){if(v===version)error.value=e.message}finally{busy.value=false}}
watch(()=>[props.projectId,props.campaignId],()=>{version++;state.value=null;clearInterval(timer);read();timer=setInterval(read,5000)},{immediate:true})
onBeforeUnmount(()=>{version++;clearInterval(timer)})
</script>
<style scoped>.coverage-task{padding:14px;background:#f3f8f5;border:1px solid #d4e2d8;border-radius:8px;margin-bottom:16px;font-size:12px}p,small{font-size:11px;line-height:1.8;color:#53695a}button{padding:10px;background:white;color:#235b40;border:1px solid #bed3c4;border-radius:5px;cursor:pointer}button:disabled{opacity:.5}summary{cursor:pointer}</style>
