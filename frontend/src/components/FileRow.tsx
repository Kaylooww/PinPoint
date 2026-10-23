import { File, FileText, Image, Presentation, Sheet, Trash2, X, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { fileMeta } from '../lib/format'
import type { FileItem, FileType } from '../lib/types'
import { Button } from './Button'
import { StatusBadge } from './StatusBadge'

const ICONS: Record<FileType, LucideIcon> = {
  pdf: FileText,
  doc: FileText,
  image: Image,
  sheet: Sheet,
  slides: Presentation,
  other: File,
}

type FileRowProps = {
  file: FileItem
  onOpen?: (file: FileItem) => void
  onDelete?: (file: FileItem) => Promise<void>
  onCancel?: (file: FileItem) => Promise<void>
}

// Figma "File Row" (4:30): type icon, name, meta (or error), progress while parsing, status badge.
// Not in Figma: a delete button with an inline confirm for uploaded files, and an X that
// cancels an upload while it is queued or being read (nothing to confirm: nothing is indexed yet).
export function FileRow({ file, onOpen, onDelete, onCancel }: FileRowProps) {
  const Icon = ICONS[file.type]
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const deletable = onDelete && file.source !== 'folder' && (file.status === 'ready' || file.status === 'failed')
  const cancellable = onCancel && file.source !== 'folder' && (file.status === 'queued' || file.status === 'parsing')

  const cancel = async () => {
    setCancelling(true)
    try {
      await onCancel?.(file)
    } finally {
      setCancelling(false)
    }
  }

  const remove = async () => {
    setDeleting(true)
    try {
      await onDelete?.(file)
    } finally {
      setDeleting(false)
      setConfirming(false)
    }
  }

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
        {confirming ? (
          <p className="truncate text-small text-danger">Delete this file from PinPoint? Answers can no longer cite it.</p>
        ) : file.status === 'failed' ? (
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
      {confirming ? (
        <>
          <Button variant="ghost" disabled={deleting} onClick={() => setConfirming(false)}>
            Cancel
          </Button>
          <Button
            variant="secondary"
            Icon={Trash2}
            disabled={deleting}
            onClick={() => void remove()}
            className="border-danger text-danger hover:bg-danger-soft"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </Button>
        </>
      ) : (
        <>
          <StatusBadge status={file.status} />
          {deletable && (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              title="Delete file"
              aria-label={`Delete ${file.name}`}
              className="flex size-8 shrink-0 items-center justify-center rounded-control text-muted transition-colors hover:bg-danger-soft hover:text-danger"
            >
              <Trash2 size={16} strokeWidth={1.75} />
            </button>
          )}
          {cancellable && (
            <button
              type="button"
              onClick={() => void cancel()}
              disabled={cancelling}
              title="Cancel upload"
              aria-label={`Cancel upload of ${file.name}`}
              className="flex size-8 shrink-0 items-center justify-center rounded-control text-muted transition-colors hover:bg-danger-soft hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
            >
              <X size={16} strokeWidth={1.75} />
            </button>
          )}
        </>
      )}
    </div>
  )
}
