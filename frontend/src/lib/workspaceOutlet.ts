import type { ReactNode } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { Workspace } from './types'

export type WorkspaceOutlet = {
  workspace: Workspace | undefined
  /** Lets a tab put its own buttons in the workspace header (e.g. "Add files"). */
  setActions: (actions: ReactNode) => void
}

export function useWorkspaceOutlet(): WorkspaceOutlet {
  return useOutletContext<WorkspaceOutlet>()
}
