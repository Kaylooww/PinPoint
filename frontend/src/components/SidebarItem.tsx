import type { LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

type SidebarItemProps = {
  to: string
  label: string
  Icon: LucideIcon
  active?: boolean
}

// Figma "Sidebar Item" (Default, Active).
export function SidebarItem({ to, label, Icon, active = false }: SidebarItemProps) {
  return (
    <Link
      to={to}
      aria-current={active ? 'page' : undefined}
      className={`flex w-full items-center gap-2.5 rounded-control px-2.5 py-2 text-body font-medium ${
        active ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-surface-muted hover:text-text'
      }`}
    >
      <Icon size={18} strokeWidth={1.75} className="shrink-0" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
    </Link>
  )
}
