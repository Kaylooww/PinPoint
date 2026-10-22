import { Briefcase, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import type { CreateWorkspaceRequest } from '../lib/types'
import { Button } from './Button'
import { Field } from './Field'

const INDUSTRIES = ['Law office', 'Real estate', 'Accounting', 'Insurance', 'Other']

type NewWorkspaceDialogProps = {
  onCreate: (body: CreateWorkspaceRequest) => Promise<void>
  onClose: () => void
}

// Not in Figma: a modal built from Field and Button, on the scrim token.
export function NewWorkspaceDialog({ onCreate, onClose }: NewWorkspaceDialogProps) {
  const [name, setName] = useState('')
  const [industry, setIndustry] = useState(INDUSTRIES[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const industryId = useId()

  useEffect(() => {
    nameRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      await onCreate({ name: name.trim(), industry })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the workspace.')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-scrim p-4" onMouseDown={onClose}>
      <form
        role="dialog"
        aria-label="New workspace"
        onSubmit={submit}
        onMouseDown={(e) => e.stopPropagation()}
        className="flex w-full max-w-[440px] flex-col gap-5 rounded-card border border-border bg-surface p-6 shadow-panel"
      >
        <header className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-control bg-accent-soft text-accent">
              <Briefcase size={20} strokeWidth={1.75} />
            </div>
            <div>
              <h2 className="text-h2 text-text">New workspace</h2>
              <p className="text-small text-muted">One workspace per client.</p>
            </div>
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

        <Field
          ref={nameRef}
          label="Client name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Santos Realty"
          maxLength={120}
        />

        <div className="flex flex-col gap-1.5">
          <label htmlFor={industryId} className="text-label text-text">
            Industry
          </label>
          <select
            id={industryId}
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="w-full rounded-control border border-border bg-surface px-3 py-2.5 text-body text-text focus:border-accent focus:outline-none"
          >
            {INDUSTRIES.map((i) => (
              <option key={i}>{i}</option>
            ))}
          </select>
        </div>

        {error && (
          <p role="alert" className="text-small text-danger">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!name.trim() || busy}>
            {busy ? 'Creating…' : 'Create workspace'}
          </Button>
        </div>
      </form>
    </div>
  )
}
