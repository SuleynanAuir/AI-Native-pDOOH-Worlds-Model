import test from 'node:test'
import assert from 'node:assert/strict'
import {sampleJourney,routePath} from './neighborhoodPlayback.js'
const trip={start_minute:10,end_minute:22,purpose:'普通行人穿行',waypoints:[{x:0,y:0,minute:10,activity:'进入街区'},{x:120,y:0,minute:12,activity:'步行'},{x:120,y:0,minute:14,activity:'等待人行横道'},{x:120,y:120,minute:22,activity:'步行离开街区'}]}
test('people enter, wait, cross and leave without connecting hourly teleports',()=>{
 assert.equal(sampleJourney(trip,9),null)
 assert.equal(sampleJourney(trip,23),null)
 assert.equal(sampleJourney(trip,10.1).stage,'arriving')
 assert.equal(sampleJourney(trip,11).x,60)
 const wait=sampleJourney(trip,13);assert.equal(wait.stationary,true);assert.equal(wait.activity,'等待人行横道')
 assert.equal(sampleJourney(trip,18).y,60)
 assert.equal(sampleJourney(trip,21.9).stage,'departing')
 assert.equal(routePath(trip),'M0,0 L120,0 L120,0 L120,120')
})
test('missing journeys never show fake pedestrian positions',()=>{
 assert.equal(sampleJourney(null,30),null)
 assert.equal(sampleJourney({waypoints:[]},30),null)
})
