import test from 'node:test'
import assert from 'node:assert/strict'
import {parseCalibrationCSV} from './roiCalibration.js'
const header='screen_id,test_exposures,test_orders,control_exposures,control_orders,order_value,margin,extra_cost,currency,period,source\n'
test('quoted CSV sources and numeric amounts',()=>{const r=parseCalibrationCSV(header+'s,10000,12,10000,5,100,.4,12.50,USD,2026-10,"matched control, internal"','USD');assert.equal(r.s.extra_cost,12.5);assert.equal(r.s.source,'matched control, internal')})
test('reject duplicate identities, currencies, blanks and unterminated quote',()=>{const row='s,10000,12,10000,5,100,.4,0,USD,2026-10,internal';assert.throws(()=>parseCalibrationCSV(header+row+'\n'+row,'USD'));assert.throws(()=>parseCalibrationCSV(header+row,'CNY'));assert.throws(()=>parseCalibrationCSV(header+row.replace('10000',''),'USD'));assert.throws(()=>parseCalibrationCSV(header+'"broken','USD'))})
