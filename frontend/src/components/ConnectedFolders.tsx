import { Folder as FolderIcon, RefreshCw, Unplug } from 'lucide-react'
import { timeAgo } from '../lib/format'
import type { Folder } from '../lib/types'
import { Button } from './Button'
import { StatusBadge } from './StatusBadge'

type ConnectedFoldersProps = {
  folders: Folder[]
  onRescan: (folder: Folder) => void
  onDisconnect: (folder: Folder) => void
}

const STATUS = { scanning: 'parsing', ready: 'ready', failed: 'failed' } as const

// Not in Figma: rows styled like File Row, with folder actions.
export function ConnectedFolders({ folders, onRescan, onDisconnect }: ConnectedFoldersProps) {
  return (
    <section className="flex flex-col gap-3" aria-label="Connected folders">
      <h2 className="text-body font-semibold text-text">Connected folders</h2>
      {folders.length === 0 ? (
        <p className="text-small text-muted">
          No connected folders. Use Add files → Connect a local folder to read a folder on this computer in place.
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {folders.map((folder) => (
            <div key={folder.id} className="flex items-center gap-3.5 rounded-control border border-border bg-surface px-4 py-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-control bg-accent-soft text-accent">
                <FolderIcon size={18} strokeWidth={1.75} />
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <p className="truncate text-body font-medium text-text" title={folder.path}>
                  {folder.path}
                </p>
                {folder.status === 'failed' ? (
                  <p className="text-small text-danger">{folder.error ?? "Couldn't read this folder."}</p>
                ) : (
                  <p className="truncate text-small text-muted">
                    {folder.file_count} file{folder.file_count === 1 ? '' : 's'}
                    {folder.last_scanned_at ? ` · Scanned ${timeAgo(folder.last_scanned_at)}` : ' · Scanning for the first time'}
                  </p>
                )}
              </div>
              <StatusBadge status={STATUS[folder.status]} label={folder.status === 'scanning' ? 'Scanning' : undefined} />
              <Button variant="ghost" Icon={RefreshCw} disabled={folder.status === 'scanning'} onClick={() => onRescan(folder)}>
                Rescan
              </Button>
              <Button variant="ghost" Icon={Unplug} onClick={() => onDisconnect(folder)}>
                Disconnect
              </Button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
