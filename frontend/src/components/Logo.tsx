type LogoProps = {
  /** Image size in px: 28 in the sidebar, 24 for small uses (footer, headers). */
  size?: number
  className?: string
}

/** The full-color PinPoint mark (local file, never recolored), e.g. 64-96px on a hero or empty state. */
export function LogoMark({ size = 28, className = '' }: { size?: number; className?: string }) {
  return (
    <img
      src="/pinpoint-logo.png"
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      draggable={false}
      className={`shrink-0 select-none ${className}`}
    />
  )
}

// Figma "Logo" (3:158): the mark plus the "PinPoint" wordmark, which carries the accessible name.
export function Logo({ size = 28, className = '' }: LogoProps) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <LogoMark size={size} />
      <span className="text-h3 text-text">PinPoint</span>
    </div>
  )
}
