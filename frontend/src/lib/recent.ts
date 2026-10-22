export type RecentQuestion = { question: string; asked_at: string }

const key = (ws: string) => `pinpoint-recent-${ws}`
const MAX = 8

export function getRecent(ws: string): RecentQuestion[] {
  try {
    const raw = JSON.parse(localStorage.getItem(key(ws)) ?? '[]') as unknown
    return Array.isArray(raw) ? (raw as RecentQuestion[]).filter((r) => typeof r?.question === 'string') : []
  } catch {
    return []
  }
}

export function addRecent(ws: string, question: string): RecentQuestion[] {
  const next = [
    { question, asked_at: new Date().toISOString() },
    ...getRecent(ws).filter((r) => r.question.toLowerCase() !== question.toLowerCase()),
  ].slice(0, MAX)
  try {
    localStorage.setItem(key(ws), JSON.stringify(next))
  } catch {
    // Not remembered on this device.
  }
  return next
}
