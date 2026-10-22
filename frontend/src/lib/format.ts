import type { FileItem, FileType } from './types'

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatSeconds(ms: number): string {
  const s = ms / 1000
  return `${s < 10 ? s.toFixed(1) : Math.round(s)} second${s === 1 ? '' : 's'}`
}

/** "Today", "Yesterday", or a short date like "Oct 18". */
export function dayLabel(iso: string): string {
  const date = new Date(iso)
  const today = new Date()
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(today) - startOf(date)) / 86_400_000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function fileMeta(file: FileItem): string {
  const parts: string[] = []
  if (file.pages > 0) {
    const unit = file.type === 'sheet' ? 'sheet' : 'page'
    parts.push(`${file.pages} ${unit}${file.pages === 1 ? '' : 's'}`)
  }
  parts.push(formatBytes(file.size_bytes))
  if (file.status === 'queued') parts.push('Waiting to start')
  if (file.source === 'folder' && file.source_path) parts.push(file.source_path)
  return parts.join(' · ')
}

/** "just now", "5 min ago", "3 h ago", then dayLabel(). */
export function timeAgo(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`
  return dayLabel(iso)
}

const TYPE_BY_EXTENSION: Record<string, FileType> = {
  pdf: 'pdf', png: 'image', jpg: 'image', jpeg: 'image', webp: 'image', gif: 'image',
  doc: 'doc', docx: 'doc', md: 'doc', txt: 'doc', xls: 'sheet', xlsx: 'sheet', csv: 'sheet', ppt: 'slides', pptx: 'slides',
}

/** File type from a file name, for citations (which carry only the name). */
export function fileTypeFromName(name: string): FileType {
  return TYPE_BY_EXTENSION[name.split('.').pop()?.toLowerCase() ?? ''] ?? 'other'
}
