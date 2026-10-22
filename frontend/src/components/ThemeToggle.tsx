import { Monitor, Moon, Sun, type LucideIcon } from 'lucide-react'
import { useTheme, type ThemeChoice } from '../lib/theme'

const OPTIONS: { value: ThemeChoice; label: string; Icon: LucideIcon }[] = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
]

// Figma "Theme Toggle" (4:92): segmented control with Light, Dark, System.
export function ThemeToggle({ showLabels = false }: { showLabels?: boolean }) {
  const { choice, setChoice } = useTheme()

  return (
    <div role="radiogroup" aria-label="Theme" className="inline-flex w-fit gap-0.5 rounded-control bg-surface-muted p-[3px]">
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = choice === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setChoice(value)}
            className={`flex h-7 items-center justify-center gap-1.5 rounded-[6px] text-label ${
              showLabels ? 'px-3' : 'w-7'
            } ${active ? 'bg-surface text-text shadow-subtle' : 'text-muted hover:text-text'}`}
          >
            <Icon size={16} strokeWidth={1.75} />
            {showLabels && label}
          </button>
        )
      })}
    </div>
  )
}
