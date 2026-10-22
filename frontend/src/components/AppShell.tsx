import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { WorkspacesProvider } from './WorkspacesProvider'

// 256px sidebar plus a main area padded 48px (docs/DESIGN.md, Layout).
export function AppShell() {
  return (
    <WorkspacesProvider>
      <div className="flex min-h-screen bg-bg">
        <Sidebar />
        <main className="min-w-0 flex-1 px-12 pt-8 pb-10">
          <Outlet />
        </main>
      </div>
    </WorkspacesProvider>
  )
}
