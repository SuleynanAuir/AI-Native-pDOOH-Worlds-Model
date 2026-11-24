import test from 'node:test'
import assert from 'node:assert/strict'
import {createHourCache} from './hourCache.js'
test('prefetch and playback deduplicate requests, including midnight wrap',async()=>{
 const calls=[];const cache=createHourCache(async round=>{calls.push(round);return {round}})
 await Promise.all([cache.prefetch(24,24),cache.get(1)])
 assert.deepEqual(calls,[1,2]);assert.equal(cache.peek(1).round,1)
 await cache.get(2);assert.deepEqual(calls,[1,2])
})
test('bounded cache and failed prefetch remain retryable',async()=>{
 let fail=true;const cache=createHourCache(async round=>{if(round===2&&fail)throw Error('network');return {round}},2)
 await cache.get(1);await cache.prefetch(1,24);fail=false
 assert.equal((await cache.get(2)).round,2);await cache.get(3)
 assert.equal(cache.peek(1),undefined)
})
test('wrong-hour response never enters cache',async()=>{
 const cache=createHourCache(async()=>({round:9}))
 await assert.rejects(cache.get(2));assert.equal(cache.peek(2),undefined)
})
