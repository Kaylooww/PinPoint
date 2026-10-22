import type { Workspace } from '../lib/types'

const now = Date.now()
const hoursAgo = (h: number) => new Date(now - h * 3_600_000).toISOString()

// Workspaces from Figma 03 Workspaces (6:172).
export const workspaces: Workspace[] = [
  { id: 'reyes-partners', name: 'Reyes & Partners', industry: 'Law office', file_count: 6, updated_at: hoursAgo(2) },
  { id: 'santos-realty', name: 'Santos Realty', industry: 'Real estate', file_count: 12, updated_at: hoursAgo(26) },
  { id: 'dela-cruz-cpa', name: 'Dela Cruz & Co. CPA', industry: 'Accounting', file_count: 18, updated_at: hoursAgo(72) },
  { id: 'harbor-insurance', name: 'Harbor Insurance', industry: 'Insurance', file_count: 7, updated_at: hoursAgo(170) },
  { id: 'villanueva-law', name: 'Villanueva Law Office', industry: 'Law office', file_count: 31, updated_at: hoursAgo(240) },
]
