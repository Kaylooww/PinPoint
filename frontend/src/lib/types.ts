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
  text: string
  crop_url: string | null
}

export type AnswerSentence = {
  text: string
  sources: string[]
}

export type AskStatus = 'answered' | 'not_found'

export type AskResponse = {
  status: AskStatus
  answer: AnswerSentence[]
  citations: Citation[]
  reason?: string
  searched_files: number
  elapsed_ms: number
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
