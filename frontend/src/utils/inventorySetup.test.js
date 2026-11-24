import { test } from 'node:test'
import assert from 'node:assert/strict'
import { inventoryRegion, inventoryBounds, resolveRegionFilters } from './inventorySetup.js'
const frames = [
  { screen_id: 'a', fields: { ADDRESS_ISO3_COUNTRY_CODE: 'USA', ADDRESS_LOCALITY: 'A', MARKET: 'M', CLOEST_POI: 'Store, West' } },
  { screen_id: 'b', fields: { ADDRESS_COUNTRY: 'USA', ADDRESS_LOCALITY: 'B', MARKET: 'N' } },
  { screen_id: 'c', fields: { ADDRESS_LOCALITY: 'C' } },
  { screen_id: 'd', fields: {} },
]
test('auto-fill preserves unique source values and POI commas', () => {
  const region = inventoryRegion(frames)
  assert.equal(region.city, 'A\nB\nC')
  assert.equal(region.country, 'USA')
  assert.equal(region.poi, 'Store, West')
  assert.equal(region.venue, '')
})
test('unchanged defaults keep incomplete rows; multi-value edits select union', () => {
  const region = inventoryRegion(frames)
  assert.deepEqual(resolveRegionFilters(frames, region).excludeIds, [])
  assert.ok(Object.values(resolveRegionFilters(frames, region).filters).every(v => v === ''))
  const edited = resolveRegionFilters(frames, { ...region, city: 'A\nB' })
  assert.deepEqual(edited.excludeIds, ['c', 'd'])
  assert.equal(edited.filters.city, '')
  assert.equal(resolveRegionFilters(frames, { ...region, city: 'B' }).filters.city, 'B')
})
test('new imports replace old geography; blank filters remain unrestricted', () => {
  assert.equal(inventoryRegion([frames[2]]).city, 'C')
  assert.deepEqual(resolveRegionFilters(frames, {}).excludeIds, [])
})

test('coordinate extent ignores missing and invalid points', () => {
  assert.equal(inventoryBounds([{lat: 37,lon:-122},{lat:38,lon:-121},{lat:null,lon:null},{lat:999,lon:0}]), '[37,-122,38,-121]')
  assert.equal(inventoryBounds(frames), '')
})
