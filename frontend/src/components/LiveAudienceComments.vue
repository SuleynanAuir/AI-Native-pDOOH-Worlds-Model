<template>
  <section class="live-comments" aria-label="代表性模拟评论">
    <div class="comments-heading"><h3>广告内容点评</h3><span><i :class="{live:playing && active}" />{{ playing && active ? '随回放更新' : '已暂停' }}</span></div>
    <div ref="viewport" class="comment-stream" :class="{'reduced-motion':reducedMotion}" aria-live="off" :data-playing="playing && active">
      <article v-for="(item, i) in visible" :key="item.key" class="live-comment" :data-comment-key="item.key" :data-agent-id="item.agentId" :data-style="item.style" :data-axis="item.axis" role="button" tabindex="0" :aria-label="`${item.name}：${item.text}，查看完整分析`" :title="item.hint||item.group" @click="$emit('person',item.agentId)" @keydown.enter="$emit('person',item.agentId)" @keydown.space.prevent="$emit('person',item.agentId)" :style="cardStyle(item,i)">
        <div class="comment-person"><span class="comment-avatar">{{ item.name?.slice(0,1) || '人' }}</span><div><b>{{ item.name }}</b><small>{{ item.axis || item.group }}<template v-if="item.interest!=null"> · 兴趣 {{ item.interest }}</template></small></div></div>
        <p>“{{ item.text }}”</p>
      </article>
      <p v-if="!visible.length" class="comments-empty">{{ !available ? '广告内容点评待生成，请打开人群分析' : '等待新的、不重复的经过评论' }}</p>
    </div>
    <small class="comments-caption">画像推演摘录 · 非真实路人发言</small>
  </section>
</template>
<script setup>
import {ref,computed,watch,onMounted,onBeforeUnmount} from 'vue'
import {commentTimeline,createCommentQueue} from '../utils/commentPlayback'
defineEmits(['person'])
const props=defineProps({events:Array,narrative:Object,round:Number,minute:Number,playing:Boolean,active:{type:Boolean,default:true},seen:{type:Set,default:()=>new Set()}})
const viewport=ref(null),height=ref(250),visible=ref([]),reducedMotion=ref(false)
const available=computed(()=>Object.values(props.narrative?.agents||{}).some(p=>p.ad_anchor&&p.ad_focus))
const timeline=computed(()=>commentTimeline(props.events,props.narrative))
let queue=createCommentQueue([]),timer,observer,media,last=0,elapsed=0
const lifetime=15000,interval=6000
const time=()=>((props.round||1)-1)*60+(props.minute||0)
function add(age=0){const row=queue.take();if(row)visible.value.push({...row,age,phase:(row.agentId*2.399)%6.283,drift:4+(row.agentId%3),inset:8+(row.agentId%3)*2})}
watch(timeline,rows=>{queue=createCommentQueue(rows,props.seen);visible.value=[];elapsed=0;queue.offer(time());for(const age of [9300,3300])add(age)},{immediate:true})
watch(()=>[props.round,props.minute],()=>{if(queue.offer(time())){visible.value=[];elapsed=interval}})
function cardStyle(item,i){
  if(reducedMotion.value)return {transform:`translateY(${i*116}px)`,opacity:1}
  const progress=Math.min(1,item.age/lifetime)
  const wave=Math.sin(progress*Math.PI*3+item.phase)
  const y=height.value+12-progress*(height.value+128)
  // Each bubble gently sways and expands as it rises; only the last section dissolves.
  const scale=.92+.08*Math.sin(Math.PI*Math.min(1,progress/.85))
  const fade=Math.max(0,Math.min(1,(1-progress)/.34))
  return {
    '--bubble-inset':`${item.inset}px`,
    transform:`translate3d(${wave*item.drift}px,${y}px,0) rotate(${wave*.7}deg) scale(${scale})`,
    opacity:Math.min(1,progress/.07)*fade,
    filter:`blur(${Math.max(0,progress-.84)*5}px)`,
  }
}
function motionChange(){reducedMotion.value=media.matches}
onMounted(()=>{
  media=window.matchMedia('(prefers-reduced-motion: reduce)');motionChange();media.addEventListener('change',motionChange)
  observer=new ResizeObserver(entries=>{if(entries[0].contentRect.height>0)height.value=entries[0].contentRect.height});observer.observe(viewport.value)
  last=performance.now();timer=setInterval(()=>{
    const now=performance.now(),delta=Math.min(now-last,250);last=now
    if(!props.playing||!props.active||document.hidden)return
    visible.value=visible.value.map(row=>({...row,age:row.age+delta})).filter(row=>row.age<lifetime)
    elapsed+=delta
    if(elapsed>=interval){elapsed=0;add()}
  },100)
})
onBeforeUnmount(()=>{clearInterval(timer);observer?.disconnect();media?.removeEventListener('change',motionChange)})
</script>
<style scoped>
.live-comments{min-width:0;min-height:0;display:flex;flex-direction:column;flex:1}.comments-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 0 8px}.comments-heading h3{margin:0;font-size:12px;font-weight:600;color:#1d2522}.comments-heading>span{font-size:9px;white-space:nowrap;color:#68746d}.comments-heading i{display:inline-block;width:5px;height:5px;border-radius:50%;background:#a6b1ac;margin-right:5px}.comments-heading i.live{background:#258066}.comment-stream{position:relative;isolation:isolate;flex:1;height:0;min-height:0;overflow:hidden;mask-image:linear-gradient(transparent,#000 9%,#000 91%,transparent)}.live-comment{cursor:pointer;position:absolute;left:var(--bubble-inset,8px);right:var(--bubble-inset,8px);top:0;height:104px;box-sizing:border-box;margin:0;padding:9px 10px;background:linear-gradient(145deg,#ffffffed,#f0f8f3ed);border:1px solid #d7e7dd;border-radius:22px 25px 21px 12px;box-shadow:0 6px 15px #234b3310,inset 0 1px 0 #fff;will-change:transform,opacity;transform-origin:center;transition:transform .1s linear,opacity .1s linear,filter .1s linear}
.live-comment::before{content:"";position:absolute;right:15px;top:5px;width:20px;height:5px;border-radius:50%;background:#fff9;transform:rotate(16deg);pointer-events:none}
.live-comment::after{content:"";position:absolute;right:22px;bottom:-6px;width:7px;height:7px;background:#f2f8f4;border:1px solid #d7e7dd;border-radius:50%;pointer-events:none}
.comment-person{display:flex;gap:7px;align-items:center;height:24px}.comment-avatar{width:22px;height:22px;display:grid;place-items:center;flex-shrink:0;background:#edf4ef;color:#416451;border-radius:50%;font-size:12px}.comment-person>div{min-width:0}.comment-person b,.comment-person small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.comment-person b{font-size:10px;font-weight:600;color:#24322b}.comment-person small{font-size:9px;color:#6c7971;margin-top:2px}.live-comment p{font-size:11px;line-height:1.55;margin:6px 0 0;color:#242e29;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;overflow-wrap:anywhere}.comments-empty{position:absolute;inset:30% 12px auto;text-align:center;line-height:1.8;font-size:11px;color:#7a857f}.comments-caption{font-size:9px;color:#7a857f;margin-top:5px}.reduced-motion .live-comment{transition:none;will-change:auto;filter:none;transform-origin:initial}.reduced-motion .live-comment::after{display:none}.reduced-motion{mask-image:none}
.live-comment:focus-visible{outline:2px solid #247a58;outline-offset:-2px}
</style>
