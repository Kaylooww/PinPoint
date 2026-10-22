// In-memory mock backend. Same shapes as the real API (src/lib/types.ts).
import type { AskResponse, AskResult, CreateWorkspaceRequest, FileItem, FileType, Folder, HistoryDetail, HistoryItem, KnowledgeStats, Note, Workspace } from '../lib/types'
import * as data from './data'

const state = {
  workspaces: structuredClone(data.workspaces),
  files: { 'reyes-partners': structuredClone(data.reyesFiles) } as Record<string, FileItem[]>,
  // Polls seen per file while queued/parsing; drives the fake progress.
  ticks: {} as Record<string, number>,
  notes: { 'reyes-partners': structuredClone(data.reyesNotes) } as Record<string, Note[]>,
  folders: {} as Record<string, Folder[]>,
  history: {} as Record<string, (HistoryDetail & { id: string })[]>,
}

export function delay(ms = 300): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function slugify(name: string): string {
  const base = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'workspace'
  let id = base
  for (let i = 2; state.workspaces.some((w) => w.id === id); i++) id = `${base}-${i}`
  return id
}

export class MockError extends Error {}

function findWorkspace(id: string): Workspace {
  const ws = state.workspaces.find((w) => w.id === id)
  if (!ws) throw new MockError('Workspace not found')
  return ws
}

function filesOf(ws: string): FileItem[] {
  findWorkspace(ws)
  state.files[ws] ??= []
  return state.files[ws]
}

function syncCount(ws: string): void {
  const w = findWorkspace(ws)
  if (state.files[ws]) w.file_count = state.files[ws].length
}

export async function listWorkspaces(): Promise<Workspace[]> {
  await delay(250)
  for (const ws of Object.keys(state.files)) syncCount(ws)
  return structuredClone(state.workspaces)
}

export async function getWorkspace(id: string): Promise<Workspace> {
  await delay(150)
  return structuredClone(findWorkspace(id))
}

export async function createWorkspace(body: CreateWorkspaceRequest): Promise<Workspace> {
  await delay(400)
  const ws: Workspace = {
    id: slugify(body.name),
    name: body.name,
    industry: body.industry,
    file_count: 0,
    updated_at: new Date().toISOString(),
  }
  state.workspaces.unshift(ws)
  state.files[ws.id] = []
  return structuredClone(ws)
}

/** Each poll moves queued files to parsing and parsing files to ready (Board_Resolution fails over to ready too). */
function advance(file: FileItem): void {
  if (file.status !== 'queued' && file.status !== 'parsing') return
  const tick = (state.ticks[file.id] = (state.ticks[file.id] ?? 0) + 1)
  if (file.status === 'queued' && tick >= 2) {
    file.status = 'parsing'
    file.progress_label = 'Reading pages…'
    state.ticks[file.id] = 0
  } else if (file.status === 'parsing' && tick >= 3) {
    file.status = 'ready'
    delete file.progress_label
    if (file.pages === 0) file.pages = file.type === 'image' ? 1 : 3
  }
}

export async function listFiles(ws: string): Promise<FileItem[]> {
  await delay(200)
  const files = filesOf(ws)
  files.forEach(advance)
  return structuredClone(files)
}

const TYPES: Record<string, FileType> = {
  pdf: 'pdf',
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  webp: 'image',
  docx: 'doc',
  md: 'doc',
  txt: 'doc',
  xlsx: 'sheet',
  csv: 'sheet',
  pptx: 'slides',
}

export async function uploadFiles(ws: string, files: File[]): Promise<FileItem[]> {
  await delay(500)
  const added: FileItem[] = files.map((file) => ({
    id: `up-${crypto.randomUUID().slice(0, 8)}`,
    name: file.name,
    type: TYPES[file.name.split('.').pop()?.toLowerCase() ?? ''] ?? 'other',
    pages: 0,
    size_bytes: file.size,
    status: 'queued',
    source: 'upload',
  }))
  filesOf(ws).unshift(...added)
  syncCount(ws)
  findWorkspace(ws).updated_at = new Date().toISOString()
  return structuredClone(added)
}

export async function ask(ws: string, question: string, threadId?: string): Promise<AskResult> {
  const response = await answer(ws, question)
  const history = (state.history[ws] ??= [])
  const thread_id = threadId && history.some((h) => h.thread_id === threadId) ? threadId : crypto.randomUUID().slice(0, 12)
  const id = crypto.randomUUID().slice(0, 12)
  history.push({ id, question, response, thread_id, created_at: new Date().toISOString(), saved: response.status === 'answered' })
  return { ...structuredClone(response), thread_id, history_id: id }
}

async function answer(ws: string, question: string): Promise<AskResponse> {
  const started = performance.now()
  await delay(1200)
  const ready = filesOf(ws).filter((f) => f.status === 'ready').length
  const q = question.toLowerCase()
  const elapsed_ms = Math.round(performance.now() - started)

  const note = (state.notes[ws] ?? []).find((n) => /email|update|contact|phone/.test(q) && /email|phone/.test(n.text.toLowerCase()))
  if (note) {
    return {
      status: 'answered',
      answer: [{ text: 'The client prefers to be updated by email rather than by phone.', sources: ['c1'] }],
      citations: [
        { id: 'c1', number: 1, kind: 'note', file_id: note.id, file_name: 'Note', page: 1, locator: `note:${note.id}`, text: note.text, crop_url: null },
      ],
      searched_files: ready,
      elapsed_ms,
    }
  }
  if (!q.includes('color') && /deadline|santos|filing|due|extension/.test(q)) {
    return { ...structuredClone(data.santosAnswer), searched_files: ready, elapsed_ms }
  }
  return {
    status: 'not_found',
    answer: [],
    citations: [],
    reason: `None of the ${ready} files in this workspace mention this.`,
    searched_files: ready,
    elapsed_ms,
  }
}

