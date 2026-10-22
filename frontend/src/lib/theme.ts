export type ThemeChoice = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'pinpoint-theme'

export function getStoredTheme(): ThemeChoice {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value === 'light' || value === 'dark') return value
  } catch {
    // Storage unavailable; fall back to the system setting.
  }
  return 'system'
}

export function storeTheme(choice: ThemeChoice): void {
  try {
    if (choice === 'system') localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, choice)
  } catch {
    // Ignore; the choice just won't be remembered.
  }
}

export function resolveTheme(choice: ThemeChoice): 'light' | 'dark' {
  if (choice !== 'system') return choice
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.classList.toggle('dark', resolveTheme(choice) === 'dark')
}
