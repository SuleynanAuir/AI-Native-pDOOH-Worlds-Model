import test from 'node:test'
import assert from 'node:assert/strict'
import {indexImpressions,impressionsAt} from './trafficPlayback.js'
const events=[{id:'a',round:1,minute:12,screen_id:'A',kind:'pedestrian',count:30,units:1},{id:'b',round:1,minute:20,screen_id:'A',kind:'vehicle',count:3,units:1},{id:'c',round:2,minute:10,screen_id:'B',kind:'vehicle',count:20,units:1},{id:'d',round:2,minute:15,screen_id:'A',kind:'pedestrian',count:45,units:1}]
const index=indexImpressions(events)
test('counters increase at events, never from frame count',()=>{
 assert.equal(impressionsAt(index,1,11).A.total,0)
 assert.equal(impressionsAt(index,1,12).A.total,30)
 assert.deepEqual(impressionsAt(index,1,20),impressionsAt(index,1,20))
 assert.equal(impressionsAt(index,1,20).A.vehicle,3)
 assert.equal(impressionsAt(index,1,20).A.vehicles,1)
 assert.equal(impressionsAt(index,2,59).A.total,78)
 assert.equal(impressionsAt(index,2,59).B.total,20)
})
test('backward seeking and loop reset do not duplicate impressions',()=>{
 const last=impressionsAt(index,2,59);assert.equal(last.A.total,78)
 assert.equal(impressionsAt(index,1,13).A.total,30)
 assert.equal(impressionsAt(index,1,0).A.total,0)
 assert.deepEqual(impressionsAt(index,2,59),last)
})
test('empty traffic and unsorted events are deterministic',()=>{
 assert.deepEqual(impressionsAt(indexImpressions([]),1,30),{})
 assert.deepEqual(impressionsAt(indexImpressions([...events].reverse()),2,59),impressionsAt(index,2,59))
})
