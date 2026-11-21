// All arithmetic uses recorded synthetic encounter weights, never LLM arithmetic.
export const percent = (part, total) => total > 0 ? 100 * part / total : null
const validScore = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100
const empty = (id, name) => ({id,name,total:0,pedestrian:0,vehicle:0,rated:0,interestSum:0,high:0,representatives:new Set()})
function add(row,event,person,rating,threshold){
 row.total+=event.count
 if(event.kind==='pedestrian'){
  row.pedestrian+=event.count
  if(person!=null)row.representatives.add(person)
  if(validScore(rating)){row.rated+=event.count;row.interestSum+=rating*event.count;if(rating>=threshold)row.high+=event.count}
 }else row.vehicle+=event.count
}
function finish(row){return {...row,representatives:row.representatives.size,interest:row.rated?row.interestSum/row.rated:null,pedestrianShare:percent(row.pedestrian,row.total),coverage:percent(row.rated,row.total),pedestrianCoverage:percent(row.rated,row.pedestrian),highShare:percent(row.high,row.rated)}}
export function screenDecision(base,narrative,threshold=60,screenId=null){
 if(!base)return null
 if(!Number.isFinite(threshold)||threshold<0||threshold>100)throw Error('Interest threshold must be 0–100')
 const total=empty('all','合计'),screens=new Map(),hours=new Map(),groups=new Map()
 const screenNames=Object.fromEntries((base.screens||[]).map(s=>[s.id,s.name]))
 const groupNames=Object.fromEntries((base.groups||[]).map(g=>[g.id,g.name]))
 for(const slot of base.meta?.schedule||[])hours.set(slot.round,{...empty(slot.round,`第${slot.day||1}天 ${slot.time}`),round:slot.round,period:slot.period_label})
 for(const screen of base.screens||[])if(!screenId||screen.id===screenId)screens.set(screen.id,empty(screen.id,screen.name))
 for(const event of base.events||[]){
  if(screenId&&event.screen_id!==screenId)continue
  if(!Number.isFinite(event.count)||event.count<0||!['pedestrian','vehicle'].includes(event.kind))continue
  const person=event.kind==='pedestrian'?String(event.actor_id).match(/^p-(\d+)-/)?.[1]:null
  const rating=person!=null?base.attitudes?.agents?.[person]?.interest:null
  add(total,event,person,rating,threshold)
  if(!screens.has(event.screen_id))screens.set(event.screen_id,empty(event.screen_id,screenNames[event.screen_id]||event.screen_id))
  add(screens.get(event.screen_id),event,person,rating,threshold)
  if(!hours.has(event.round))hours.set(event.round,{...empty(event.round,`轮次 ${event.round}`),round:event.round})
  add(hours.get(event.round),event,person,rating,threshold)
  if(event.kind==='pedestrian'){
   const groupId=narrative?.agents?.[person]?.group_id||'unknown'
   if(!groups.has(groupId))groups.set(groupId,empty(groupId,groupNames[groupId]||'尚未关联人物群体'))
   add(groups.get(groupId),event,person,rating,threshold)
  }
 }
 const result={...finish(total),sceneId:base.meta.id,title:base.meta.title,durationHours:base.meta.rounds,threshold,screens:[...screens.values()].map(finish),hours:[...hours.values()].map(finish),groups:[...groups.values()].map(finish).sort((a,b)=>b.high-a.high||b.pedestrian-a.pedestrian)}
 result.peak=[...result.hours].sort((a,b)=>b.total-a.total||a.round-b.round).slice(0,3)
 return result
}
export function quoteScenario(summary,quote,sot){
 if(!summary||quote==null||String(quote).trim()===''||!Number.isFinite(Number(quote))||Number(quote)<0||!Number.isFinite(Number(sot))||Number(sot)<=0||Number(sot)>100)return null
 const fraction=Number(sot)/100,total=summary.total*fraction,high=summary.high*fraction
 return {quote:Number(quote),sot:Number(sot),opportunities:total,highOpportunities:high,cpm:total>0?1000*Number(quote)/total:null,highCpm:high>0?1000*Number(quote)/high:null}
}
