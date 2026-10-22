import { Fragment, useMemo, useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { Button } from '../components/Button'
import type { WorkspaceOutlet } from '../lib/workspaceOutlet'
import { useWorkspaces } from '../lib/workspaces'

const TABS = [
  { to: 'files', label: 'Files' },
  { to: 'ask', label: 'Ask' },
  { to: 'memory', label: 'Memory' },
] as const

// Workspace header from Figma 04 Files (6:528): breadcrumb, title, industry pill, tabs.
export function WorkspaceLayout() {
  const { id = '' } = useParams()
  const { workspaces, loading } = useWorkspaces()
  const ws = workspaces.find((w) => w.id === id)
  const [actions, setActions] = useState<ReactNode>(null)
  const outlet = useMemo<WorkspaceOutlet>(() => ({ workspace: ws, setActions }), [ws])

  if (!loading && !ws) {
    return (
      <div className="flex flex-col items-start gap-2">
        <h1 className="text-h1">Workspace not found</h1>
        <p className="text-small text-muted">It may have been removed.</p>
        <Link to="/workspaces" className="text-body font-medium text-accent hover:text-accent-hover">
          Back to workspaces
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-col gap-4">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-label">
          <Link to="/workspaces" className="text-muted hover:text-text">
            Workspaces
          </Link>
          <span className="text-muted">/</span>
          <span className="text-text">{ws?.name ?? '…'}</span>
        </nav>

        <div className="flex min-h-[42px] items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="truncate text-h1 text-text">{ws?.name ?? ''}</h1>
            {ws && (
              <span className="shrink-0 rounded-pill bg-surface-muted px-2 py-[3px] text-label text-muted">{ws.industry}</span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {/* Sharing is out of scope for the MVP: static button. */}
            <Button variant="secondary" title="Sharing is not available in this demo">
              Share
            </Button>
            {actions}
          </div>
        </div>

        <div role="tablist" className="flex gap-6 border-b border-border">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              role="tab"
              className={({ isActive }) =>
                `-mb-px flex items-center gap-1.5 border-b-2 pb-2.5 text-body font-medium ${
                  isActive ? 'border-accent text-text' : 'border-transparent text-muted hover:text-text'
                }`
              }
            >
              {tab.label}
              {tab.to === 'files' && ws && (
                <span className="rounded-pill bg-surface-muted px-1.5 py-px text-label text-muted">{ws.file_count}</span>
              )}
            </NavLink>
          ))}
        </div>
      </header>

      {/* Keyed by workspace so each tab starts fresh when switching clients. */}
      <Fragment key={id}>
        <Outlet context={outlet} />
      </Fragment>
    </div>
  )
}
