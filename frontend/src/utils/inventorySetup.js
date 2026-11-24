const fields = {
  country: ['ADDRESS_ISO3_COUNTRY_CODE', 'ADDRESS_COUNTRY'],
  city: ['ADDRESS_LOCALITY'], market: ['MARKET'],
  venue: ['VENUE_TAXONOMY_VALUE'], poi: ['CLOSEST_POI', 'CLOEST_POI'],
}
const text = value => String(value ?? '').trim()
const entries = value => (Array.isArray(value) ? value : text(value).split('\n')).map(text).filter(Boolean)
const normalize = value => text(value).toLowerCase()

export function inventoryRegion(frames) {
  return Object.fromEntries(Object.entries(fields).map(([key, names]) => [key,
    [...new Set(frames.map(frame => names.map(name => text(frame.fields[name])).find(Boolean)).filter(Boolean))].join('\n'),
  ]))
}

// Keep the existing server filter contract. Multiple values become explicit
// screen exclusions; unchanged imported values must not discard incomplete rows.
export function resolveRegionFilters(frames, selected) {
  const imported = inventoryRegion(frames), filters = {}, excludeIds = new Set()
  for (const [key, names] of Object.entries(fields)) {
    const values = [...new Set(entries(selected[key]))]
    const baseline = entries(imported[key])
    const unchanged = values.length === baseline.length && values.every(v => baseline.includes(v))
    filters[key] = !unchanged && values.length === 1 ? values[0] : ''
    if (unchanged || values.length < 2) continue
    const accepted = new Set(values.map(normalize))
    for (const frame of frames) {
      if (!names.some(name => accepted.has(normalize(frame.fields[name])))) excludeIds.add(frame.screen_id)
    }
  }
  return { filters, excludeIds: [...excludeIds] }
}

// This is the inventory extent, not a verified administrative boundary.
export function inventoryBounds(frames) {
  const points = frames.map(f => [f.lat, f.lon]).filter(([lat, lon]) =>
    Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180)
  if (!points.length) return ''
  const lat = points.map(p => p[0]), lon = points.map(p => p[1])
  return JSON.stringify([lat.reduce((a,b)=>Math.min(a,b)), lon.reduce((a,b)=>Math.min(a,b)), lat.reduce((a,b)=>Math.max(a,b)), lon.reduce((a,b)=>Math.max(a,b))])
}
