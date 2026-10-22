import { useId, type ComponentProps } from 'react'

type FieldProps = ComponentProps<'input'> & { label: string }

// Figma "Field" (3:194): label above a bordered input.
export function Field({ label, className = '', id, ...rest }: FieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={inputId} className="text-label text-text">
        {label}
      </label>
      <input
        id={inputId}
        className="w-full rounded-control border border-border bg-surface px-3 py-2.5 text-body text-text placeholder:text-muted focus:border-accent focus:outline-none"
        {...rest}
      />
    </div>
  )
}
