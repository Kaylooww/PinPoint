import { Link } from 'react-router-dom'
import { WorkspaceCard } from '../components/WorkspaceCard'
import { useWorkspaces } from '../lib/workspaces'

export type ClientTab = 'files' | 'ask' | 'memory'

const TITLES: Record<ClientTab, string> = {
  files: 'Choose whose files to open.',
  ask: 'Choose whose documents to ask about.',
  memory: 'Choose whose notes and history to open.',
}

// Not in Figma: sidebar Files / Ask / Memory land here first, reusing the Workspaces grid's cards.
export function SelectClientPage({ tab }: { tab: ClientTab }) {
  const { workspaces, loading, error } = useWorkspaces()
  return (
    <div className="flex flex-col gap-7 pt-1">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1 text-text">Select client</h1>
        <p className="text-small text-muted">{TITLES[tab]}</p>
      </header>
      {error && !workspaces.length ? (
        <p role="alert" className="text-small text-danger">
          {error}
        </p>
      ) : loading && !workspaces.length ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-[178px] animate-pulse rounded-card border border-border bg-surface" />
          ))}
        </div>
      ) : workspaces.length === 0 ? (
        <p className="text-small text-muted">
          No clients yet.{' '}
          <Link to="/workspaces" className="text-accent hover:text-accent-hover">
            Create a workspace
          </Link>
          .
        </p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-5">
          {workspaces.map((w) => (
            <WorkspaceCard key={w.id} workspace={w} to={`/w/${w.id}/${tab}`} />
          ))}
        </div>
      )}
    </div>
  )
}
