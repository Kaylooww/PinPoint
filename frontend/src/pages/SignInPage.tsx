import { Link } from 'react-router-dom'

// Placeholder; built from Figma 8:1110 in a later step.
export function SignInPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg">
      <h1 className="text-h1 text-text">Sign in</h1>
      <Link to="/workspaces" className="rounded-control bg-accent px-4 py-[9px] font-medium text-on-accent hover:bg-accent-hover">
        Continue
      </Link>
    </div>
  )
}
