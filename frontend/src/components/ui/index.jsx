/**
 * shadcn-equivalent primitives, hand-rolled.
 *
 * shadcn/ui is a copy-paste library on top of Radix; pulling in the real thing would mean a dozen
 * Radix packages for the handful of primitives this app uses. These are the same API shapes and
 * the same visual language at a fraction of the dependency weight. Accessibility is not skipped:
 * focus rings, aria attributes and Escape-to-close are all here.
 */
import { AnimatePresence, motion } from 'framer-motion'
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, ChevronDown, Info, X, XCircle } from 'lucide-react'
import { cn } from '../../lib/utils'

const BTN = {
  primary: 'bg-brand text-brand-fg hover:bg-brand-deep shadow-sm',
  secondary: 'bg-surface text-ink border border-line hover:bg-bg',
  ghost: 'text-muted hover:text-ink hover:bg-bg',
  danger: 'bg-danger text-white hover:brightness-95 shadow-sm',
  success: 'bg-success text-white hover:brightness-95 shadow-sm',
  soft: 'bg-brand-soft text-brand hover:bg-brand hover:text-brand-fg',
}
const SIZE = { sm: 'h-8 px-3 text-xs', md: 'h-9 px-4 text-[13px]', lg: 'h-11 px-6 text-sm', icon: 'h-9 w-9' }

export function Button({ variant = 'primary', size = 'md', className, loading, children, ...p }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all',
        'disabled:opacity-50 disabled:pointer-events-none active:scale-[.98]',
        BTN[variant], SIZE[size], className,
      )}
      disabled={loading || p.disabled}
      {...p}
    >
      {loading && <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />}
      {children}
    </button>
  )
}

export const Card = ({ className, hover, ...p }) => (
  <div className={cn('rounded-2xl bg-surface border border-line shadow-card',
    hover && 'transition-all hover:shadow-lift hover:-translate-y-0.5', className)} {...p} />
)
export const CardHeader = ({ className, ...p }) => (
  <div className={cn('px-5 py-4 border-b border-line flex items-center gap-3', className)} {...p} />
)
export const CardTitle = ({ className, ...p }) => (
  <h3 className={cn('text-[13px] font-semibold tracking-tight', className)} {...p} />
)
export const CardBody = ({ className, ...p }) => <div className={cn('p-5', className)} {...p} />

export const Label = ({ className, required, children, hint, ...p }) => (
  <label className={cn('block text-xs font-medium text-muted mb-1.5', className)} {...p}>
    {children}
    {required && <span className="text-danger ml-0.5">*</span>}
    {hint && <span className="ml-1.5 font-normal text-muted/70">{hint}</span>}
  </label>
)

const FIELD =
  'w-full rounded-lg bg-surface border border-line px-3 py-2 text-[13px] text-ink placeholder:text-muted/60 ' +
  'transition-shadow focus:border-brand focus:ring-4 focus:ring-brand/10 outline-none disabled:opacity-60'

export const Input = ({ className, invalid, ...p }) => (
  <input className={cn(FIELD, invalid && 'border-danger ring-4 ring-danger/10', className)} {...p} />
)
export const Textarea = ({ className, invalid, ...p }) => (
  <textarea className={cn(FIELD, 'min-h-[84px] resize-y leading-relaxed',
    invalid && 'border-danger ring-4 ring-danger/10', className)} {...p} />
)
export const Select = ({ className, children, ...p }) => (
  <div className="relative">
    <select className={cn(FIELD, 'appearance-none pr-9 cursor-pointer', className)} {...p}>{children}</select>
    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
  </div>
)

const TONE = {
  default: 'bg-bg text-muted border-line',
  brand: 'bg-brand-soft text-brand border-brand/20',
  success: 'bg-success/10 text-success border-success/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  danger: 'bg-danger/10 text-danger border-danger/20',
  outline: 'bg-transparent text-muted border-line',
}
export const Badge = ({ tone = 'default', className, ...p }) => (
  <span className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10.5px] font-semibold tracking-wide',
    TONE[tone], className)} {...p} />
)

