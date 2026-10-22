// Picking a whole folder in the browser and keeping only files PinPoint can read.

export const SUPPORTED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'docx', 'xlsx', 'pptx', 'csv', 'md', 'txt']
export const ACCEPT = SUPPORTED_EXTENSIONS.map((e) => `.${e}`).join(',')
const SKIP_DIRS = new Set(['node_modules', '.git', '__pycache__'])
const MAX_DEPTH = 5

export function isSupported(name: string): boolean {
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : ''
  return SUPPORTED_EXTENSIONS.includes(ext)
}

function skipDir(name: string): boolean {
  return name.startsWith('.') || SKIP_DIRS.has(name)
}

// Minimal File System Access API types (Chrome, Edge); not in TypeScript's DOM lib.
type FsFileHandle = { kind: 'file'; name: string; getFile: () => Promise<File> }
type FsDirHandle = { kind: 'directory'; name: string; values: () => AsyncIterable<FsFileHandle | FsDirHandle> }
type DirectoryPickerWindow = Window & { showDirectoryPicker?: (opts?: { mode?: 'read' }) => Promise<FsDirHandle> }

export function canPickDirectory(): boolean {
  return typeof (window as DirectoryPickerWindow).showDirectoryPicker === 'function'
}

async function walk(dir: FsDirHandle, depth: number, out: File[]): Promise<void> {
  for await (const entry of dir.values()) {
    if (entry.kind === 'directory') {
      if (depth < MAX_DEPTH && !skipDir(entry.name)) await walk(entry, depth + 1, out)
    } else if (!entry.name.startsWith('.') && isSupported(entry.name)) {
      out.push(await entry.getFile())
    }
  }
}

/** Opens the native folder picker. Returns null if the user cancels. */
export async function pickDirectoryFiles(): Promise<File[] | null> {
  const picker = (window as DirectoryPickerWindow).showDirectoryPicker
  if (!picker) return null
  let dir: FsDirHandle
  try {
    dir = await picker({ mode: 'read' })
  } catch {
    return null // Cancelled.
  }
  const files: File[] = []
  await walk(dir, 0, files)
  return files
}

/** Filters the files from an <input webkitdirectory>, skipping hidden folders. */
export function filterFolderInput(list: FileList): File[] {
  return Array.from(list).filter((file) => {
    const parts = (file.webkitRelativePath || file.name).split('/')
    return parts.length - 1 <= MAX_DEPTH + 1 && !parts.slice(0, -1).some(skipDir) && !file.name.startsWith('.') && isSupported(file.name)
  })
}
