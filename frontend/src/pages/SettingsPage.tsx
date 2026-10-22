import { ThemeToggle } from '../components/ThemeToggle'

// Placeholder; built from Figma 9:1023 in a later step.
export function SettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-h1 text-text">Settings</h1>
      <div className="flex flex-col gap-2">
        <h2 className="text-h3 text-text">Theme</h2>
        <ThemeToggle showLabels />
      </div>
    </div>
  )
}
