import { BookMarked, FileText, Folder, LayoutGrid, MessageSquare, SlidersHorizontal } from 'lucide-react'
import { useEffect } from 'react'
import { useLocation, useMatch } from 'react-router-dom'
import { getLastWorkspaceId, setLastWorkspaceId, useWorkspaces } from '../lib/workspaces'
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

  useEffect(() => {
    if (currentId) setLastWorkspaceId(currentId)
  }, [currentId])

  const lastId = getLastWorkspaceId()
  const wsId =
    currentId ??
    (lastId && workspaces.some((w) => w.id === lastId) ? lastId : workspaces[0]?.id)
  const wsLink = (t: string) => (wsId ? `/w/${wsId}/${t}` : '/workspaces')

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col gap-6 border-r border-border bg-surface px-4 pt-5 pb-4">
      <div className="px-2.5 py-1">
        <Logo />
      </div>

      <nav className="flex flex-col gap-0.5" aria-label="Main">
        <SidebarItem to="/workspaces" label="Workspaces" Icon={LayoutGrid} active={pathname === '/workspaces'} />
        {/* Inside a workspace, Figma highlights the client entry, not these shortcuts. */}
        <SidebarItem to={wsLink('files')} label="Files" Icon={FileText} />
        <SidebarItem to={wsLink('ask')} label="Ask" Icon={MessageSquare} />
        <SidebarItem to={wsLink('memory')} label="Memory" Icon={BookMarked} />
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
            MR
          </div>
          <div className="min-w-0 font-medium">
            <p className="truncate text-body text-text">Maria Reyes</p>
            <p className="truncate text-label text-muted">maria@reyeslaw.ph</p>
          </div>
        </div>
      </div>
    </aside>
  )
}
