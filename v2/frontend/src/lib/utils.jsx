export function highlightSnippet(text, query) {
  if (!text || !query) return text
  const words = query.split(/\s+/).filter((w) => w.length > 3).slice(0, 5)
  if (!words.length) return text
  const lowerWords = new Set(words.map((w) => w.toLowerCase()))
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi')
  const parts = text.split(pattern)
  return parts.map((part, i) =>
    lowerWords.has(part.toLowerCase()) ? <mark key={i}>{part}</mark> : <span key={i}>{part}</span>
  )
}

export function confidenceLevel(score) {
  if (score == null) return { label: 'Unverified', cls: 'neutral', pct: null }
  if (score >= 0) return { label: 'Strong match', cls: 'high', pct: Math.min(100, Math.round(70 + score * 10)) }
  if (score >= -2) return { label: 'Moderate', cls: 'medium', pct: Math.round(45 + (score + 2) * 15) }
  return { label: 'Weak match', cls: 'low', pct: Math.max(10, Math.round(30 + score * 5)) }
}

export function riskColor(level) {
  const map = { high: 'risk-high', medium: 'risk-medium', low: 'risk-low', green: 'risk-ok' }
  return map[String(level).toLowerCase()] || 'risk-neutral'
}

export function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}
