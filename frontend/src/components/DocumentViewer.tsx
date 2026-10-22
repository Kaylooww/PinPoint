import { Loader2, Maximize, MessageSquare, PanelRightClose, X, ZoomIn, ZoomOut } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, pageUrl, rawUrl } from '../lib/api'
import type { AskResult, FileText, FileType } from '../lib/types'
import { BlockText } from './BlockText'
import { SearchInput } from './SearchInput'

export type ViewerFile = { id: string; name: string; type: FileType; page?: number; locator?: string }

type Target = { page: number; locator?: string }
type DocumentViewerProps = { ws: string; file: ViewerFile; onClose: () => void }

const ZOOM_STEPS = [50, 67, 80, 90, 100, 110, 125, 150, 175, 200, 250, 300]
const extension = (name: string) => name.split('.').pop()?.toLowerCase() ?? ''

// Not in Figma: a centered modal (never full-screen) on the app's tokens. PDFs are page
// images rendered by the backend (no PDF library, no CDN), images show directly, and
// text-like and office files show their parsed text by page. The right side asks
// questions about this document only.
export function DocumentViewer({ ws, file, onClose }: DocumentViewerProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [doc, setDoc] = useState<FileText | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(100)
  const [current, setCurrent] = useState(file.page ?? 1)
  const [target, setTarget] = useState<Target | null>(file.page ? { page: file.page, locator: file.locator } : null)
  const [askOpen, setAskOpen] = useState(true)
  const ext = extension(file.name)
  const mode = file.type === 'pdf' && pageUrl(ws, file.id, 1) ? 'pdf' : file.type === 'image' && rawUrl(ws, file.id) ? 'image' : ['md', 'txt', 'csv'].includes(ext) && rawUrl(ws, file.id) ? 'plain' : 'parsed'
  const pageCount = mode === 'image' ? 1 : Math.max(doc?.page_count ?? 0, doc?.pages.length ?? 0, 1)

  useEffect(() => {
    let alive = true
    api.getFileText(ws, file.id).then(
      (d) => alive && setDoc(d),
      (e: unknown) => alive && setError(e instanceof Error ? e.message : 'Could not load this document.'),
    )
    return () => {
      alive = false
    }
  }, [ws, file.id])

  // Modal behavior: Escape closes only the viewer, Tab stays inside, Ctrl/Cmd +/−/0 zoom,
  // and focus returns to whatever opened it.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    dialogRef.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopImmediatePropagation()
        onClose()
      } else if (e.key === 'Tab' && dialogRef.current) {
        const items = [...dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input, [tabindex]:not([tabindex="-1"])')]
        if (!items.length) return
        const first = items[0]
        const last = items[items.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      } else if ((e.metaKey || e.ctrlKey) && ['=', '+', '-', '0'].includes(e.key)) {
        e.preventDefault()
        if (e.key === '0') setZoom(100)
        else setZoom((z) => step(z, e.key === '-' ? -1 : 1))
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      opener?.focus()
    }
  }, [onClose])

  const scrollToPage = useCallback((page: number) => {
    document.getElementById(`viewer-page-${page}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [])

  // Open at the cited page once the layout exists.
  useEffect(() => {
    if (doc && target) requestAnimationFrame(() => scrollToPage(target.page))
  }, [doc, target, scrollToPage])

  // Track the page in view for "Page n of N".
  useEffect(() => {
    const root = scrollRef.current
    if (!root || !doc) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (visible) setCurrent(Number((visible.target as HTMLElement).dataset.page))
      },
      { root, threshold: [0.25, 0.5, 0.75] },
    )
    root.querySelectorAll('[data-page]').forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [doc, mode])

  const bboxFor = (page: number): number[] | undefined =>
    target?.page === page && target.locator
      ? doc?.pages.find((p) => p.page === page)?.blocks.find((b) => b.locator === target.locator)?.bbox
      : undefined

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim" onMouseDown={onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Document: ${file.name}`}
        onMouseDown={(e) => e.stopPropagation()}
        className="flex h-[85vh] w-[90vw] flex-col overflow-hidden rounded-card border border-border bg-surface shadow-panel"
      >
        <header className="flex items-center gap-3 border-b border-border px-4 py-2.5">
          <div className="min-w-0 flex-1">
            <p className="truncate text-h3 text-text">{file.name}</p>
            <p className="text-label text-muted" aria-live="polite">
              Page {Math.min(current, pageCount)} of {pageCount}
            </p>
          </div>
          <div className="flex items-center gap-1 rounded-control border border-border p-0.5" role="group" aria-label="Zoom">
            <IconButton label="Zoom out (Ctrl −)" onClick={() => setZoom((z) => step(z, -1))} disabled={zoom <= ZOOM_STEPS[0]}>
              <ZoomOut size={16} strokeWidth={1.75} />
            </IconButton>
            <span className="w-12 text-center text-label text-text tabular-nums">{zoom}%</span>
            <IconButton label="Zoom in (Ctrl +)" onClick={() => setZoom((z) => step(z, 1))} disabled={zoom >= ZOOM_STEPS[ZOOM_STEPS.length - 1]}>
              <ZoomIn size={16} strokeWidth={1.75} />
            </IconButton>
            <IconButton label="Fit to width" onClick={() => setZoom(100)}>
              <Maximize size={16} strokeWidth={1.75} />
            </IconButton>
          </div>
          <IconButton label={askOpen ? 'Hide Ask panel' : 'Ask about this document'} onClick={() => setAskOpen((v) => !v)} pressed={askOpen}>
            {askOpen ? <PanelRightClose size={16} strokeWidth={1.75} /> : <MessageSquare size={16} strokeWidth={1.75} />}
          </IconButton>
          <IconButton label="Close (Esc)" onClick={onClose} autoFocus>
            <X size={16} strokeWidth={1.75} />
          </IconButton>
        </header>

        <div className="flex min-h-0 flex-1">
          <div ref={scrollRef} className="min-w-0 flex-1 overflow-auto bg-surface-muted">
            {error ? (
              <Message text={error} />
            ) : !doc && mode !== 'image' ? (
              <Loading />
            ) : mode === 'pdf' ? (
              <div className="flex flex-col items-center gap-4 p-6">
                {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
                  <PdfPage key={n} src={pageUrl(ws, file.id, n)!} page={n} zoom={zoom} bbox={bboxFor(n)} name={file.name} />
                ))}
              </div>
            ) : mode === 'image' ? (
              <div className="p-6" data-page="1" id="viewer-page-1">
                <img src={rawUrl(ws, file.id)!} alt={file.name} style={{ width: `${zoom}%` }} className="mx-auto block max-w-none rounded-control border border-border bg-surface" />
              </div>
            ) : mode === 'plain' ? (
              <div style={{ zoom: zoom / 100 }}>
                <PlainView src={rawUrl(ws, file.id)!} csv={ext === 'csv'} />
              </div>
            ) : (
              <div style={{ zoom: zoom / 100 }} className="flex flex-col gap-4 p-6">
                <p className="text-small text-muted">Browsers can't display this file type, so this is the text PinPoint read from it.</p>
                {doc!.pages.map((p) => (
                  <section
                    key={p.page}
                    id={`viewer-page-${p.page}`}
                    data-page={p.page}
                    className={`flex flex-col gap-3 rounded-card border bg-surface p-6 ${target?.page === p.page ? 'border-accent' : 'border-border'}`}
                  >
                    <p className="text-eyebrow text-muted uppercase">Page {p.page}</p>
                    {p.blocks.map((b, i) => (
                      <div key={i} className={b.locator === target?.locator ? 'rounded-control ring-2 ring-accent' : ''}>
                        <BlockText text={b.text} table={b.table} />
                      </div>
                    ))}
                  </section>
                ))}
              </div>
            )}
          </div>

          {askOpen && (
            <AskAboutDocument
              ws={ws}
              file={file}
              onCitation={(page, locator) => {
                setTarget({ page, locator })
                scrollToPage(page)
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function step(zoom: number, dir: 1 | -1): number {
  const next = dir > 0 ? ZOOM_STEPS.find((z) => z > zoom) : [...ZOOM_STEPS].reverse().find((z) => z < zoom)
  return next ?? zoom
}

function PdfPage({ src, page, zoom, bbox, name }: { src: string; page: number; zoom: number; bbox?: number[]; name: string }) {
  const [ratio, setRatio] = useState<number | null>(null)
  return (
    <div
      id={`viewer-page-${page}`}
      data-page={page}
      style={{ width: `${zoom}%`, aspectRatio: ratio ? undefined : '1 / 1.414' }}
      className="relative shrink-0 bg-surface shadow-subtle"
    >
      <img
        src={src}
        alt={`${name}, page ${page}`}
        loading="lazy"
        onLoad={(e) => setRatio(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)}
        className="block w-full"
      />
      {bbox && (
        <div
          aria-label="Cited passage"
          className="pointer-events-none absolute rounded-[2px] bg-highlight/30 ring-2 ring-accent"
          style={{
            left: `${bbox[0] * 100}%`,
            top: `${bbox[1] * 100}%`,
            width: `${(bbox[2] - bbox[0]) * 100}%`,
            height: `${(bbox[3] - bbox[1]) * 100}%`,
          }}
        />
      )}
    </div>
  )
}

function AskAboutDocument({ ws, file, onCitation }: { ws: string; file: ViewerFile; onCitation: (page: number, locator: string) => void }) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<AskResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const ask = async (q: string) => {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.ask(ws, q, undefined, [file.id]))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const byId = new Map(result?.citations.map((c) => [c.id, c]) ?? [])
  return (
    <aside aria-label="Ask about this document" className="flex w-[360px] shrink-0 flex-col gap-3 overflow-y-auto border-l border-border bg-surface p-4">
      <p className="text-eyebrow text-muted uppercase">Ask about this document</p>
      <SearchInput value={question} onChange={setQuestion} onSubmit={(q) => void ask(q)} busy={busy} placeholder="Ask about this file…" />
      {busy && (
        <p className="flex items-center gap-2 text-small text-muted">
          <Loader2 size={14} strokeWidth={2} className="animate-spin text-accent" /> Reading this document…
        </p>
      )}
      {error && <p className="text-small text-danger">{error}</p>}
      {result && !busy && result.status === 'answered' && (
        <div className="flex flex-col gap-3">
          <p className="text-body text-text">
            {result.answer.map((s, i) => (
              <span key={i}>
                {s.text}
                {s.sources.map((id) => {
                  const c = byId.get(id)
                  return c ? (
                    <button key={id} type="button" onClick={() => onCitation(c.page, c.locator)} className="ml-0.5 text-label font-medium text-accent hover:text-accent-hover">
                      [{c.number}]
                    </button>
                  ) : null
                })}{' '}
              </span>
            ))}
          </p>
          <ul className="flex flex-col gap-1.5">
            {result.citations.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onCitation(c.page, c.locator)}
                  className="flex w-full items-start gap-2 rounded-control border border-border p-2.5 text-left hover:border-accent"
                >
                  <span className="flex size-[18px] shrink-0 items-center justify-center rounded-pill bg-accent-soft text-label text-accent">{c.number}</span>
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-label text-muted">Page {c.page}</span>
                    <mark className="line-clamp-3 rounded-[3px] bg-highlight px-1 font-serif text-small text-text">{c.excerpt || c.text}</mark>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {result && !busy && result.status === 'not_found' && (
        <div className="flex flex-col gap-2 rounded-control bg-surface-muted p-3">
          <p className="text-eyebrow text-muted uppercase">Not found in this document</p>
          <p className="text-small text-text">{result.reason}</p>
          {result.suggestion && (
            <button type="button" onClick={() => { setQuestion(result.suggestion!.question); void ask(result.suggestion!.question) }} className="self-start text-left text-small font-medium text-accent hover:text-accent-hover">
              {result.suggestion.text}
            </button>
          )}
        </div>
      )}
      {!result && !busy && <p className="text-small text-muted">Answers come only from this file, with page citations. They are saved in History.</p>}
    </aside>
  )
}

function IconButton({
  label,
  onClick,
  children,
  disabled,
  pressed,
  autoFocus,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
  disabled?: boolean
  pressed?: boolean
  autoFocus?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      data-autofocus={autoFocus ? '' : undefined}
      className={`flex size-8 items-center justify-center rounded-[6px] text-muted hover:bg-surface-muted hover:text-text disabled:opacity-40 ${pressed ? 'bg-accent-soft text-accent' : ''}`}
    >
      {children}
    </button>
  )
}

function PlainView({ src, csv }: { src: string; csv: boolean }) {
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    fetch(src).then(
      async (res) => {
        if (!alive) return
        if (res.ok) setText(await res.text())
        else setError("This file isn't available any more.")
      },
      () => alive && setError('Could not reach the PinPoint server.'),
    )
    return () => {
      alive = false
    }
  }, [src])
  if (error) return <Message text={error} />
  if (text === null) return <Loading />
  const rows = csv ? text.split(/\r?\n/).filter((l) => l.trim()).map((l) => l.split(',').map((c) => c.trim().replace(/^"|"$/g, ''))) : null
  return (
    <div className="p-6" id="viewer-page-1" data-page="1">
      <div className="mx-auto max-w-[820px] rounded-card border border-border bg-surface p-8">
        {rows ? <BlockText text={text} table={rows} /> : <p className="text-body whitespace-pre-wrap text-text">{text}</p>}
      </div>
    </div>
  )
}

function Loading() {
  return (
    <p className="flex items-center justify-center gap-2 py-16 text-small text-muted">
      <Loader2 size={16} strokeWidth={2} className="animate-spin text-accent" />
      Loading…
    </p>
  )
}

function Message({ text }: { text: string }) {
  return <p className="py-16 text-center text-small text-muted">{text}</p>
}
