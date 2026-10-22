import { Link } from 'react-router-dom'

// Placeholder; built from Figma 8:845 in a later step.
export function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg">
      <h1 className="font-serif text-hero text-text">PinPoint</h1>
      <Link to="/signin" className="rounded-control bg-accent px-4 py-[9px] font-medium text-on-accent hover:bg-accent-hover">
        Get started
      </Link>
    </div>
  )
}
