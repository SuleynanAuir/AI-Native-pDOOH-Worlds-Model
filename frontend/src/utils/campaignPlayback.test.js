import test from 'node:test'
import assert from 'node:assert/strict'
import {indexAttitudes,attitudesAt,attitudeColor} from './campaignPlayback.js'
test('weighted attitude ignores unknown passengers and distinguishes zero from unknown',()=>{
 const events=[{id:'a',screen_id:'s',round:1,minute:1,kind:'pedestrian',actor_id:'p-1-0',count:100},{id:'b',screen_id:'s',round:1,minute:2,kind:'vehicle',actor_id:'v-1',count:1000},{id:'c',screen_id:'s',round:1,minute:3,kind:'pedestrian',actor_id:'p-2-0',count:300}]
 const index=indexAttitudes(events,{'1':{interest:0,favorability:null},'2':{interest:80,favorability:40}})
 assert.equal(attitudesAt(index,1,0).s.interest,null)
 assert.equal(attitudesAt(index,1,2).s.interest,0)
 const end=attitudesAt(index,1,5).s
 assert.equal(end.interest,60);assert.equal(end.interestWeight,400);assert.equal(end.total,1400);assert.equal(end.favorability,40);assert.equal(end.favorabilityWeight,300)
 assert.equal(attitudesAt(index,1,1).s.interest,0)
 assert.deepEqual(attitudesAt(index,1,5),attitudesAt(index,1,5))
})
test('gradient is continuous and unknown is neutral grey, not zero',()=>{
 assert.equal(attitudeColor(0),'#b33439');assert.equal(attitudeColor(50),'#936600');assert.equal(attitudeColor(100),'#16764b')
 assert.equal(attitudeColor(null),'#68747c');assert.notEqual(attitudeColor(30),attitudeColor(31));assert.equal(attitudeColor(101),attitudeColor(100))
})
