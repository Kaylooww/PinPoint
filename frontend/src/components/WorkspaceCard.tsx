import { Briefcase, Calculator, Home, Scale, Umbrella, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { dayLabel } from '../lib/format'
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

// Figma "Workspace Card" (4:51).
export function WorkspaceCard({ workspace }: { workspace: Workspace }) {
  return (
    <Link
      to={`/w/${workspace.id}/ask`}
      className="flex flex-col gap-3.5 rounded-card border border-border bg-surface p-5 shadow-subtle hover:border-accent"
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
          {workspace.file_count} file{workspace.file_count === 1 ? '' : 's'} · Updated {dayLabel(workspace.updated_at).toLowerCase()}
        </p>
      </div>
    </Link>
  )
}
