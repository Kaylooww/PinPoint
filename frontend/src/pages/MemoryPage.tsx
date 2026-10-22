import { Bookmark, History, Loader2, StickyNote, Trash2 } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '../components/Button'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../lib/api'
import { dayLabel, timeAgo } from '../lib/format'
import type { HistoryItem, Note } from '../lib/types'

// Memory tab (not in Figma): built from the existing cards, rows, and type scale.
export function MemoryPage() {
  const { id = '' } = useParams()
  return (
    <div className="flex max-w-[820px] flex-col gap-10">
      <NotesSection ws={id} />
      <HistorySections ws={id} />
    </div>
  )
}

function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-h3 text-text">{title}</h2>
      <p className="text-small text-muted">{hint}</p>
    </div>
  )
}

function NotesSection({ ws }: { ws: string }) {
  const [notes, setNotes] = useState<Note[] | null>(null)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api.listNotes(ws).then(
      (list) => alive && setNotes(list),
      (e: unknown) => alive && setError(e instanceof Error ? e.message : 'Could not load notes.'),
    )
    return () => {
      alive = false
    }
  }, [ws])

  const add = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!text.trim() || saving) return
    setSaving(true)
    setError(null)
    try {
      const note = await api.addNote(ws, text.trim())
      setNotes((list) => [note, ...(list ?? [])])
      setText('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the note.')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (note: Note) => {
    setNotes((list) => list?.filter((n) => n.id !== note.id) ?? null)
    try {
      await api.deleteNote(ws, note.id)
    } catch (err) {
      setNotes((list) => [note, ...(list ?? [])])
      setError(err instanceof Error ? err.message : 'Could not delete the note.')
    }
  }

  return (
    <section className="flex flex-col gap-4" aria-label="Notes">
      <SectionHeader title="Notes" hint="Facts you save here are searched and cited in answers, just like your documents." />

      <form onSubmit={add} className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-subtle">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void add()
          }}
          rows={3}
          maxLength={4000}
          placeholder="Remember something about this client…"
          aria-label="New note"
          className="w-full resize-none rounded-control border border-border bg-surface px-3 py-2.5 text-body text-text placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-label text-muted">⌘ Enter to save</span>
          <Button type="submit" disabled={!text.trim() || saving} Icon={saving ? Loader2 : undefined}>
            Add note
          </Button>
        </div>
      </form>

      {error && <p className="text-small text-danger">{error}</p>}

      {notes === null && !error ? (
        <div className="h-[60px] animate-pulse rounded-card bg-surface-muted" />
      ) : notes && notes.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-border px-6 py-8 text-center">
          <StickyNote size={20} strokeWidth={1.75} className="text-muted" />
          <p className="text-body text-text">No notes yet</p>
          <p className="text-small text-muted">Add things like preferences, deadlines you were told by phone, or who to contact.</p>
        </div>
      ) : (
        <ul className="flex flex-col overflow-hidden rounded-card border border-border bg-surface">
          {notes?.map((note) => (
            <li key={note.id} className="flex items-start gap-3 border-b border-border px-4 py-3.5 last:border-b-0">
              <StickyNote size={16} strokeWidth={1.75} className="mt-[3px] shrink-0 text-muted" />
              <p className="min-w-0 flex-1 font-serif text-doc whitespace-pre-line text-text">{note.text}</p>
              <span className="shrink-0 pt-1 text-label text-muted">{dayLabel(note.created_at)}</span>
              <button
                type="button"
                onClick={() => void remove(note)}
                aria-label="Delete note"
                title="Delete note"
                className="flex size-7 shrink-0 items-center justify-center rounded-control text-muted hover:bg-danger-soft hover:text-danger"
              >
                <Trash2 size={15} strokeWidth={1.75} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function HistorySections({ ws }: { ws: string }) {
  const [items, setItems] = useState<HistoryItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api.listHistory(ws).then(
      (list) => alive && setItems(list),
      (e: unknown) => alive && setError(e instanceof Error ? e.message : 'Could not load history.'),
    )
    return () => {
      alive = false
    }
  }, [ws])

  const saved = items?.filter((i) => i.saved) ?? []
  const byDay = new Map<string, HistoryItem[]>()
  for (const item of items ?? []) {
    const day = dayLabel(item.created_at)
    byDay.set(day, [...(byDay.get(day) ?? []), item])
  }

  return (
    <>
      <section className="flex flex-col gap-4" aria-label="Saved answers">
        <SectionHeader title="Saved answers" hint="Every answered question is saved here automatically. Open one to see it with its sources; use Save on the Ask tab to remove one." />
        {error ? (
          <p className="text-small text-danger">{error}</p>
        ) : items === null ? (
          <div className="h-[60px] animate-pulse rounded-card bg-surface-muted" />
        ) : saved.length === 0 ? (
          <EmptyState Icon={Bookmark} title="No saved answers yet" hint="Answers to questions you ask on the Ask tab are saved here automatically." />
        ) : (
          <HistoryList ws={ws} items={saved} />
        )}
      </section>

      <section className="flex flex-col gap-4" aria-label="History">
        <SectionHeader title="History" hint="Every question asked in this workspace, newest first." />
        {error ? null : items === null ? (
          <div className="h-[60px] animate-pulse rounded-card bg-surface-muted" />
        ) : items.length === 0 ? (
          <EmptyState Icon={History} title="No questions yet" hint="Questions you ask on the Ask tab are kept here." />
        ) : (
          [...byDay.entries()].map(([day, list]) => (
            <div key={day} className="flex flex-col gap-2">
              <p className="text-eyebrow text-muted uppercase">{day}</p>
              <HistoryList ws={ws} items={list} />
            </div>
          ))
        )}
      </section>
    </>
  )
}

function HistoryList({ ws, items }: { ws: string; items: HistoryItem[] }) {
  return (
    <ul className="flex flex-col overflow-hidden rounded-card border border-border bg-surface">
      {items.map((item) => (
        <li key={item.id} className="border-b border-border last:border-b-0">
          <Link to={`/w/${ws}/ask?h=${item.id}`} className="flex items-start gap-3 px-4 py-3.5 hover:bg-surface-muted">
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <p className="truncate text-body font-medium text-text">{item.question}</p>
              <p className="line-clamp-2 text-small text-muted">{item.answer_preview}</p>
            </div>
            <span className="shrink-0 pt-0.5 text-label text-muted">{timeAgo(item.created_at)}</span>
            {item.saved && <Bookmark size={15} strokeWidth={1.75} className="mt-0.5 shrink-0 text-accent" aria-label="Saved" />}
            <StatusBadge
              status={item.status === 'answered' ? 'ready' : 'queued'}
              label={item.status === 'answered' ? 'Answered' : 'Not found'}
            />
          </Link>
        </li>
      ))}
    </ul>
  )
}

function EmptyState({ Icon, title, hint }: { Icon: typeof Bookmark; title: string; hint: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-border px-6 py-8 text-center">
      <Icon size={20} strokeWidth={1.75} className="text-muted" />
      <p className="text-body text-text">{title}</p>
      <p className="text-small text-muted">{hint}</p>
    </div>
  )
}
