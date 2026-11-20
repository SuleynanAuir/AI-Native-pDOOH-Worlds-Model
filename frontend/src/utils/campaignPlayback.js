// Attitudes are exposure-weighted model estimates, not observed public opinion.
// Unknown vehicle passengers are excluded from the colour denominator.
export function attitudeColor(value) {
  if(value==null||!Number.isFinite(value))return '#68747c'
  const stops=[[179,52,57],[147,102,0],[22,118,75]],v=Math.max(0,Math.min(100,value)),i=v<50?0:1,t=(v-i*50)/50
  return '#'+stops[i].map((a,k)=>Math.round(a+(stops[i+1][k]-a)*t).toString(16).padStart(2,'0')).join('')
}
export function indexAttitudes(events, agents) {
  const screens={}
  for(const e of events||[]) {
    const list=screens[e.screen_id]||(screens[e.screen_id]=[])
    const id=e.kind==='pedestrian'?String(e.actor_id).match(/^p-(\d+)-/)?.[1]:null
    list.push({...e,time:(e.round-1)*60+e.minute,rating:id!=null?agents?.[id]:null})
  }
  const result={}
  for(const [id,rows] of Object.entries(screens)) {
    let total=0,interestSum=0,interestWeight=0,favorabilitySum=0,favorabilityWeight=0
    result[id]=rows.sort((a,b)=>a.time-b.time||a.id.localeCompare(b.id)).map(e=>{
      total+=e.count
      for(const key of ['interest','favorability']){
        const value=e.rating?.[key]
        if(typeof value==='number'&&Number.isFinite(value)){
          if(key==='interest'){interestSum+=value*e.count;interestWeight+=e.count}
          else{favorabilitySum+=value*e.count;favorabilityWeight+=e.count}
        }
      }
      return {time:e.time,total,interest:interestWeight?interestSum/interestWeight:null,favorability:favorabilityWeight?favorabilitySum/favorabilityWeight:null,interestWeight,favorabilityWeight}
    })
  }
  return result
}
export function attitudesAt(index,round,minute) {
  const time=(round-1)*60+minute,result={}
  for(const [id,rows] of Object.entries(index)){
    let lo=0,hi=rows.length
    while(lo<hi){const mid=(lo+hi)>>>1;if(rows[mid].time<=time)lo=mid+1;else hi=mid}
    result[id]=rows[lo-1]||{interest:null,favorability:null,total:0,interestWeight:0,favorabilityWeight:0}
  }
  return result
}
