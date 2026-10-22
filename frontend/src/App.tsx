import { Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { applyTheme, getStoredTheme, storeTheme, type ThemeChoice } from './lib/theme'

const OPTIONS: { value: ThemeChoice; label: string; Icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
]

const SWATCHES = [
  'bg', 'surface', 'surface-muted', 'border', 'text', 'text-muted', 'accent', 'accent-soft',
  'highlight', 'success', 'warning', 'danger',
]

export default function App() {
  const [theme, setTheme] = useState<ThemeChoice>(getStoredTheme)

  useEffect(() => {
    applyTheme(theme)
    storeTheme(theme)
    if (theme !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => applyTheme('system')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [theme])

  return (
    <main className="mx-auto max-w-3xl px-12 py-12">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase leading-4 tracking-[0.08em] text-muted">
          Setup check
        </span>
        <div className="flex gap-1 rounded-control border border-border bg-surface p-1">
          {OPTIONS.map(({ value, label, Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setTheme(value)}
              aria-pressed={theme === value}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-[12px] font-medium leading-4 ${
                theme === value ? 'bg-accent-soft text-accent' : 'text-muted hover:text-text'
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </div>

      <h1 className="mt-8 font-serif text-[72px] leading-none">PinPoint</h1>
      <p className="mt-4 text-muted">
        Ask a question across every file. Get the answer and the exact place it came from.
      </p>

      <section className="mt-10 rounded-card border border-border bg-surface p-6 shadow-card">
        <h2 className="text-[18px] font-semibold leading-[26px]">Theme tokens</h2>
        <div className="mt-4 grid grid-cols-4 gap-3">
          {SWATCHES.map((token) => (
            <div key={token} className="text-[12px] leading-4">
              <div
                className="h-10 rounded-control border border-border"
                style={{ background: `var(--${token})` }}
              />
              <code className="mt-1 block text-muted">--{token}</code>
            </div>
          ))}
        </div>
        <p className="mt-6 font-serif text-[18px]">
          <span className="rounded-sm bg-highlight px-1">Citation highlight sample</span>
        </p>
        <button
          type="button"
          className="mt-6 rounded-control bg-accent px-4 py-2 font-medium text-on-accent hover:bg-accent-hover"
        >
          Primary button
        </button>
      </section>
    </main>
  )
}
