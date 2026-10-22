import { createContext, useContext } from 'react'
import type { Workspace } from './types'

export type WorkspacesContextValue = {
  workspaces: Workspace[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export const WorkspacesContext = createContext<WorkspacesContextValue | null>(null)

export function useWorkspaces(): WorkspacesContextValue {
  const value = useContext(WorkspacesContext)
  if (!value) throw new Error('useWorkspaces must be used inside WorkspacesProvider')
  return value
}

const LAST_KEY = 'pinpoint-last-workspace'

export function getLastWorkspaceId(): string | null {
  try {
    return localStorage.getItem(LAST_KEY)
  } catch {
    return null
  }
}

export function setLastWorkspaceId(id: string): void {
  try {
    localStorage.setItem(LAST_KEY, id)
  } catch {
    // Not remembered; the sidebar falls back to the first workspace.
  }
}
