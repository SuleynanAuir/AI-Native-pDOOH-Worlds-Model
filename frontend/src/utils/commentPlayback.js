// Excerpts of saved synthetic comments, released only after a pedestrian encounter.
// A shared session ledger prevents repetition across scenes, seeks and day loops.
export function shortComment(value, limit = 44) {
  const text = String(value || '').replace(/\s+/g, ' ').replace(/^[“”"「」]+|[“”"「」]+$/g, '').trim()
  if (Array.from(text).length <= limit) return text
  // Prefer a complete decision-related sentence over a cut-off scene description.
  const sentences = text.match(/[^。！？；]+[。！？；]?/gu) || []
  const candidates = sentences.filter(s => Array.from(s).length >= 12 && Array.from(s).length <= limit)
  const relevance = s => (s.match(/价格|预算|需要|需求|试穿|舒适|比较|考虑|购买|适合|关注|想知道/g) || []).length * 12 + Array.from(s).length
  if (candidates.length) return candidates.sort((a,b) => relevance(b)-relevance(a))[0].trim()
  const prefix = Array.from(text).slice(0, limit - 1).join('')
  const boundary = Math.max(prefix.lastIndexOf('。'), prefix.lastIndexOf('！'), prefix.lastIndexOf('？'), prefix.lastIndexOf('；'))
  return boundary >= 24 ? prefix.slice(0, boundary + 1) : prefix.replace(/[，、；：\s]+$/g, '') + '…'
}
export const commentKey = text => text.normalize('NFKC').toLocaleLowerCase().replace(/[\p{P}\p{Z}\s]/gu, '')
export function commentTimeline(events, narrative) {
  const groups = Object.fromEntries((narrative?.groups || []).map(g => [g.group_id, g.name]))
  const people = new Map(Object.entries(narrative?.agents || {}).map(([id, p]) => {
    const text = shortComment(p.possible_comment)
    return [id, { agentId: Number(id), name: p.name, group: groups[p.group_id] || '代表画像', text, key: commentKey(text), interest: p.interest }]
  }))
  return (events || []).flatMap(e => {
    const id = e.kind === 'pedestrian' ? String(e.actor_id).match(/^p-(\d+)-/)?.[1] : null
    const person = people.get(id), time = (e.round - 1) * 60 + e.minute
    return person?.key && Number.isFinite(time) ? [{ ...person, time, eventId: e.id }] : []
  }).sort((a, b) => a.time - b.time)
}
function upperBound(rows, time) {
  let low = 0, high = rows.length
  while (low < high) { const mid = (low + high) >>> 1; if (rows[mid].time <= time) low = mid + 1; else high = mid }
  return low
}
export function createCommentQueue(rows, seen = new Set()) {
  let previous = null, pending = [], lastGroup = ''
  return {
    offer(time) {
      const rewound = previous != null && time < previous
      const end = upperBound(rows, time)
      const start = previous == null || rewound || time - previous > 10 ? Math.max(0, end - 80) : upperBound(rows, previous)
      if (rewound) pending = []
      const keys = new Set(pending.map(r => r.key)), incoming = []
      // Recent encounters take priority after loading or seeking, without future comments.
      for (const row of rows.slice(start, end).reverse()) {
        if (!seen.has(row.key) && !keys.has(row.key)) { incoming.push(row); keys.add(row.key) }
      }
      pending = [...incoming, ...pending].slice(0, 40)
      previous = time
      return rewound
    },
    take() {
      pending = pending.filter(r => !seen.has(r.key))
      if (!pending.length) return null
      const different = pending.findIndex(r => r.group !== lastGroup)
      const row = pending.splice(different < 0 ? 0 : different, 1)[0]
      seen.add(row.key); lastGroup = row.group
      return row
    },
  }
}
