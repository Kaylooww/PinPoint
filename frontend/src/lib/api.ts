import * as mock from '../mocks/server'
import type {
  AskResult,
  CreateWorkspaceRequest,
  FileItem,
  FileText,
  Folder,
  HistoryDetail,
  HistoryItem,
  KnowledgeStats,
  Note,
  Workspace,
} from './types'

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'
const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError('Could not reach the PinPoint server.', 0)
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Keep the generic message.
    }
    throw new ApiError(message, res.status)
  }
  return (await res.json()) as T
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

/** URL of a file's original, for <iframe>/<img>/fetch. null in mock mode (no originals). */
export function rawUrl(ws: string, fileId: string): string | null {
  return USE_MOCKS ? null : `${API_BASE}/api/workspaces/${encodeURIComponent(ws)}/files/${encodeURIComponent(fileId)}/raw`
}

/** Absolute URL for a path returned by the API (crops), or a local mock asset. */
export function assetUrl(path: string): string {
  return USE_MOCKS || /^https?:/.test(path) ? path : `${API_BASE}${path}`
}

export const api = {
  listWorkspaces: (): Promise<Workspace[]> =>
    USE_MOCKS ? mock.listWorkspaces() : request('/api/workspaces'),

  getWorkspace: async (id: string): Promise<Workspace> => {
    if (USE_MOCKS) return mock.getWorkspace(id)
    // The contract has no single-workspace route; pick it from the list.
    const all = await request<Workspace[]>('/api/workspaces')
    const ws = all.find((w) => w.id === id)
    if (!ws) throw new ApiError('Workspace not found', 404)
    return ws
  },

  createWorkspace: (body: CreateWorkspaceRequest): Promise<Workspace> =>
    USE_MOCKS ? mock.createWorkspace(body) : request('/api/workspaces', json('POST', body)),

  listFiles: (ws: string): Promise<FileItem[]> =>
    USE_MOCKS ? mock.listFiles(ws) : request(`/api/workspaces/${encodeURIComponent(ws)}/files`),

  uploadFiles: (ws: string, files: File[]): Promise<FileItem[]> => {
    if (USE_MOCKS) return mock.uploadFiles(ws, files)
    const body = new FormData()
    for (const file of files) body.append('files', file, file.name)
    return request(`/api/workspaces/${encodeURIComponent(ws)}/files`, { method: 'POST', body })
  },

  ask: (ws: string, question: string, threadId?: string): Promise<AskResult> =>
    USE_MOCKS
      ? mock.ask(ws, question, threadId)
      : request(
          `/api/workspaces/${encodeURIComponent(ws)}/ask`,
          json('POST', threadId ? { question, thread_id: threadId } : { question }),
        ),

  listNotes: (ws: string): Promise<Note[]> =>
    USE_MOCKS ? mock.listNotes(ws) : request(`/api/workspaces/${encodeURIComponent(ws)}/notes`),

  addNote: (ws: string, text: string): Promise<Note> =>
    USE_MOCKS ? mock.addNote(ws, text) : request(`/api/workspaces/${encodeURIComponent(ws)}/notes`, json('POST', { text })),

  deleteNote: async (ws: string, noteId: string): Promise<void> => {
    if (USE_MOCKS) return mock.deleteNote(ws, noteId)
    await request(`/api/workspaces/${encodeURIComponent(ws)}/notes/${encodeURIComponent(noteId)}`, { method: 'DELETE' })
  },

  listFolders: (ws: string): Promise<Folder[]> =>
    USE_MOCKS ? mock.listFolders(ws) : request(`/api/workspaces/${encodeURIComponent(ws)}/folders`),

  connectFolder: (ws: string, path: string): Promise<Folder> =>
    USE_MOCKS ? mock.connectFolder(ws, path) : request(`/api/workspaces/${encodeURIComponent(ws)}/folders`, json('POST', { path })),

  rescanFolder: (ws: string, folderId: string): Promise<Folder> =>
    USE_MOCKS
      ? mock.rescanFolder(ws, folderId)
      : request(`/api/workspaces/${encodeURIComponent(ws)}/folders/${encodeURIComponent(folderId)}/rescan`, { method: 'POST' }),

  disconnectFolder: async (ws: string, folderId: string): Promise<void> => {
    if (USE_MOCKS) return mock.disconnectFolder(ws, folderId)
    await request(`/api/workspaces/${encodeURIComponent(ws)}/folders/${encodeURIComponent(folderId)}`, { method: 'DELETE' })
  },

  listHistory: (ws: string): Promise<HistoryItem[]> =>
    USE_MOCKS ? mock.listHistory(ws) : request(`/api/workspaces/${encodeURIComponent(ws)}/history`),

  getHistory: (ws: string, historyId: string): Promise<HistoryDetail> =>
    USE_MOCKS
      ? mock.getHistory(ws, historyId)
      : request(`/api/workspaces/${encodeURIComponent(ws)}/history/${encodeURIComponent(historyId)}`),

  setSaved: (ws: string, historyId: string, saved: boolean): Promise<HistoryItem> =>
    USE_MOCKS
      ? mock.setSaved(ws, historyId, saved)
      : request(`/api/workspaces/${encodeURIComponent(ws)}/history/${encodeURIComponent(historyId)}`, json('PATCH', { saved })),

  knowledge: (ws: string): Promise<KnowledgeStats> =>
    USE_MOCKS ? mock.knowledge(ws) : request(`/api/workspaces/${encodeURIComponent(ws)}/knowledge`),

  getFileText: (ws: string, fileId: string): Promise<FileText> =>
    USE_MOCKS
      ? mock.getFileText(ws, fileId)
      : request(`/api/workspaces/${encodeURIComponent(ws)}/files/${encodeURIComponent(fileId)}/text`),
}
