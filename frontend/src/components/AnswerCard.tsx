import { Bookmark, BookmarkCheck, Check, Copy, CornerDownRight } from 'lucide-react'
import { Fragment, useState } from 'react'
import type { AskResponse, Citation } from '../lib/types'
import { Button } from './Button'
import { CitationCard } from './CitationCard'

type AnswerCardProps = {
  response: AskResponse
  activeCitationId?: string | null
  onOpenCitation: (citation: Citation) => void
  onFollowUp?: () => void
  saved?: boolean
  onToggleSave?: () => void
}

export const EXTRACTIVE_LABEL = 'Showing matching passages.'

// Figma "Answer Card" (4:156): answer text with inline numbered markers, sources, actions.
export function AnswerCard({ response, activeCitationId, onOpenCitation, onFollowUp, saved = false, onToggleSave }: AnswerCardProps) {
  const [copied, setCopied] = useState(false)
  const byId = new Map(response.citations.map((c) => [c.id, c]))
  const fileCount = new Set(response.citations.filter((c) => c.kind === 'file').map((c) => c.file_id)).size
  const extractive = response.reason === EXTRACTIVE_LABEL

  const copy = async () => {
    const text = response.answer.map((s) => s.text).join(' ')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard blocked; nothing else to do.
    }
  }

  return (
    <article className="flex w-full flex-col gap-[18px] rounded-card border border-border bg-surface px-6 py-[22px] shadow-subtle">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-muted">
          <Check size={16} strokeWidth={2} className="text-success" />
          <span className="text-eyebrow uppercase">{extractive ? 'Matching passages' : 'Answer'}</span>
        </div>
        <span className="text-label text-muted">
          {fileCount === 0
            ? 'From your notes'
            : `From ${fileCount} of ${response.searched_files} file${response.searched_files === 1 ? '' : 's'}`}
        </span>
      </header>

      {extractive && (
        <p className="-mt-2 text-small text-muted">{EXTRACTIVE_LABEL} The assistant is unavailable, so these are the closest passages.</p>
      )}

      <p className={extractive ? 'font-serif text-doc text-text' : 'text-[16px] leading-[26px] text-text'}>
        {response.answer.map((sentence, i) => (
          <Fragment key={i}>
            {i > 0 && ' '}
            {sentence.text}
            {sentence.sources.map((id) => {
              const c = byId.get(id)
              return c ? (
                <button
                  key={id}
                  type="button"
                  onClick={() => onOpenCitation(c)}
                  aria-label={`Source ${c.number}`}
                  className="ml-0.5 align-baseline font-sans text-label font-medium text-accent hover:text-accent-hover"
                >
                  [{c.number}]
                </button>
              ) : null
            })}
          </Fragment>
        ))}
      </p>

      <p className="text-eyebrow text-muted uppercase">Sources</p>
      <div className="flex flex-wrap gap-3">
        {response.citations.map((c) => (
          <CitationCard key={c.id} citation={c} onOpen={onOpenCitation} active={c.id === activeCitationId} />
        ))}
      </div>

      <div className="flex gap-1">
        <Button variant="ghost" Icon={copied ? Check : Copy} onClick={copy}>
          {copied ? 'Copied' : 'Copy answer'}
        </Button>
        {onToggleSave && (
          <Button variant="ghost" Icon={saved ? BookmarkCheck : Bookmark} onClick={onToggleSave} aria-pressed={saved}>
            {saved ? 'Saved' : 'Save'}
          </Button>
        )}
        {onFollowUp && (
          <Button variant="ghost" Icon={CornerDownRight} onClick={onFollowUp}>
            Ask a follow-up
          </Button>
        )}
      </div>
    </article>
  )
}
