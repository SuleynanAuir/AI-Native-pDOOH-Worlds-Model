// Replaying completed records never creates a new simulation or provider call.
export function advancePlayback({cursor,maxRound,complete,loop,firstFrame=1}) {
  if (cursor < maxRound) return {cursor:cursor+1,playing:true}
  if (!complete) return {cursor,playing:true}
  if (loop && maxRound >= firstFrame) return {cursor:firstFrame,playing:true}
  return {cursor,playing:false}
}
