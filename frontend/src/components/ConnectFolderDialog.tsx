import { FolderOpen, FolderSearch, ShieldCheck, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import { Button } from './Button'
import { Field } from './Field'

type ConnectFolderDialogProps = {
  onConnect: (path: string) => Promise<void>
  onClose: () => void
}

// Not in Figma: a modal built from Field and Button, on the scrim token.
export function ConnectFolderDialog({ onConnect, onClose }: ConnectFolderDialogProps) {
  const [path, setPath] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [choosing, setChoosing] = useState(false)
  const [pickerFailed, setPickerFailed] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const browseRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    browseRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  // Opens Finder / File Explorer on this computer; the path still goes through POST /folders checks.
  const browse = async () => {
    setChoosing(true)
    setPickerFailed(false)
    try {
      const picked = await api.pickFolder()
      if (picked) {
        setPath(picked)
        setError(null)
      }
    } catch {
      setPickerFailed(true)
      inputRef.current?.focus()
    } finally {
      setChoosing(false)
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!path.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      await onConnect(path.trim())
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not connect that folder.')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-scrim p-4" onMouseDown={onClose}>
      <form
        role="dialog"
        aria-label="Connect a local folder"
        onSubmit={submit}
        onMouseDown={(e) => e.stopPropagation()}
        className="flex w-full max-w-[480px] flex-col gap-5 rounded-card border border-border bg-surface p-6 shadow-panel"
      >
        <header className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-control bg-accent-soft text-accent">
              <FolderOpen size={20} strokeWidth={1.75} />
            </div>
            <h2 className="text-h2 text-text">Connect a local folder</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex size-8 items-center justify-center rounded-control text-muted hover:bg-surface-muted hover:text-text"
          >
            <X size={16} strokeWidth={1.75} />
          </button>
        </header>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-end gap-2">
            <Field
              ref={inputRef}
              label="Folder path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/Users/you/Documents/Reyes Client Files"
              spellCheck={false}
              autoComplete="off"
              className="min-w-0 flex-1"
            />
            <Button ref={browseRef} variant="secondary" Icon={FolderSearch} onClick={() => void browse()} disabled={choosing}>
              {choosing ? 'Choosing…' : 'Browse…'}
            </Button>
          </div>
          <p className="text-label text-muted" aria-live="polite">
            {pickerFailed ? "Couldn't open the folder picker. Type the path instead." : 'Choose a folder, or paste its path.'}
          </p>
        </div>

        <p className="flex gap-2.5 rounded-control bg-surface-muted px-3.5 py-3 text-small text-muted">
          <ShieldCheck size={16} strokeWidth={1.75} className="mt-0.5 shrink-0 text-success" />
          PinPoint reads this folder on this computer. It never changes or deletes your files.
        </p>

        {error && (
          <p role="alert" className="text-small text-danger">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!path.trim() || busy}>
            {busy ? 'Connecting…' : 'Connect folder'}
          </Button>
        </div>
      </form>
    </div>
  )
}
