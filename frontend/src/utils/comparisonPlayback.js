export function distinctScenes(catalog, count=4) {
  const seen=new Set(),selected=[]
  for(const item of catalog){if(seen.has(item.location_key))continue;seen.add(item.location_key);selected.push(item.id);if(selected.length===count)break}
  return [...selected,...Array(Math.max(0,count-selected.length)).fill('')]
}
export function advanceClock(round,minute,delta,rounds,loop=true){
  const total=rounds*60;let t=(round-1)*60+minute+delta
  if(t>=total){if(!loop)return {round:rounds,minute:59.99,playing:false};t%=total}
  return {round:Math.floor(t/60)+1,minute:t%60,playing:true}
}
