// Per-scene bounded cache. Prefetch and foreground playback share requests.
export function createHourCache(fetchHour, limit=6) {
  const values=new Map(),pending=new Map()
  function peek(hour){const value=values.get(hour);if(value){values.delete(hour);values.set(hour,value)}return value}
  function get(hour){
    const value=peek(hour);if(value)return Promise.resolve(value)
    if(pending.has(hour))return pending.get(hour)
    const request=Promise.resolve().then(()=>fetchHour(hour)).then(value=>{
      if(value.round!==hour)throw Error('小时回放记录不匹配')
      values.set(hour,value);while(values.size>limit)values.delete(values.keys().next().value)
      return value
    }).finally(()=>pending.delete(hour))
    pending.set(hour,request);return request
  }
  return {peek,get,async prefetch(hour,total){
    for(let offset=1;offset<=2;offset++){
      const next=(hour-1+offset)%total+1
      try{await get(next)}catch{return} // Foreground retries failures with a visible error.
    }
  }}
}
