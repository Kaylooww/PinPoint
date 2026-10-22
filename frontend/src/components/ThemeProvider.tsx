import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ThemeContext,
  getStoredTheme,
  storeTheme,
  systemTheme,
  type ResolvedTheme,
  type ThemeChoice,
} from '../lib/theme'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoice] = useState<ThemeChoice>(getStoredTheme)
  const [system, setSystem] = useState<ResolvedTheme>(systemTheme)

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setSystem(media.matches ? 'dark' : 'light')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const resolved = choice === 'system' ? system : choice

  useEffect(() => {
    document.documentElement.classList.toggle('dark', resolved === 'dark')
  }, [resolved])

  const value = useMemo(
    () => ({
      choice,
      resolved,
      setChoice: (next: ThemeChoice) => {
        storeTheme(next)
        setChoice(next)
      },
    }),
    [choice, resolved],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
