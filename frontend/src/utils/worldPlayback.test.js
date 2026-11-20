import {test} from 'node:test'
import assert from 'node:assert/strict'
import {advancePlayback} from './worldPlayback.js'

test('a full day repeats 00 through 23 without the initialization frame',()=>{
  let cursor=1
  const seen=[]
  for(let i=0;i<48;i++){
    seen.push(cursor)
    const next=advancePlayback({cursor,maxRound:24,complete:true,loop:true})
    assert.equal(next.playing,true);cursor=next.cursor
  }
  assert.deepEqual(seen,[...Array.from({length:24},(_,i)=>i+1),...Array.from({length:24},(_,i)=>i+1)])
})
test('disabled loop stops at the end and incomplete run waits without wrapping',()=>{
  assert.deepEqual(advancePlayback({cursor:24,maxRound:24,complete:true,loop:false}),{cursor:24,playing:false})
  assert.deepEqual(advancePlayback({cursor:8,maxRound:8,complete:false,loop:true}),{cursor:8,playing:true})
  assert.deepEqual(advancePlayback({cursor:8,maxRound:9,complete:false,loop:true}),{cursor:9,playing:true})
})
test('multiple days wrap only after the final hour and empty runs do not play',()=>{
  assert.equal(advancePlayback({cursor:24,maxRound:48,complete:true,loop:true}).cursor,25)
  assert.equal(advancePlayback({cursor:48,maxRound:48,complete:true,loop:true}).cursor,1)
  assert.deepEqual(advancePlayback({cursor:0,maxRound:0,complete:true,loop:true}),{cursor:0,playing:false})
})
