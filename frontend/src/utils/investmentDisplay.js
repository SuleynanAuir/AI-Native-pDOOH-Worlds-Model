export const SCREEN_PAGE_SIZE = 5
export function planningDays(finance) {
  const n = Number(finance?.planning_days ?? finance?.days)
  return Number.isFinite(n) && n > 0 ? n : null
}
export function dailyInvestment(row, days) {
  return days && row.recommended_amount != null ? Number(row.recommended_amount) / days : null
}
export function investmentTotals(rows) {
  let spend = 0, impressions = 0
  for (const row of rows) {
    const amount = Number(row.recommended_amount), exposure = Number(row.recommended_exposures)
    if (row.recommended_amount != null && Number.isFinite(amount)) spend += amount
    if (row.recommended_exposures != null && Number.isFinite(exposure)) impressions += exposure
  }
  return { spend, impressions, cpm: impressions > 0 ? spend * 1000 / impressions : null }
}
export function histogram(values, count = 8) {
  const valid = values.filter(v => v != null && Number.isFinite(Number(v)) && Number(v) >= 0).map(Number)
  if (!valid.length) return []
  const min = Math.min(...valid), max = Math.max(...valid)
  if (min === max) return [{ low: min, high: max, count: valid.length }]
  const width = (max - min) / count
  const bins = Array.from({ length: count }, (_, i) => ({ low: min + i * width, high: min + (i + 1) * width, count: 0 }))
  for (const value of valid) bins[Math.min(count - 1, Math.floor((value - min) / width))].count++
  return bins
}