export const Progress = ({ value = 0, className }) => (
  <div className={cn('h-1.5 w-full rounded-full bg-line overflow-hidden', className)}>
    <motion.div className="h-full rounded-full bg-brand" initial={{ width: 0 }}
      animate={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      transition={{ type: 'spring', stiffness: 120, damping: 20 }} />
  </div>
)

export const Skeleton = ({ className }) => (
  <div className={cn('relative overflow-hidden rounded-lg bg-line/60', className)}>
    <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-surface/70 to-transparent" />
  </div>
)

/* Confidence — shown wherever a model asserts something. A number the model itself produced,
   not a marketing metric. */
export function Confidence({ value, size = 'md' }) {
  if (value == null) return <span className="text-muted text-xs">—</span>
  const pct = Math.round(value * 100)
  const tone = pct >= 85 ? 'success' : pct >= 70 ? 'warning' : 'danger'
  const colour = { success: 'bg-success', warning: 'bg-warning', danger: 'bg-danger' }[tone]
  const text = { success: 'text-success', warning: 'text-warning', danger: 'text-danger' }[tone]
  return (
    <div className="flex items-center gap-2" title={`Model confidence: ${pct}%`}>
      <div className={cn('rounded-full bg-line overflow-hidden', size === 'sm' ? 'h-1 w-10' : 'h-1.5 w-16')}>
        <div className={cn('h-full rounded-full', colour)} style={{ width: `${Math.max(0, pct)}%` }} />
      </div>
      <span className={cn('font-mono tabular-nums font-semibold', size === 'sm' ? 'text-[10px]' : 'text-[11px]', text)}>
        {pct}%
      </span>
    </div>
  )
}

export function Dialog({ open, onClose, title, description, children, footer, wide }) {
  const ref = useRef(null)
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    if (open) {
      document.addEventListener('keydown', onKey)
      document.body.style.overflow = 'hidden'
      ref.current?.focus()
    }
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
            className={cn('relative w-full rounded-2xl bg-surface shadow-pop border border-line', wide ? 'max-w-3xl' : 'max-w-lg')}
            initial={{ opacity: 0, scale: 0.97, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 4 }} transition={{ type: 'spring', stiffness: 300, damping: 26 }}>
            <div className="flex items-start gap-3 px-5 py-4 border-b border-line">
              <div className="flex-1">
                <h2 className="text-[15px] font-semibold">{title}</h2>
                {description && <p className="text-xs text-muted mt-0.5">{description}</p>}
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="px-5 py-4 max-h-[65vh] overflow-auto">{children}</div>
            {footer && <div className="px-5 py-3.5 border-t border-line flex justify-end gap-2 bg-bg/50 rounded-b-2xl">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)
const ICON = { success: Check, error: XCircle, info: Info, warning: AlertCircle }
const TTONE = {
  success: 'border-success/30 text-success',
  error: 'border-danger/30 text-danger',
  info: 'border-brand/30 text-brand',
  warning: 'border-warning/30 text-warning',
}

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = (msg, opts = {}) => {
    const id = Math.random().toString(36).slice(2)
    setItems((v) => [...v, { id, msg, tone: opts.tone || 'info', detail: opts.detail }])
    setTimeout(() => setItems((v) => v.filter((t) => t.id !== id)), opts.duration ?? 4200)
  }
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-5 right-5 z-[60] flex flex-col gap-2 w-[360px]" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => {
            const Icon = ICON[t.tone]
            return (
              <motion.div key={t.id}
                className={cn('flex gap-2.5 rounded-xl border px-3.5 py-3 shadow-lift bg-surface', TTONE[t.tone])}
                initial={{ opacity: 0, x: 24, scale: 0.97 }} animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 24, scale: 0.97 }} transition={{ type: 'spring', stiffness: 400, damping: 30 }}>
                <Icon className="h-4 w-4 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <div className="text-[12.5px] font-medium text-ink">{t.msg}</div>
                  {t.detail && <div className="text-[11.5px] text-muted mt-0.5">{t.detail}</div>}
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  )
}

export const Empty = ({ icon: Icon, title, hint, action }) => (
  <div className="flex flex-col items-center justify-center py-14 text-center">
    {Icon && (
      <div className="h-11 w-11 rounded-xl bg-brand-soft grid place-items-center mb-3">
        <Icon className="h-5 w-5 text-brand" />
      </div>
    )}
    <p className="text-[13px] font-medium text-ink">{title}</p>
    {hint && <p className="text-xs text-muted mt-1 max-w-sm">{hint}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
)

export function Tooltip({ label, children, side = 'top' }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-flex" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
      {children}
      <AnimatePresence>
        {open && (
          <motion.span role="tooltip" initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className={cn('absolute z-50 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-[11px] font-medium text-bg shadow-lift',
              side === 'top' && 'bottom-full left-1/2 -translate-x-1/2 mb-1.5',
              side === 'right' && 'left-full top-1/2 -translate-y-1/2 ml-2')}>
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  )
}
