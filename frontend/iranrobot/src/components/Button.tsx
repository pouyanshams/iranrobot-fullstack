import { motion } from 'framer-motion'
import type { HTMLMotionProps } from 'framer-motion'
import type { ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'tech'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: Variant
  size?: Size
  leading?: ReactNode
  trailing?: ReactNode
  fullWidth?: boolean
  children?: ReactNode
}

const VARIANT: Record<Variant, string> = {
  primary:
    'text-white bg-brand-600 hover:bg-brand-700 shadow-[0_12px_30px_-12px_rgba(127, 24, 16,0.55)]',
  secondary:
    'text-white bg-ink-900 hover:bg-ink-800',
  ghost:
    'text-muted hover:text-fg hover:bg-ink-100',
  outline:
    'text-fg bg-white border border-line hover:border-line-strong hover:bg-ink-50',
  tech:
    'text-white bg-tech-blue hover:brightness-110 shadow-[0_12px_30px_-12px_rgba(37,99,235,0.45)]',
}

const SIZE: Record<Size, string> = {
  sm: 'h-9 px-4 text-sm rounded-lg gap-1.5',
  md: 'h-11 px-6 text-[15px] rounded-lg gap-2',
  lg: 'h-14 px-6 sm:px-8 text-base rounded-lg gap-2.5',
}

export function Button({
  variant = 'primary',
  size = 'md',
  leading,
  trailing,
  fullWidth,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <motion.button
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      whileHover={{ y: disabled ? 0 : -2 }}
      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
      disabled={disabled}
      className={[
        'relative inline-flex items-center justify-center font-semibold whitespace-nowrap',
        'transition-[background,box-shadow,color,border] duration-200 select-none cursor-pointer',
        'disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:translate-y-0',
        VARIANT[variant],
        SIZE[size],
        fullWidth ? 'w-full' : '',
        className,
      ].join(' ')}
      {...rest}
    >
      {leading}
      {children}
      {trailing}
    </motion.button>
  )
}
