import { File, FileText, Image, Presentation, Sheet, type LucideIcon } from 'lucide-react'
import { fileMeta } from '../lib/format'
import type { FileItem, FileType } from '../lib/types'
import { StatusBadge } from './StatusBadge'

const ICONS: Record<FileType, LucideIcon> = {
  pdf: FileText,
  doc: FileText,
  image: Image,
  sheet: Sheet,
  slides: Presentation,
  other: File,
}

// Figma "File Row" (4:30): type icon, name, meta (or error), progress while parsing, status badge.
export function FileRow({ file, onOpen }: { file: FileItem; onOpen?: (file: FileItem) => void }) {
  const Icon = ICONS[file.type]
  return (
    <div className="flex items-center gap-3.5 rounded-control border border-border bg-surface px-4 py-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-control bg-surface-muted text-muted">
        <Icon size={18} strokeWidth={1.75} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {onOpen && file.status === 'ready' ? (
          <button
            type="button"
            onClick={() => onOpen(file)}
            title="Open document"
            className="truncate text-left text-body font-medium text-text hover:text-accent hover:underline"
          >
            {file.name}
          </button>
        ) : (
          <p className="truncate text-body font-medium text-text">{file.name}</p>
        )}
        {file.status === 'failed' ? (
          <p className="text-small text-danger">{file.error ?? "Couldn't read this file."}</p>
        ) : (
          <>
          <p className="flex min-w-0 items-center gap-1.5 truncate text-small text-muted">
            {file.source === 'folder' && (
              <span className="rounded-control border border-border px-1.5 text-label">Folder</span>
            )}
            {fileMeta(file)}
          </p>
          {/* A ready file can carry a note, e.g. pages that couldn't be read. */}
          {file.status === 'ready' && file.error && <p className="truncate text-small text-warning">{file.error}</p>}
          </>
        )}
      </div>
      {file.status === 'parsing' && (
        <div className="flex w-40 shrink-0 flex-col gap-1.5" aria-live="polite">
          <p className="truncate text-label text-muted">{file.progress_label ?? 'Reading pages…'}</p>
          <div className="h-1 overflow-hidden rounded-[2px] bg-surface-muted">
            <div className="h-1 w-2/3 animate-pulse rounded-[2px] bg-accent" />
          </div>
        </div>
      )}
      <StatusBadge status={file.status} />
    </div>
  )
}