export async function listNotes(ws: string): Promise<Note[]> {
  await delay(200)
  findWorkspace(ws)
  return structuredClone(state.notes[ws] ?? [])
}

export async function addNote(ws: string, text: string): Promise<Note> {
  await delay(300)
  findWorkspace(ws)
  const note: Note = { id: crypto.randomUUID().slice(0, 12), text: text.trim(), created_at: new Date().toISOString() }
  ;(state.notes[ws] ??= []).unshift(note)
  return structuredClone(note)
}

export async function deleteNote(ws: string, noteId: string): Promise<void> {
  await delay(200)
  state.notes[ws] = (state.notes[ws] ?? []).filter((n) => n.id !== noteId)
}

/** A connected folder finishes scanning on the next poll and brings in three files. */
export async function listFolders(ws: string): Promise<Folder[]> {
  await delay(200)
  findWorkspace(ws)
  for (const folder of state.folders[ws] ?? []) {
    if (folder.status !== 'scanning') continue
    const names = ['Engagement_Letter.pdf', 'Hearing_Notice.jpg', 'Billing_2026.xlsx']
    if (!filesOf(ws).some((f) => f.source_path?.startsWith(folder.path))) {
      filesOf(ws).unshift(
        ...names.map((name): FileItem => ({
          id: `fd-${crypto.randomUUID().slice(0, 8)}`,
          name,
          type: TYPES[name.split('.').pop()!.toLowerCase()] ?? 'other',
          pages: 0,
          size_bytes: 400 * 1024,
          status: 'queued',
          source: 'folder',
          source_path: `${folder.path}/${name}`,
        })),
      )
      syncCount(ws)
    }
    folder.status = 'ready'
    folder.file_count = names.length
    folder.last_scanned_at = new Date().toISOString()
  }
  return structuredClone(state.folders[ws] ?? [])
}

export async function connectFolder(ws: string, path: string): Promise<Folder> {
  await delay(400)
  findWorkspace(ws)
  if (!path.startsWith('/')) throw new MockError('Use a full folder path, for example /Users/you/Documents/Client.')
  const folder: Folder = { id: crypto.randomUUID().slice(0, 12), path, file_count: 0, status: 'scanning', last_scanned_at: null }
  ;(state.folders[ws] ??= []).push(folder)
  return structuredClone(folder)
}

export async function rescanFolder(ws: string, folderId: string): Promise<Folder> {
  await delay(300)
  const folder = (state.folders[ws] ?? []).find((f) => f.id === folderId)
  if (!folder) throw new MockError('Folder not found')
  folder.status = 'scanning'
  return structuredClone(folder)
}

export async function disconnectFolder(ws: string, folderId: string): Promise<void> {
  await delay(300)
  const folder = (state.folders[ws] ?? []).find((f) => f.id === folderId)
  state.folders[ws] = (state.folders[ws] ?? []).filter((f) => f.id !== folderId)
  if (folder) state.files[ws] = filesOf(ws).filter((f) => !f.source_path?.startsWith(folder.path))
  syncCount(ws)
}

function historyItem(h: HistoryDetail & { id: string }): HistoryItem {
  const preview = h.response.answer.map((a) => a.text).join(' ') || h.response.reason || ''
  return {
    id: h.id,
    question: h.question,
    status: h.response.status,
    answer_preview: preview.slice(0, 160),
    thread_id: h.thread_id,
    created_at: h.created_at,
    saved: h.saved,
  }
}

export async function listHistory(ws: string): Promise<HistoryItem[]> {
  await delay(200)
  return (state.history[ws] ?? []).map(historyItem).reverse()
}

export async function getHistory(ws: string, historyId: string): Promise<HistoryDetail> {
  await delay(200)
  const h = (state.history[ws] ?? []).find((x) => x.id === historyId)
  if (!h) throw new MockError('Not found in history')
  const { id: _id, ...detail } = structuredClone(h)
  return detail
}

export async function setSaved(ws: string, historyId: string, saved: boolean): Promise<HistoryItem> {
  await delay(200)
  const h = (state.history[ws] ?? []).find((x) => x.id === historyId)
  if (!h) throw new MockError('Not found in history')
  h.saved = saved
  return historyItem(h)
}

export async function knowledge(ws: string): Promise<KnowledgeStats> {
  await delay(200)
  const files = filesOf(ws)
  const ready = files.filter((f) => f.status === 'ready')
  const pages = ready.reduce((n, f) => n + f.pages, 0)
  return {
    files: files.length,
    ready_files: ready.length,
    pages,
    passages: pages * 8,
    notes: (state.notes[ws] ?? []).length,
    folders: (state.folders[ws] ?? []).length,
    last_indexed_at: new Date(Date.now() - 2 * 60_000).toISOString(),
  }
}
