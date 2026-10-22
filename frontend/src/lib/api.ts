import * as mock from '../mocks/server'
import type { CreateWorkspaceRequest, Workspace } from './types'

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
}
