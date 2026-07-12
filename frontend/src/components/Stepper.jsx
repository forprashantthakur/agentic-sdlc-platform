import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import { cn } from '../lib/utils'

export const STEPS = [
  { id: 'context', label: 'Business Context', hint: 'Sponsor, objectives, KPIs' },
  { id: 'ingestion', label: 'Knowledge Ingestion', hint: 'Documents & connectors' },
  { id: 'discovery', label: 'Requirement Discovery', hint: 'Clarify with the copilot' },
  { id: 'analysis', label: 'AI Analysis', hint: 'Six agents, two gates' },
  { id: 'review', label: 'Review', hint: 'Approve, reject, modify' },
  { id: 'generate', label: 'Generate BRD', hint: 'Export & publish' },
]

export default function Stepper({ current, completed = [], onSelect }) {
  const idx = STEPS.findIndex((s) => s.id === current)
  return (
    <nav aria-label="Progress" className="mb-6">
      <ol className="flex items-start">
        {STEPS.map((s, i) => {
          const done = completed.includes(s.id) || i < idx
          const active = s.id === current
          const reachable = done || active || i <= idx
          return (
            <li key={s.id} className={cn('flex-1 flex flex-col', i < STEPS.length - 1 && 'pr-1')}>
              <div className="flex items-center w-full">
                <button onClick={() => reachable && onSelect?.(s.id)} disabled={!reachable}
                  aria-current={active ? 'step' : undefined}
                  className={cn(
                    'relative grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 text-[11px] font-semibold transition-all',
                    done && 'border-success bg-success text-white',
                    active && !done && 'border-brand bg-brand text-brand-fg shadow-[0_0_0_4px] shadow-brand/15',
                    !done && !active && 'border-line bg-surface text-muted',
                    reachable && 'cursor-pointer hover:scale-105',
                  )}>
                  {done ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : i + 1}
                </button>
                {i < STEPS.length - 1 && (
                  <div className="relative mx-1.5 h-[2px] flex-1 rounded-full bg-line overflow-hidden">
                    <motion.div className="absolute inset-y-0 left-0 bg-success rounded-full"
                      initial={false} animate={{ width: done ? '100%' : '0%' }} transition={{ duration: 0.4 }} />
                  </div>
                )}
              </div>
              <div className="mt-2 pr-3">
                <p className={cn('text-[11.5px] font-semibold leading-tight',
                  active ? 'text-brand' : done ? 'text-ink' : 'text-muted')}>{s.label}</p>
                <p className="text-[10.5px] text-muted leading-tight mt-0.5 hidden lg:block">{s.hint}</p>
              </div>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
