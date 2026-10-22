import type { FileStatus } from '../lib/types'

const STYLES: Record<FileStatus, { label: string; pill: string; dot: string }> = {
  ready: { label: 'Ready', pill: 'bg-success-soft text-success', dot: 'bg-success' },
  parsing: { label: 'Parsing', pill: 'bg-warning-soft text-warning', dot: 'bg-warning animate-pulse' },
  queued: { label: 'Queued', pill: 'bg-surface-muted text-muted', dot: 'bg-muted' },
  failed: { label: 'Failed', pill: 'bg-danger-soft text-danger', dot: 'bg-danger' },
}

// Figma "Status Badge" (3:190): Ready, Parsing, Queued, Failed.
export function StatusBadge({ status }: { status: FileStatus }) {
  const s = STYLES[status]
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-pill px-2.5 py-1 text-label ${s.pill}`}>
      <span className={`size-1.5 rounded-pill ${s.dot}`} aria-hidden="true" />
      {s.label}
    </span>
  )
}
