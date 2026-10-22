import { Search } from 'lucide-react'
import { forwardRef, type FormEvent } from 'react'
import { Button } from './Button'

type SearchInputProps = {
  value: string
  onChange: (value: string) => void
  onSubmit: (value: string) => void
  placeholder?: string
  busy?: boolean
}

// Figma "Search Input" (3:198): search icon, question text, Ask button.
export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(function SearchInput(
  { value, onChange, onSubmit, placeholder = 'Ask a question about these files…', busy = false },
  ref,
) {
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim() && !busy) onSubmit(value.trim())
  }
  return (
    <form
      onSubmit={submit}
      className="flex w-full items-center gap-3 rounded-card border border-border bg-surface py-2 pr-2 pl-[18px] shadow-subtle focus-within:border-accent"
    >
      <Search size={20} strokeWidth={1.75} className="shrink-0 text-muted" aria-hidden="true" />
      <input
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Question"
        className="min-w-0 flex-1 bg-transparent text-body text-text placeholder:text-muted focus:outline-none"
      />
      <Button type="submit" disabled={!value.trim() || busy}>
        Ask
      </Button>
    </form>
  )
})
