// Mirrors the API contract in docs/ARCHITECTURE.md (including "API additions").
// Change this file together with the doc and the backend.

export type Workspace = {
  id: string
  name: string
  industry: string
  file_count: number
  updated_at: string
}

export type FileType = 'pdf' | 'image' | 'doc' | 'sheet' | 'slides' | 'other'
export type FileStatus = 'queued' | 'parsing' | 'ready' | 'failed'
export type FileSource = 'upload' | 'folder'

export type FileItem = {
  id: string
  name: string
  type: FileType
  pages: number
  size_bytes: number
  status: FileStatus
  progress_label?: string
  error?: string
  source: FileSource
  source_path?: string
}

export type CitationKind = 'file' | 'note'

export type Citation = {
  id: string
  number: number
  kind: CitationKind
  file_id: string
  file_name: string
  page: number
  locator: string
  /** Full cleaned block text, with line breaks. */
  text: string
  /** Short supporting passage, always literally from the block. */
  excerpt: string
  crop_url: string | null
  /** Rows of cells when the block is a table. */
  table?: string[][]
}

export type AnswerKind = 'paragraph' | 'bullet' | 'numbered' | 'heading'

export type AnswerSentence = {
  /** Missing in answers saved before structured answers: treat as "paragraph". */
  kind?: AnswerKind
  text: string
  /** Empty only for "heading" items, which are labels, not claims. */
  sources: string[]
}

export type AskStatus = 'answered' | 'not_found'

export type Suggestion = {
  /** e.g. "Did you mean the invoice dated April 15, 2026?" */
  text: string
  /** The question to ask instead. */
  question: string
}

export type AskResponse = {
  status: AskStatus
  answer: AnswerSentence[]
  citations: Citation[]
  reason?: string
  searched_files: number
  elapsed_ms: number
  /** not_found only: up to 3 close passages (with crops). */
  near_matches?: Citation[]
  /** not_found only: a validated "Did you mean…?" (its dates and numbers are in near_matches). */
  suggestion?: Suggestion
}

export type AskRequest = {
  question: string
  thread_id?: string
}

export type AskResult = AskResponse & {
  thread_id: string
  history_id: string
}

export type HistoryItem = {
  id: string
  question: string
  status: AskStatus
  answer_preview: string
  thread_id: string
  created_at: string
  saved: boolean
}

export type HistoryDetail = {
  question: string
  response: AskResponse
  thread_id: string
  created_at: string
  saved: boolean
}

export type Note = {
  id: string
  text: string
  created_at: string
}

export type FolderStatus = 'scanning' | 'ready' | 'failed'

export type Folder = {
  id: string
  path: string
  file_count: number
  status: FolderStatus
  last_scanned_at: string | null
  error?: string
}

export type KnowledgeStats = {
  files: number
  ready_files: number
  pages: number
  passages: number
  notes: number
  folders: number
  last_indexed_at: string | null
}

export type CreateWorkspaceRequest = {
  name: string
  industry: string
}

export type FileTextBlock = {
  text: string
  locator: string
  table?: string[][]
  /** [x0, y0, x1, y1], normalized 0-1 on the page image. */
  bbox?: number[]
}

export type FileText = {
  id: string
  name: string
  type: FileType
  page_count: number
  pages: { page: number; blocks: FileTextBlock[] }[]
}
