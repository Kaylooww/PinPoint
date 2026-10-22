import { FileText, StickyNote } from 'lucide-react'
import type { Citation } from '../lib/types'
import { breadcrumb } from '../lib/format'
import { CropImage } from './CropImage'

type CitationCardProps = {
  citation: Citation
  onOpen: (citation: Citation) => void
  active?: boolean
  /** With only 1-2 citations, cards grow (up to 480px) so wide paragraph crops stay readable. */
  wide?: boolean
}

// Figma "Citation Card" (4:72): crop on top, numbered footer with file and page.
export function CitationCard({ citation, onOpen, active = false, wide = false }: CitationCardProps) {
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      aria-label={`Open source ${citation.number}: ${citation.kind === 'note' ? 'note' : `${citation.file_name}, page ${citation.page}`}`}
      className={`flex flex-col overflow-hidden rounded-card border bg-surface text-left hover:border-accent ${
        wide ? 'min-w-[264px] max-w-[480px] flex-1 basis-[264px]' : 'w-[264px]'
      } ${
        active ? 'border-accent' : 'border-border'
      }`}
    >
      <CropImage citation={citation} />
      {citation.path?.length ? (
        <p className="truncate border-t border-border px-3.5 pt-2 text-label text-muted" title={citation.path.join(' > ')}>
          {breadcrumb(citation.path)}
        </p>
      ) : null}
      <div className={`flex w-full items-center gap-2 px-3.5 py-2.5 ${citation.path?.length ? 'pt-1' : 'border-t border-border'}`}>
        <span className="flex size-[18px] shrink-0 items-center justify-center rounded-pill bg-accent-soft text-label text-accent">
          {citation.number}
        </span>
        {citation.kind === 'note' ? (
          <>
            <StickyNote size={14} strokeWidth={1.75} className="shrink-0 text-muted" />
            <span className="min-w-0 flex-1 truncate text-label text-text">Note</span>
          </>
        ) : (
          <>
            <FileText size={14} strokeWidth={1.75} className="shrink-0 text-muted" />
            <span className="min-w-0 flex-1 truncate text-label text-text">{citation.file_name}</span>
            <span className="shrink-0 text-label text-muted">p. {citation.page}</span>
          </>
        )}
      </div>
    </button>
  )
}
