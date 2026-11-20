// Prefix indexes make deterministic seeking cheap; rendering never increments counters.
export function indexImpressions(events) {
  const groups={}
  for(const event of events||[]) {
    const list=groups[event.screen_id]||(groups[event.screen_id]=[])
    list.push({...event,time:(event.round-1)*60+event.minute})
  }
  const result={}
  for(const [screen,list] of Object.entries(groups)) {
    list.sort((a,b)=>a.time-b.time||a.id.localeCompare(b.id))
    let pedestrian=0,vehicle=0,vehicles=0,walkers=0
    result[screen]=list.map(e=>{if(e.kind==='pedestrian'){pedestrian+=e.count;walkers+=e.units}else{vehicle+=e.count;vehicles+=e.units}return {time:e.time,pedestrian,vehicle,vehicles,walkers,total:pedestrian+vehicle}})
  }
  return result
}
export function impressionsAt(index,round,minute) {
  const time=(round-1)*60+minute,result={}
  for(const [screen,rows] of Object.entries(index)) {
    let lo=0,hi=rows.length
    while(lo<hi){const mid=(lo+hi)>>>1;if(rows[mid].time<=time)lo=mid+1;else hi=mid}
    const row=rows[lo-1]
    result[screen]=row?{...row,recent:time-row.time<1}:{total:0,pedestrian:0,vehicle:0,vehicles:0,walkers:0,recent:false}
  }
  return result
}
