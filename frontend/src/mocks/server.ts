// In-memory mock backend. Same shapes as the real API (src/lib/types.ts).
import type { CreateWorkspaceRequest, Workspace } from '../lib/types'
import * as data from './data'

const state = {
  workspaces: structuredClone(data.workspaces),
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

export async function listWorkspaces(): Promise<Workspace[]> {
  await delay(250)
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
  return structuredClone(ws)
}
