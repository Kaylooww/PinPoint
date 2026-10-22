import { AlertTriangle, Clock, Loader2, Search, Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AnswerCard } from '../components/AnswerCard'
import { Button } from '../components/Button'
import { CitationPanel } from '../components/CitationPanel'
import { SearchInput } from '../components/SearchInput'
import { api } from '../lib/api'
import { dayLabel, formatSeconds } from '../lib/format'
import { addRecent, getRecent, type RecentQuestion } from '../lib/recent'
import type { AskResponse, Citation } from '../lib/types'
import { useWorkspaceOutlet } from '../lib/workspaceOutlet'

type State =
  | { kind: 'idle' }
  | { kind: 'loading'; question: string }
  | { kind: 'done'; question: string; response: AskResponse }
  | { kind: 'error'; question: string; message: string }

// Figma 05 Ask (7:542) and 06 Citation Viewer (7:748).
export function AskPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { workspace, setActions } = useWorkspaceOutlet()
  const inputRef = useRef<HTMLInputElement>(null)
  const [question, setQuestion] = useState('')
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [citation, setCitation] = useState<Citation | null>(null)
  const [recent, setRecent] = useState<RecentQuestion[]>(() => getRecent(id))

  useEffect(() => {
    setActions(
      <Button Icon={Upload} onClick={() => navigate(`/w/${id}/files`)}>
        Upload files
      </Button>,
    )
    return () => setActions(null)
  }, [id, navigate, setActions])

  const ask = useCallback(
    async (q: string) => {
      setQuestion(q)
      setCitation(null)
      setState({ kind: 'loading', question: q })
      setRecent(addRecent(id, q))
      try {
        const response = await api.ask(id, q)
        setState({ kind: 'done', question: q, response })
      } catch (e) {
        setState({ kind: 'error', question: q, message: e instanceof Error ? e.message : 'Something went wrong.' })
      }
    },
    [id],
  )

  const followUp = () => {
    setQuestion('')
    inputRef.current?.focus()
  }

  const closePanel = useCallback(() => setCitation(null), [])
  const fileCount = workspace?.file_count ?? 0

  return (
    <div className="flex items-start gap-8">
      <div className="flex min-w-0 flex-1 flex-col gap-3.5">
        <SearchInput
          ref={inputRef}
          value={question}
          onChange={setQuestion}
          onSubmit={ask}
          busy={state.kind === 'loading'}
        />

        {state.kind === 'idle' && (
          <p className="text-small text-muted">
            Ask anything about the files in {workspace?.name ?? 'this workspace'}. Every answer shows where it came from.
          </p>
        )}

        {state.kind === 'loading' && <LoadingCard fileCount={fileCount} />}

        {state.kind === 'done' && (
          <>
            <p className="text-label text-muted">
              Searched {state.response.searched_files} file{state.response.searched_files === 1 ? '' : 's'} in{' '}
              {formatSeconds(state.response.elapsed_ms)}
            </p>
            {state.response.status === 'answered' && state.response.answer.length > 0 ? (
              <AnswerCard
                response={state.response}
                activeCitationId={citation?.id}
                onOpenCitation={setCitation}
                onFollowUp={followUp}
              />
            ) : (
              <NotFoundCard
                reason={state.response.reason}
                workspaceName={workspace?.name}
                fileCount={state.response.searched_files}
                onUpload={() => navigate(`/w/${id}/files`)}
                onRephrase={() => inputRef.current?.focus()}
              />
            )}
          </>
        )}

        {state.kind === 'error' && (
          <div role="alert" className="flex items-start gap-3 rounded-card border border-border bg-danger-soft px-5 py-4">
            <AlertTriangle size={18} strokeWidth={1.75} className="mt-0.5 shrink-0 text-danger" />
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <p className="text-body font-medium text-text">Couldn't get an answer</p>
              <p className="text-small text-muted">{state.message}</p>
            </div>
            <Button variant="secondary" onClick={() => void ask(state.question)}>
              Retry
            </Button>
          </div>
        )}
      </div>

      <aside className="flex w-[272px] shrink-0 flex-col gap-1" aria-label="Recent questions">
        <h2 className="pb-2 text-h3 text-text">Recent questions</h2>
        {recent.length === 0 ? (
          <p className="px-2.5 text-small text-muted">Your questions will show up here.</p>
        ) : (
          recent.map((r) => (
            <button
              key={r.question}
              type="button"
              onClick={() => void ask(r.question)}
              className="flex w-full items-start gap-2.5 rounded-control p-2.5 text-left hover:bg-surface-muted"
            >
              <Clock size={16} strokeWidth={1.75} className="mt-0.5 shrink-0 text-muted" />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="text-small text-text">{r.question}</span>
                <span className="text-label text-muted">{dayLabel(r.asked_at)}</span>
              </span>
            </button>
          ))
        )}
      </aside>

      {citation && state.kind === 'done' && (
        <CitationPanel key={citation.id} citation={citation} total={state.response.citations.length} onClose={closePanel} />
      )}
    </div>
  )
}

// Figma 07 States (9:971), "Loading".
function LoadingCard({ fileCount }: { fileCount: number }) {
  return (
    <div className="flex flex-col gap-4 rounded-card border border-border bg-surface px-6 py-[22px]" aria-live="polite">
      <p className="flex items-center gap-2 text-body font-medium text-text">
        <Loader2 size={16} strokeWidth={2} className="animate-spin text-accent" />
        Searching {fileCount} file{fileCount === 1 ? '' : 's'}…
      </p>
      <div className="flex flex-col gap-2.5" aria-hidden="true">
        <div className="h-2.5 w-4/5 animate-pulse rounded-pill bg-surface-muted" />
        <div className="h-2.5 w-3/5 animate-pulse rounded-pill bg-surface-muted" />
        <div className="h-2.5 w-2/5 animate-pulse rounded-pill bg-surface-muted" />
      </div>
      <div className="flex gap-3" aria-hidden="true">
        {[0, 1].map((i) => (
          <div key={i} className="flex w-[264px] flex-col gap-3 rounded-card border border-border p-3">
            <div className="h-[88px] animate-pulse rounded-control bg-surface-muted" />
            <div className="h-2 w-1/2 animate-pulse rounded-pill bg-surface-muted" />
          </div>
        ))}
      </div>
    </div>
  )
}

type NotFoundCardProps = {
  reason?: string
  workspaceName?: string
  fileCount: number
  onUpload: () => void
  onRephrase: () => void
}

// Figma 07 States (9:971), "Not found".
function NotFoundCard({ reason, workspaceName, fileCount, onUpload, onRephrase }: NotFoundCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-card border border-border bg-surface px-6 py-[22px] shadow-subtle">
      <p className="flex items-center gap-2 text-eyebrow text-muted uppercase">
        <Search size={14} strokeWidth={1.75} />
        Not found in these files
      </p>
      <p className="text-[16px] leading-[26px] text-text">
        {reason || `None of the ${fileCount} files in ${workspaceName ?? 'this workspace'} answer this question.`}
      </p>
      <p className="text-small text-muted">Try uploading the document that covers it, or rephrase your question.</p>
      <div className="flex gap-1 pt-1">
        <Button variant="secondary" onClick={onUpload}>
          Upload more files
        </Button>
        <Button variant="ghost" onClick={onRephrase}>
          Rephrase
        </Button>
      </div>
    </div>
  )
}
