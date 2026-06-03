import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import { localizeDigits, parseLocalizedNumber } from '../lib/numerals'
import { useI18n } from '../i18n'

interface FieldShellProps {
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
  className?: string
}

const FIELD_BASE = 'bg-white ring-1 ring-inset transition-shadow duration-150'
const FIELD_OK = 'ring-line focus-within:ring-2 focus-within:ring-tech-blue/60'
const FIELD_ERR = 'ring-brand-300 focus-within:ring-2 focus-within:ring-brand-500/70'

function labelEl(label?: ReactNode) {
  return label ? (
    <span className="block mb-1.5 text-sm font-semibold text-ink-800">{label}</span>
  ) : null
}

function footEl(error?: ReactNode, hint?: ReactNode) {
  if (error)
    return <span className="block mt-1.5 text-xs text-brand-600 font-medium">{error}</span>
  if (hint) return <span className="block mt-1.5 text-xs text-faint">{hint}</span>
  return null
}

interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'className'>,
    FieldShellProps {
  trailing?: ReactNode
  leading?: ReactNode
}

export function Input({
  label,
  hint,
  error,
  trailing,
  leading,
  className = '',
  ...rest
}: InputProps) {
  return (
    <label className={['block', className].join(' ')}>
      {labelEl(label)}
      <span
        className={[
          'flex items-center gap-2 h-12 px-4 rounded-2xl',
          FIELD_BASE,
          error ? FIELD_ERR : FIELD_OK,
        ].join(' ')}
      >
        {leading ? <span className="text-faint shrink-0">{leading}</span> : null}
        <input
          {...rest}
          className="flex-1 bg-transparent outline-none text-[15px] text-fg placeholder:text-ink-400 num-fa min-w-0"
        />
        {trailing ? <span className="text-muted shrink-0">{trailing}</span> : null}
      </span>
      {footEl(error, hint)}
    </label>
  )
}

interface TextareaProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'className'>,
    FieldShellProps {}

export function Textarea({ label, hint, error, className = '', ...rest }: TextareaProps) {
  return (
    <label className={['block', className].join(' ')}>
      {labelEl(label)}
      <textarea
        {...rest}
        className={[
          'block w-full rounded-2xl px-4 py-3 text-[15px] text-fg outline-none resize-none',
          'placeholder:text-ink-400 num-fa',
          FIELD_BASE,
          error ? FIELD_ERR : FIELD_OK,
        ].join(' ')}
      />
      {footEl(error, hint)}
    </label>
  )
}

interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'className'>,
    FieldShellProps {
  children: ReactNode
}

export function Select({
  label,
  hint,
  error,
  className = '',
  children,
  ...rest
}: SelectProps) {
  return (
    <label className={['block', className].join(' ')}>
      {labelEl(label)}
      <span
        className={[
          'flex items-center gap-2 h-12 px-3 rounded-2xl',
          FIELD_BASE,
          error ? FIELD_ERR : FIELD_OK,
        ].join(' ')}
      >
        <select
          {...rest}
          className="flex-1 bg-transparent outline-none text-[15px] text-fg appearance-none cursor-pointer"
        >
          {children}
        </select>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-faint">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </span>
      {footEl(error, hint)}
    </label>
  )
}

interface NumberInputProps
  extends Omit<
      InputHTMLAttributes<HTMLInputElement>,
      'className' | 'value' | 'onChange' | 'type'
    >,
    FieldShellProps {
  value: number | null
  onValueChange: (v: number | null) => void
  min?: number
  max?: number
  trailing?: ReactNode
  leading?: ReactNode
}

export function NumberInput({
  label,
  hint,
  error,
  value,
  onValueChange,
  min,
  max,
  trailing,
  leading,
  className = '',
  ...rest
}: NumberInputProps) {
  const { lang } = useI18n()
  const display = value === null || value === undefined ? '' : localizeDigits(value, lang)
  return (
    <Input
      {...rest}
      label={label}
      hint={hint}
      error={error}
      className={className}
      leading={leading}
      trailing={trailing}
      value={display}
      inputMode="decimal"
      onChange={(e) => {
        const parsed = parseLocalizedNumber(e.target.value)
        if (parsed === null) {
          onValueChange(null)
          return
        }
        let next = parsed
        if (typeof min === 'number' && next < min) next = min
        if (typeof max === 'number' && next > max) next = max
        onValueChange(next)
      }}
    />
  )
}
