import { BookMarked, FileText, Folder, LayoutGrid, MessageSquare, SlidersHorizontal } from 'lucide-react'
import { useLocation, useMatch } from 'react-router-dom'
import { useWorkspaces } from '../lib/workspaces'
import { Logo } from './Logo'
import { SidebarItem } from './SidebarItem'
import { ThemeToggle } from './ThemeToggle'

// Figma "Sidebar" (4:209): brand, nav, clients, theme toggle, user.
export function Sidebar() {
  const { pathname } = useLocation()
  const match = useMatch('/w/:id/:tab')
  const { workspaces } = useWorkspaces()

  const currentId = match?.params.id
  const tab = match?.params.tab

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col gap-6 border-r border-border bg-surface px-4 pt-5 pb-4">
      <div className="px-2.5 py-1">
        <Logo />
      </div>

      <nav className="flex flex-col gap-0.5" aria-label="Main">
        <SidebarItem to="/workspaces" label="Workspaces" Icon={LayoutGrid} active={pathname === '/workspaces'} />
        {/* Inside a workspace, Figma highlights the client entry, not these shortcuts. */}
        <SidebarItem to="/files" label="Files" Icon={FileText} active={pathname === '/files'} />
        <SidebarItem to="/ask" label="Ask" Icon={MessageSquare} active={pathname === '/ask'} />
        <SidebarItem to="/memory" label="Memory" Icon={BookMarked} active={pathname === '/memory'} />
        <SidebarItem to="/settings" label="Settings" Icon={SlidersHorizontal} active={pathname === '/settings'} />
      </nav>

      <nav className="flex min-h-0 flex-col gap-0.5" aria-label="Clients">
        <p className="pb-1.5 pl-2.5 text-eyebrow text-muted uppercase">Clients</p>
        <div className="flex min-h-0 flex-col gap-0.5 overflow-y-auto">
          {workspaces.map((ws) => (
            <SidebarItem
              key={ws.id}
              to={`/w/${ws.id}/${tab ?? 'files'}`}
              label={ws.name}
              Icon={Folder}
              active={ws.id === currentId}
            />
          ))}
        </div>
      </nav>

      <div className="mt-auto flex flex-col gap-3.5">
        <ThemeToggle />
        <div className="flex items-center gap-2.5 border-t border-border pt-3.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-pill bg-accent-soft text-label text-accent">
            LD
          </div>
          <div className="min-w-0 font-medium">
            <p className="truncate text-body text-text">Luther Dira</p>
            <p className="truncate text-label text-muted">luther@reyeslaw.ph</p>
          </div>
        </div>
      </div>
    </aside>
  )
}
