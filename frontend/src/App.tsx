import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { AskPage } from './pages/AskPage'
import { FilesPage } from './pages/FilesPage'
import { LandingPage } from './pages/LandingPage'
import { MemoryPage } from './pages/MemoryPage'
import { SettingsPage } from './pages/SettingsPage'
import { SignInPage } from './pages/SignInPage'
import { WorkspaceLayout } from './pages/WorkspaceLayout'
import { WorkspacesPage } from './pages/WorkspacesPage'

export default function App() {
  return (
    <Routes>
      {/* Temporary for the demo: "/" opens the Ask tab of the demo workspace. */}
      <Route path="/" element={<Navigate to="/w/reyes-partners/ask" replace />} />
      <Route path="/landing" element={<LandingPage />} />
      <Route path="/signin" element={<SignInPage />} />
      <Route element={<AppShell />}>
        <Route path="/workspaces" element={<WorkspacesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/w/:id" element={<WorkspaceLayout />}>
          <Route index element={<Navigate to="files" replace />} />
          <Route path="files" element={<FilesPage />} />
          <Route path="ask" element={<AskPage />} />
          <Route path="memory" element={<MemoryPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
