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

// Preserve chosen locations, promote current-batch results, and fill even saved empty slots.
export function fillSceneSlots(catalog, previous=[], count=4) {
 const location=s=>s.location_key||`${s.coordinate?.lat},${s.coordinate?.lon}`
 const used=new Set(),result=[]
 for(let i=0;i<count;i++){
  let item=catalog.find(s=>s.id===previous[i])
  if(item){item=catalog.find(s=>s.current_batch&&location(s)===location(item))||item}
  if(!item||used.has(location(item)))item=catalog.find(s=>!used.has(location(s)))
  result.push(item?.id||'');if(item)used.add(location(item))
 }
 return result
}
