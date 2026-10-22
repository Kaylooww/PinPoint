import { AlertTriangle, Clock, CornerDownRight, Loader2, Plus, Search, Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { AnswerCard } from '../components/AnswerCard'
import { Button } from '../components/Button'
import { CitationPanel } from '../components/CitationPanel'
import { SearchInput } from '../components/SearchInput'
import { api } from '../lib/api'
import { dayLabel, formatSeconds } from '../lib/format'
import type { AskResponse, Citation, HistoryItem } from '../lib/types'
import { useWorkspaceOutlet } from '../lib/workspaceOutlet'

/** One question in the current thread and what came back. */
type Turn = {
  question: string
  response?: AskResponse
  historyId?: string
  saved: boolean
  error?: string
}

// Figma 05 Ask (7:542) and 06 Citation Viewer (7:748). Answers form a thread: "Ask a follow-up"
// keeps the thread_id; "New question" starts over. ?h=<history id> reopens a past answer.
export function AskPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const { workspace, setActions } = useWorkspaceOutlet()
  const inputRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [followingUp, setFollowingUp] = useState(false)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState<{ turn: number; citation: Citation } | null>(null)
  const [recent, setRecent] = useState<HistoryItem[]>([])

  useEffect(() => {
    setActions(
      <Button Icon={Upload} onClick={() => navigate(`/w/${id}/files`)}>
        Upload files
      </Button>,
    )
    return () => setActions(null)
  }, [id, navigate, setActions])

  const loadRecent = useCallback(
    () =>
      api.listHistory(id).then(
        (items) => {
          // Newest first, one row per distinct question.
          const seen = new Set<string>()
          setRecent(items.filter((i) => !seen.has(i.question.toLowerCase()) && seen.add(i.question.toLowerCase())).slice(0, 8))
        },
        () => undefined, // Recent questions are a convenience; the page works without them.
      ),
    [id],
  )

  useEffect(() => {
    void loadRecent()
  }, [loadRecent])

  // Reopen a past answer from history (Memory tab, recent questions) without asking again.
  const reopen = params.get('h')
  useEffect(() => {
    if (!reopen) return
    let alive = true
    api.getHistory(id, reopen).then(
      (detail) => {
        if (!alive) return
        setTurns([{ question: detail.question, response: detail.response, historyId: reopen, saved: detail.saved }])
        setThreadId(detail.thread_id)
        setFollowingUp(false)
        setOpen(null)
        setQuestion('')
      },
      (e: unknown) => alive && setTurns([{ question: '', saved: false, error: e instanceof Error ? e.message : 'Not found in history.' }]),
    )
    return () => {
      alive = false
    }
  }, [id, reopen])

  useEffect(() => {
    if (turns.length > 1 || loading) bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length, loading])

  const ask = useCallback(
    async (q: string) => {
      const thread = followingUp ? threadId : null
      if (params.has('h')) setParams({}, { replace: true })
      setOpen(null)
      setLoading(true)
      setQuestion('')
      setTurns((list) => (thread ? list : []))
      try {
        const result = await api.ask(id, q, thread ?? undefined)
        setThreadId(result.thread_id)
        setTurns((list) => [...list, { question: q, response: result, historyId: result.history_id, saved: false }])
      } catch (e) {
        setTurns((list) => [...list, { question: q, saved: false, error: e instanceof Error ? e.message : 'Something went wrong.' }])
      } finally {
        setLoading(false)
        setFollowingUp(false)
        void loadRecent()
      }
    },
    [followingUp, threadId, id, params, setParams, loadRecent],
  )

  const followUp = () => {
    setFollowingUp(true)
    setQuestion('')
    inputRef.current?.focus()
  }

  const newQuestion = () => {
    setFollowingUp(false)
    setThreadId(null)
    setTurns([])
    setOpen(null)
    setQuestion('')
    if (params.has('h')) setParams({}, { replace: true })
    inputRef.current?.focus()
  }

  const toggleSave = async (index: number) => {
    const turn = turns[index]
    if (!turn.historyId) return
    const next = !turn.saved
    setTurns((list) => list.map((t, i) => (i === index ? { ...t, saved: next } : t)))
    try {
      await api.setSaved(id, turn.historyId, next)
    } catch {
      setTurns((list) => list.map((t, i) => (i === index ? { ...t, saved: !next } : t)))
    }
  }

  const closePanel = useCallback(() => setOpen(null), [])
  const fileCount = workspace?.file_count ?? 0
  const last = turns.length - 1

  return (
    <div className="flex items-start gap-8">
      <div className="flex min-w-0 flex-1 flex-col gap-3.5">
        {turns.map((turn, i) => (
          <div key={`${turn.historyId ?? i}`} className="flex flex-col gap-3.5">
            {turn.question && (
              <p className="flex items-start gap-2 text-body font-medium text-text">
                {i > 0 && <CornerDownRight size={16} strokeWidth={1.75} className="mt-[3px] shrink-0 text-muted" />}
                {turn.question}
              </p>
            )}
            {turn.error ? (
              <div role="alert" className="flex items-start gap-3 rounded-card border border-border bg-danger-soft px-5 py-4">
                <AlertTriangle size={18} strokeWidth={1.75} className="mt-0.5 shrink-0 text-danger" />
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <p className="text-body font-medium text-text">Couldn't get an answer</p>
                  <p className="text-small text-muted">{turn.error}</p>
                </div>
                {turn.question && (
                  <Button variant="secondary" onClick={() => void ask(turn.question)}>
                    Retry
                  </Button>
                )}
              </div>
            ) : turn.response ? (
              <>
                <p className="text-label text-muted">
                  Searched {turn.response.searched_files} file{turn.response.searched_files === 1 ? '' : 's'} in{' '}
                  {formatSeconds(turn.response.elapsed_ms)}
                </p>
                {turn.response.status === 'answered' && turn.response.answer.length > 0 ? (
                  <AnswerCard
                    response={turn.response}
                    activeCitationId={open?.turn === i ? open.citation.id : null}
                    onOpenCitation={(citation) => setOpen({ turn: i, citation })}
                    onFollowUp={i === last && !loading ? followUp : undefined}
                    saved={turn.saved}
                    onToggleSave={turn.historyId ? () => void toggleSave(i) : undefined}
                  />
                ) : (
                  <NotFoundCard
                    reason={turn.response.reason}
                    workspaceName={workspace?.name}
                    fileCount={turn.response.searched_files}
                    onUpload={() => navigate(`/w/${id}/files`)}
                    onRephrase={() => inputRef.current?.focus()}
                  />
                )}
              </>
            ) : null}
          </div>
        ))}

        {loading && <LoadingCard fileCount={fileCount} />}

        {followingUp && turns.length > 0 && (
          <div className="flex items-center justify-between gap-3 rounded-control bg-accent-soft px-3.5 py-2">
            <p className="flex min-w-0 items-center gap-2 text-small text-accent">
              <CornerDownRight size={14} strokeWidth={1.75} className="shrink-0" />
              <span className="truncate">Following up on: {turns[last].question}</span>
            </p>
            <Button variant="ghost" Icon={Plus} onClick={newQuestion}>
              New question
            </Button>
          </div>
        )}

        <SearchInput
          ref={inputRef}
          value={question}
          onChange={setQuestion}
          onSubmit={ask}
          busy={loading}
          placeholder={followingUp ? 'Ask a follow-up…' : undefined}
        />

        {turns.length === 0 && !loading && (
          <p className="text-small text-muted">
            Ask anything about the files in {workspace?.name ?? 'this workspace'}. Every answer shows where it came from.
          </p>
        )}

        {turns.length > 0 && !loading && !followingUp && (
          <div>
            <Button variant="ghost" Icon={Plus} onClick={newQuestion}>
              New question
            </Button>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <aside className="flex w-[272px] shrink-0 flex-col gap-1" aria-label="Recent questions">
        <h2 className="pb-2 text-h3 text-text">Recent questions</h2>
        {recent.length === 0 ? (
          <p className="px-2.5 text-small text-muted">Your questions will show up here.</p>
        ) : (
          recent.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => setParams({ h: r.id })}
              className="flex w-full items-start gap-2.5 rounded-control p-2.5 text-left hover:bg-surface-muted"
            >
              <Clock size={16} strokeWidth={1.75} className="mt-0.5 shrink-0 text-muted" />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="text-small text-text">{r.question}</span>
                <span className="text-label text-muted">{dayLabel(r.created_at)}</span>
              </span>
            </button>
          ))
        )}
      </aside>

      {open && turns[open.turn]?.response && (
        <CitationPanel
          key={`${open.turn}-${open.citation.id}`}
          citation={open.citation}
          total={turns[open.turn].response!.citations.length}
          onClose={closePanel}
        />
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
