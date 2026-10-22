import { Link } from 'react-router-dom'
import { useWorkspaces } from '../lib/workspaces'

// Placeholder; built from Figma 6:172 in a later step.
export function WorkspacesPage() {
  const { workspaces } = useWorkspaces()
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-h1 text-text">Workspaces</h1>
      <ul className="flex flex-col gap-1">
        {workspaces.map((ws) => (
          <li key={ws.id}>
            <Link to={`/w/${ws.id}/files`} className="text-body text-accent hover:text-accent-hover">
              {ws.name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
