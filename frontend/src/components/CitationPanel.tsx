import { Check, Copy, FileText, X, StickyNote } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Citation } from '../lib/types'
import { Button } from './Button'
import { CropImage } from './CropImage'

type CitationPanelProps = {
  citation: Citation
  total: number
  onClose: () => void
}

// Figma "Citation Panel" (7:922): larger proof image, file and page, extracted text, Copy text.
// Render with key={citation.id} so per-source state (Copied) resets when switching sources.
export function CitationPanel({ citation, total, onClose }: CitationPanelProps) {
  const [copied, setCopied] = useState(false)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(citation.text)
      setCopied(true)
    } catch {
      // Clipboard blocked; nothing else to do.
    }
  }

  return (
    <aside
      role="dialog"
      aria-label={`Source ${citation.number} of ${total}`}
      className="fixed inset-y-0 right-0 z-30 flex w-[440px] flex-col gap-[18px] overflow-y-auto border-l border-border bg-surface p-6 shadow-panel"
    >
      <header className="flex items-center justify-between">
        <h2 className="text-h3 text-text">
          Source {citation.number} of {total}
        </h2>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label="Close source"
          className="flex size-8 items-center justify-center rounded-control border border-border text-muted hover:text-text"
        >
          <X size={16} strokeWidth={1.75} />
        </button>
      </header>

      <div className="flex items-center gap-2">
        <span className="flex size-[18px] shrink-0 items-center justify-center rounded-pill bg-accent-soft text-label text-accent">
          {citation.number}
        </span>
        {citation.kind === 'note' ? (
          <StickyNote size={14} strokeWidth={1.75} className="shrink-0 text-muted" />
        ) : (
          <FileText size={14} strokeWidth={1.75} className="shrink-0 text-muted" />
        )}
        <span className="min-w-0 truncate text-small text-text">
          {citation.kind === 'note' ? 'Note saved in Memory' : `${citation.file_name} · Page ${citation.page}`}
        </span>
      </div>

      <div className="overflow-hidden rounded-card">
        <CropImage citation={citation} size="panel" />
      </div>

      <p className="text-eyebrow text-muted uppercase">{citation.kind === 'note' ? 'Note' : 'Extracted text'}</p>
      <p className="text-small whitespace-pre-line text-text">{citation.text}</p>

      <div className="flex gap-2">
        <Button variant="secondary" Icon={copied ? Check : Copy} onClick={copy}>
          {copied ? 'Copied' : 'Copy text'}
        </Button>
      </div>
    </aside>
  )
}
