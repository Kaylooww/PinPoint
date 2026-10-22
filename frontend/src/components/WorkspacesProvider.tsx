import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import type { Workspace } from '../lib/types'
import { WorkspacesContext } from '../lib/workspaces'

export function WorkspacesProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(
    () =>
      api.listWorkspaces().then(
        (list) => {
          setWorkspaces(list)
          setError(null)
          setLoading(false)
        },
        (e: unknown) => {
          setError(e instanceof Error ? e.message : 'Could not load workspaces.')
          setLoading(false)
        },
      ),
    [],
  )

  useEffect(() => {
    void load()
  }, [load])

  const refresh = load

  const value = useMemo(() => ({ workspaces, loading, error, refresh }), [workspaces, loading, error, refresh])
  return <WorkspacesContext.Provider value={value}>{children}</WorkspacesContext.Provider>
}
