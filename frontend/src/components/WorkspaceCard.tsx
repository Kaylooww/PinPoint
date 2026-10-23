import { Briefcase, Calculator, Home, Scale, Trash2, Umbrella, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { timeAgo } from '../lib/format'
import type { Workspace } from '../lib/types'

const INDUSTRY_ICONS: [string[], LucideIcon][] = [
  [['law', 'legal'], Scale],
  [['real'], Home],
  [['account'], Calculator],
  [['insur'], Umbrella],
]

function IndustryIcon({ industry }: { industry: string }) {
  const i = industry.toLowerCase()
  const Icon = INDUSTRY_ICONS.find(([keys]) => keys.some((k) => i.includes(k)))?.[1] ?? Briefcase
  return <Icon size={20} strokeWidth={1.75} />
}

type WorkspaceCardProps = {
  workspace: Workspace
  to?: string
  onDelete?: (workspace: Workspace) => void
}

// Figma "Workspace Card" (4:51). Not in Figma: a delete button (bottom right, on hover or
// keyboard focus), outside the link so it isn't a button nested in an anchor.
export function WorkspaceCard({ workspace, to, onDelete }: WorkspaceCardProps) {
  const card = (
    <Link
      to={to ?? `/w/${workspace.id}/ask`}
      className="flex h-full flex-col gap-3.5 rounded-card border border-border bg-surface p-5 shadow-subtle hover:border-accent"
    >
      <div className="flex items-center justify-between">
        <div className="flex size-10 items-center justify-center rounded-control bg-accent-soft text-accent">
          <IndustryIcon industry={workspace.industry} />
        </div>
        <span className="rounded-pill bg-surface-muted px-2 py-[3px] text-label text-muted">{workspace.industry}</span>
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-h3 text-text">{workspace.name}</p>
        <p className="text-small text-muted">
          {workspace.file_count} file{workspace.file_count === 1 ? '' : 's'} · Updated {timeAgo(workspace.updated_at)}
        </p>
      </div>
    </Link>
  )
  if (!onDelete) return card
  return (
    <div className="group relative">
      {card}
      <button
        type="button"
        onClick={() => onDelete(workspace)}
        title="Delete workspace"
        aria-label={`Delete workspace ${workspace.name}`}
        className="absolute right-4 bottom-4 flex size-8 items-center justify-center rounded-control text-muted opacity-0 transition hover:bg-danger-soft hover:text-danger focus-visible:opacity-100 group-hover:opacity-100"
      >
        <Trash2 size={16} strokeWidth={1.75} />
      </button>
    </div>
  )
}
