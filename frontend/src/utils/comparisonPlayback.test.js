import test from 'node:test'
import assert from 'node:assert/strict'
import {distinctScenes,advanceClock} from './comparisonPlayback.js'
test('defaults pick distinct locations, leave slots empty rather than duplicate scenes',()=>{
 const catalog=[{id:'a',location_key:'one'},{id:'b',location_key:'one'},{id:'c',location_key:'two'}]
 assert.deepEqual(distinctScenes(catalog),['a','c','',''])
})
test('comparison clock seeks across hours and loops without incrementing any counts',()=>{
 assert.deepEqual(advanceClock(9,59,2,24,true),{round:10,minute:1,playing:true})
 assert.deepEqual(advanceClock(24,59,2,24,true),{round:1,minute:1,playing:true})
 assert.deepEqual(advanceClock(24,59,2,24,false),{round:24,minute:59.99,playing:false})
})
