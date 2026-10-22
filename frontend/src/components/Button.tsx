import type { LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent hover:bg-accent-hover',
  secondary: 'border border-border bg-surface text-text hover:bg-surface-muted',
  ghost: 'text-muted hover:bg-surface-muted hover:text-text',
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  Icon?: LucideIcon
}

// Figma "Button" (3:174): Primary for the main action, Secondary for alternatives, Ghost for low emphasis.
export function Button({ variant = 'primary', Icon, className = '', children, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-control px-4 py-[9px] text-body font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {Icon && <Icon size={16} strokeWidth={1.75} />}
      {children}
    </button>
  )
}
