import { AlertTriangle, ChevronDown, FileUp, FolderUp, Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'
import { useParams } from 'react-router-dom'
import { Button } from '../components/Button'
import { FileRow } from '../components/FileRow'
import { api } from '../lib/api'
import { ACCEPT, canPickDirectory, filterFolderInput, isSupported, pickDirectoryFiles } from '../lib/folders'
import type { FileItem } from '../lib/types'
import { useWorkspaceOutlet } from '../lib/workspaceOutlet'
import { useWorkspaces } from '../lib/workspaces'

const BATCH_SIZE = 10
const POLL_MS = 2000

// Figma 04 Files (6:435).
export function FilesPage() {
  const { id = '' } = useParams()
  const { setActions } = useWorkspaceOutlet()
  const { refresh: refreshWorkspaces } = useWorkspaces()
  const [files, setFiles] = useState<FileItem[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploadMessage, setUploadMessage] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const lastSignature = useRef('')

  const load = useCallback(
    () =>
      api.listFiles(id).then(
        (list) => {
          setFiles(list)
          setLoadError(null)
          // Keep the tab count and sidebar fresh when files appear or finish.
          const signature = list.map((f) => `${f.id}:${f.status}`).join(',')
          if (signature !== lastSignature.current) {
            if (lastSignature.current) void refreshWorkspaces()
            lastSignature.current = signature
          }
        },
        (e: unknown) => setLoadError(e instanceof Error ? e.message : 'Could not load files.'),
      ),
    [id, refreshWorkspaces],
  )

  useEffect(() => {
    void load()
  }, [load])

  const busy = files?.some((f) => f.status === 'queued' || f.status === 'parsing') ?? false
  useEffect(() => {
    if (!busy) return
    const timer = setInterval(() => void load(), POLL_MS)
    return () => clearInterval(timer)
  }, [busy, load])

  const upload = useCallback(
    async (picked: File[]) => {
      const supported = picked.filter((f) => isSupported(f.name))
      const skipped = picked.length - supported.length
      setUploadError(null)
      if (supported.length === 0) {
        setUploadError(picked.length ? 'None of those files are a supported type.' : null)
        return
      }
      try {
        for (let i = 0; i < supported.length; i += BATCH_SIZE) {
          const batch = supported.slice(i, i + BATCH_SIZE)
          setUploadMessage(
            supported.length > BATCH_SIZE
              ? `Uploading ${i + batch.length} of ${supported.length} files…`
              : `Uploading ${supported.length} file${supported.length === 1 ? '' : 's'}…`,
          )
          await api.uploadFiles(id, batch)
        }
        if (skipped) setUploadError(`Skipped ${skipped} unsupported file${skipped === 1 ? '' : 's'}.`)
      } catch (e) {
        setUploadError(e instanceof Error ? e.message : 'Upload failed.')
      } finally {
        setUploadMessage(null)
        await load()
      }
    },
    [id, load],
  )

  const uploadFolder = useCallback(async () => {
    if (canPickDirectory()) {
      const picked = await pickDirectoryFiles()
      if (picked) await upload(picked)
    } else {
      folderInput.current?.click()
    }
  }, [upload])

  useEffect(() => {
    setActions(<AddFilesMenu onFiles={() => fileInput.current?.click()} onFolder={() => void uploadFolder()} />)
    return () => setActions(null)
  }, [setActions, uploadFolder])

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    void upload(Array.from(e.dataTransfer.files))
  }

  return (
    <div className="flex flex-col gap-5">
      <input
        ref={fileInput}
        type="file"
        multiple
        accept={ACCEPT}
        hidden
        onChange={(e) => {
          if (e.target.files) void upload(Array.from(e.target.files))
          e.target.value = ''
        }}
      />
      <input
        ref={folderInput}
        type="file"
        hidden
        // webkitdirectory isn't in React's input props, so set it as an attribute.
        {...{ webkitdirectory: '' }}
        onChange={(e) => {
          if (e.target.files) void upload(filterFolderInput(e.target.files))
          e.target.value = ''
        }}
      />

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center gap-2.5 rounded-card border border-dashed py-[22px] ${
          dragging ? 'border-accent bg-accent-soft' : 'border-border bg-surface'
        }`}
      >
        <div className="flex size-11 items-center justify-center rounded-pill bg-accent-soft text-accent">
          <Upload size={20} strokeWidth={1.75} />
        </div>
        {uploadMessage ? (
          <p className="text-body font-medium text-text" aria-live="polite">
            {uploadMessage}
          </p>
        ) : (
          <p className="text-body font-medium text-text">
            Drop files here, or{' '}
            <button type="button" onClick={() => fileInput.current?.click()} className="text-accent hover:text-accent-hover">
              browse
            </button>
          </p>
        )}
        <p className="text-small text-muted">Photos, scans, PDF, Word, Excel, and PowerPoint · Up to 50 MB each</p>
      </div>

      {uploadError && (
        <p role="alert" className="flex items-center gap-2 text-small text-danger">
          <AlertTriangle size={14} strokeWidth={1.75} />
          {uploadError}
        </p>
      )}

      {loadError && !files ? (
        <div role="alert" className="flex items-center gap-3 rounded-card border border-border bg-danger-soft px-5 py-4">
          <AlertTriangle size={18} strokeWidth={1.75} className="shrink-0 text-danger" />
          <p className="flex-1 text-small text-text">{loadError}</p>
          <Button variant="secondary" onClick={() => void load()}>
            Retry
          </Button>
        </div>
      ) : files === null ? (
        <div className="flex flex-col gap-1.5" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-[70px] animate-pulse rounded-control border border-border bg-surface" />
          ))}
        </div>
      ) : (
        <section className="flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <h2 className="text-body font-semibold text-text">
              {files.length} file{files.length === 1 ? '' : 's'}
            </h2>
            <span className="text-label text-muted">Sorted by: Recently added</span>
          </div>
          {files.length === 0 ? (
            <p className="text-small text-muted">No files yet. Upload PDFs, scans, photos, or spreadsheets to start asking questions.</p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {files.map((file) => (
                <FileRow key={file.id} file={file} />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function AddFilesMenu({ onFiles, onFolder }: { onFiles: () => void; onFolder: () => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const choose = (action: () => void) => () => {
    setOpen(false)
    action()
  }

  return (
    <div ref={ref} className="relative">
      <Button aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        Add files
        <ChevronDown size={16} strokeWidth={1.75} />
      </Button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1.5 flex w-56 flex-col rounded-control border border-border bg-surface p-1 shadow-panel"
        >
          <MenuItem Icon={FileUp} label="Upload files" onClick={choose(onFiles)} />
          <MenuItem Icon={FolderUp} label="Upload a folder" onClick={choose(onFolder)} />
        </div>
      )}
    </div>
  )
}

function MenuItem({ Icon, label, onClick }: { Icon: typeof FileUp; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className="flex items-center gap-2.5 rounded-[6px] px-2.5 py-2 text-left text-body text-text hover:bg-surface-muted"
    >
      <Icon size={16} strokeWidth={1.75} className="text-muted" />
      {label}
    </button>
  )
}
