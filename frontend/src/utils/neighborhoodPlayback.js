// Replay recorded routes only. Clock jumps never connect two unrelated hourly outings.
export function sampleJourney(journey, minute) {
  const points=journey?.waypoints || []
  if (!points.length || minute<points[0].minute || minute>points.at(-1).minute) return null
  let index=points.findIndex(p=>p.minute>=minute)
  if(index<=0) index=1
  const a=points[index-1], b=points[index] || a
  const fraction=b.minute>a.minute?(minute-a.minute)/(b.minute-a.minute):1
  const stationary=a.x===b.x && a.y===b.y
  return {x:a.x+(b.x-a.x)*fraction,y:a.y+(b.y-a.y)*fraction,
    activity:stationary?b.activity:minute>journey.end_minute-.35?points.at(-1).activity:minute<journey.start_minute+.35?points[0].activity:'步行 / '+journey.purpose,
    stationary,angle:Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI,
    stage:minute>journey.end_minute-.35?'departing':minute<journey.start_minute+.35?'arriving':stationary?'staying':'walking'}
}
export function routePath(journey){return (journey?.waypoints||[]).map((p,i)=>`${i?'L':'M'}${p.x},${p.y}`).join(' ')}
