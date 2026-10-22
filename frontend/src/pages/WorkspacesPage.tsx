import { Clock, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../components/Button'
import { NewWorkspaceDialog } from '../components/NewWorkspaceDialog'
import { WorkspaceCard } from '../components/WorkspaceCard'
import { api } from '../lib/api'
import { timeAgo } from '../lib/format'
import type { CreateWorkspaceRequest, HistoryItem } from '../lib/types'
import { useWorkspaces } from '../lib/workspaces'

type RecentRow = HistoryItem & { workspaceId: string; workspaceName: string }

// Figma 03 Workspaces (6:172): header, grid of workspace cards, dashed New workspace card, recent questions.
export function WorkspacesPage() {
  const navigate = useNavigate()
  const { workspaces, loading, error, refresh } = useWorkspaces()
  const [creating, setCreating] = useState(false)
  const [recent, setRecent] = useState<RecentRow[] | null>(null)
  const totalFiles = workspaces.reduce((n, w) => n + w.file_count, 0)

  useEffect(() => {
    if (!workspaces.length) return
    let alive = true
    Promise.all(
      workspaces.map((w) =>
        api.listHistory(w.id).then(
          (items) => items.map((i) => ({ ...i, workspaceId: w.id, workspaceName: w.name })),
          () => [] as RecentRow[],
        ),
      ),
    ).then((lists) => {
      if (!alive) return
      const seen = new Set<string>()
      const rows = lists
        .flat()
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .filter((r) => {
          const key = `${r.workspaceId}:${r.question.toLowerCase()}`
          return !seen.has(key) && seen.add(key)
        })
      setRecent(rows.slice(0, 5))
    })
    return () => {
      alive = false
    }
  }, [workspaces])

  const create = async (body: CreateWorkspaceRequest) => {
    const ws = await api.createWorkspace(body)
    await refresh()
    navigate(`/w/${ws.id}/files`)
  }

  return (
    <div className="flex flex-col gap-7 pt-1">
      <header className="flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-h1 text-text">Workspaces</h1>
          <p className="text-small text-muted">
            One workspace per client · {workspaces.length} client{workspaces.length === 1 ? '' : 's'} · {totalFiles} file
            {totalFiles === 1 ? '' : 's'}
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>New workspace</Button>
      </header>

      {error && !workspaces.length ? (
        <div role="alert" className="flex items-center gap-3 rounded-card border border-border bg-danger-soft px-5 py-4">
          <p className="flex-1 text-small text-text">{error}</p>
          <Button variant="secondary" onClick={() => void refresh()}>
            Retry
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-5">
          {loading && !workspaces.length
            ? [0, 1, 2].map((i) => <div key={i} className="h-[178px] animate-pulse rounded-card border border-border bg-surface" />)
            : workspaces.map((w) => <WorkspaceCard key={w.id} workspace={w} />)}
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex min-h-[178px] flex-col items-center justify-center gap-2.5 rounded-card border border-dashed border-border text-muted hover:border-accent hover:text-text"
          >
            <span className="flex size-9 items-center justify-center rounded-pill bg-surface-muted">
              <Plus size={18} strokeWidth={1.75} />
            </span>
            <span className="text-body font-medium">New workspace</span>
          </button>
        </div>
      )}

      <section className="flex flex-col gap-3" aria-label="Recent questions">
        <h2 className="text-h3 text-text">Recent questions</h2>
        {recent === null ? (
          <div className="h-[52px] animate-pulse rounded-card bg-surface-muted" />
        ) : recent.length === 0 ? (
          <p className="text-small text-muted">Questions you ask in any workspace show up here.</p>
        ) : (
          <ul className="flex flex-col overflow-hidden rounded-card border border-border bg-surface">
            {recent.map((r) => (
              <li key={r.id} className="border-b border-border last:border-b-0">
                <Link
                  to={`/w/${r.workspaceId}/ask?h=${r.id}`}
                  className="flex items-center gap-3 px-4 py-3.5 hover:bg-surface-muted"
                >
                  <Clock size={16} strokeWidth={1.75} className="shrink-0 text-muted" />
                  <span className="min-w-0 flex-1 truncate text-body text-text">{r.question}</span>
                  <span className="shrink-0 text-label text-muted">{r.workspaceName}</span>
                  <span className="shrink-0 text-label text-muted">{timeAgo(r.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {creating && <NewWorkspaceDialog onCreate={create} onClose={() => setCreating(false)} />}
    </div>
  )
}
