import type { AskResponse, FileItem, Note, Workspace } from '../lib/types'

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

const MB = 1024 * 1024

// Files from Figma 04 Files (6:435), newest first.
export const reyesFiles: FileItem[] = [
  { id: 'f1', name: 'Lease_Agreement_Scan.pdf', type: 'pdf', pages: 12, size_bytes: 2.4 * MB, status: 'ready', source: 'upload' },
  { id: 'f2', name: 'Receipt_0412.jpg', type: 'image', pages: 1, size_bytes: 860 * 1024, status: 'ready', source: 'upload' },
  {
    id: 'f3',
    name: 'Q3_Invoices.xlsx',
    type: 'sheet',
    pages: 3,
    size_bytes: 410 * 1024,
    status: 'parsing',
    progress_label: 'Reading sheet 2 of 3',
    source: 'upload',
  },
  { id: 'f4', name: 'Santos_Motion_Extension.pdf', type: 'pdf', pages: 4, size_bytes: 1.1 * MB, status: 'ready', source: 'upload' },
  { id: 'f5', name: 'Board_Resolution_Photo.jpg', type: 'image', pages: 1, size_bytes: 1.9 * MB, status: 'queued', source: 'upload' },
  {
    id: 'f6',
    name: 'Client_Intake_Form.docx',
    type: 'doc',
    pages: 0,
    size_bytes: 320 * 1024,
    status: 'failed',
    error: "Couldn't read this file. Try re-uploading a clearer copy.",
    source: 'upload',
  },
]

// The Figma example answer (05 Ask, 7:542).
export const santosAnswer: Omit<AskResponse, 'searched_files' | 'elapsed_ms'> = {
  status: 'answered',
  answer: [
    { text: 'The response for the Santos case is due on March 14, 2026.', sources: ['c1'] },
    { text: 'This already includes the 15-day extension the court granted on February 27.', sources: ['c2'] },
  ],
  citations: [
    {
      id: 'c1',
      number: 1,
      kind: 'file',
      file_id: 'f4',
      file_name: 'Santos_Motion_Extension.pdf',
      page: 2,
      locator: 'doc:mock01/tier:basic/page:2/block:4',
      text: 'WHEREFORE, the Court grants petitioner fifteen (15) days, until 14 March 2026, within which to file the required response.',
      excerpt: 'until 14 March 2026, within which to file the required response',
      crop_url: '/mock-crops/santos-motion.png',
    },
    {
      id: 'c2',
      number: 2,
      kind: 'file',
      file_id: 'f7',
      file_name: 'Court_Order_0227.jpg',
      page: 1,
      locator: 'doc:mock02/tier:basic/page:1/block:2',
      text: 'ORDER. Acting on the motion, the extension is granted on 27 February 2026 for a period of fifteen days.',
      excerpt: 'the extension is granted on 27 February 2026 for a period of fifteen days',
      crop_url: '/mock-crops/court-order.png',
    },
  ],
}

export const reyesNotes: Note[] = [
  { id: 'n1', text: 'The client prefers updates by email, not phone calls.', created_at: hoursAgo(5) },
]
