import { ArrowLeft, Loader2, Maximize2, Minimize2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, rawUrl } from '../lib/api'
import type { FileText, FileType } from '../lib/types'
import { BlockText } from './BlockText'
import { Button } from './Button'

export type ViewerFile = { id: string; name: string; type: FileType; page?: number }

type DocumentViewerProps = { ws: string; file: ViewerFile; onClose: () => void }

const extension = (name: string) => name.split('.').pop()?.toLowerCase() ?? ''

// Not in Figma: a full-screen reader on the app's tokens. PDFs use the browser's own viewer
// (opened at the cited page), images zoom, plain text shows as-is, and office files show
// the parsed text page by page (browsers can't render them).
export function DocumentViewer({ ws, file, onClose }: DocumentViewerProps) {
  const backRef = useRef<HTMLButtonElement>(null)
  const raw = rawUrl(ws, file.id)
  const ext = extension(file.name)
  const mode = !raw ? 'parsed' : file.type === 'pdf' ? 'pdf' : file.type === 'image' ? 'image' : ['md', 'txt', 'csv'].includes(ext) ? 'plain' : 'parsed'

  useEffect(() => {
    backRef.current?.focus()
    // Capture Escape first so it closes only the viewer, not the citation panel underneath.
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.stopImmediatePropagation()
      onClose()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [onClose])

  return (
    <div role="dialog" aria-label={`Document: ${file.name}`} className="fixed inset-0 z-50 flex flex-col bg-bg">
      <header className="flex items-center gap-4 border-b border-border bg-surface px-6 py-3">
        <Button ref={backRef} variant="secondary" Icon={ArrowLeft} onClick={onClose}>
          Back
        </Button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-h3 text-text">{file.name}</p>
          {file.page && file.type !== 'image' && <p className="text-label text-muted">Opened at page {file.page}</p>}
        </div>
      </header>
      <div className="min-h-0 flex-1">
        {mode === 'pdf' && (
          <iframe title={file.name} src={`${raw}#page=${file.page ?? 1}`} className="h-full w-full border-0 bg-surface-muted" />
        )}
        {mode === 'image' && <ImageView src={raw!} name={file.name} />}
        {mode === 'plain' && <PlainView src={raw!} csv={ext === 'csv'} />}
        {mode === 'parsed' && <ParsedView ws={ws} file={file} />}
      </div>
    </div>
  )
}

function ImageView({ src, name }: { src: string; name: string }) {
  const [fit, setFit] = useState(true)
  return (
    <div className="relative h-full overflow-auto bg-surface-muted p-6">
      <div className="sticky top-0 z-10 flex justify-end">
        <Button variant="secondary" Icon={fit ? Maximize2 : Minimize2} onClick={() => setFit((f) => !f)}>
          {fit ? 'Actual size' : 'Fit to screen'}
        </Button>
      </div>
      <div className={`flex justify-center ${fit ? 'h-[calc(100%-56px)] items-center' : ''}`}>
        <img
          src={src}
          alt={name}
          onClick={() => setFit((f) => !f)}
          className={`rounded-control border border-border bg-surface ${
            fit ? 'max-h-full max-w-full cursor-zoom-in object-contain' : 'max-w-none cursor-zoom-out'
          }`}
        />
      </div>
    </div>
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
    <div className="h-full overflow-auto px-12 py-8">
      <div className="mx-auto max-w-[820px] rounded-card border border-border bg-surface p-8 shadow-subtle">
        {rows ? <BlockText text={text} table={rows} /> : <p className="text-body whitespace-pre-wrap text-text">{text}</p>}
      </div>
    </div>
  )
}

function ParsedView({ ws, file }: { ws: string; file: ViewerFile }) {
  const [doc, setDoc] = useState<FileText | null>(null)
  const [error, setError] = useState<string | null>(null)
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
  useEffect(() => {
    if (doc && file.page) document.getElementById(`doc-page-${file.page}`)?.scrollIntoView({ block: 'start' })
  }, [doc, file.page])
  if (error) return <Message text={error} />
  if (!doc) return <Loading />
  if (doc.pages.length === 0) return <Message text="No text was found in this file." />
  return (
    <div className="h-full overflow-auto px-12 py-8">
      <div className="mx-auto flex max-w-[820px] flex-col gap-6">
        <p className="text-small text-muted">Browsers can't display this file type, so this is the text PinPoint read from it.</p>
        {doc.pages.map((p) => (
          <section
            key={p.page}
            id={`doc-page-${p.page}`}
            className={`flex flex-col gap-3 rounded-card border bg-surface p-6 shadow-subtle ${
              p.page === file.page ? 'border-accent' : 'border-border'
            }`}
          >
            <p className="text-eyebrow text-muted uppercase">Page {p.page}</p>
            {p.blocks.map((b, i) => (
              <BlockText key={i} text={b.text} table={b.table} />
            ))}
          </section>
        ))}
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
