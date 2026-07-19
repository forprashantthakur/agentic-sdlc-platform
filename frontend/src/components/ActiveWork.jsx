import { ArrowRight, Loader2, ShieldCheck, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { cn } from '../lib/utils'

/**
 * Active Work — the continuity bar.
 *
 * The workflow used to live only in one page's React state, so approving from the Outbox (or the
 * standalone /approve page) dropped it and the user had to start again. This polls for any
 * non-terminal run and gives a permanent, one-click way back into it, from anywhere in the app.
 *
 * It is deliberately in the shell, not on a page: continuity you have to navigate to find is not
 * continuity.
 */
export default function ActiveWork() {
  const nav = useNavigate()
  const [runs, setRuns] = useState([])
  const [projects, setProjects] = useState([])

  useEffect(() => {
    const tick = async () => {
      try {
        const [rs, ps] = await Promise.all([
          api.runs(),
          api.projects().catch(() => []),
        ])
        setRuns(rs.filter((r) => !['COMPLETED', 'FAILED', 'REJECTED'].includes(r.status)))
        setProjects(ps)
      } catch { /* transient */ }
    }
    tick()
    const t = setInterval(tick, 6000)
    return () => clearInterval(t)
  }, [])

  const dismiss = async (e, r) => {
    e.stopPropagation()
    await api.abandonRun(r.id).catch(() => {})
    setRuns((rs) => rs.filter((x) => x.id !== r.id))
  }

  const clearAll = async () => {
    await api.abandonStale().catch(() => {})
    setRuns([])
  }

  if (runs.length === 0) return null

  const nameOf = (pid) => projects.find((p) => p.id === pid)?.name || 'Project'

  const resume = (r) => {
    const isFlow2 = (r.thread_id || '').startsWith('f2-')
    // Land where the work actually is: Flow-2 runs on Sprint Delivery, Flow-1 runs on the
    // AI-Analysis step of the wizard (which auto-attaches to the project's latest run).
    nav(isFlow2 ? '/sprint-delivery'
      : '/new', isFlow2 ? undefined : { state: { step: 'analysis', completed: ['context', 'ingestion', 'discovery'] } })
  }

  return (
    <div className="border-b border-line bg-brand-soft/60 px-6 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10.5px] font-bold uppercase tracking-wide text-brand">In progress</span>
        {runs.slice(0, 3).map((r) => {
          const isFlow2 = (r.thread_id || '').startsWith('f2-')
          const waiting = r.status === 'WAITING_APPROVAL'
          return (
            <button
              key={r.id}
              onClick={() => resume(r)}
              className={cn('group flex items-center gap-2 rounded-lg border px-2.5 py-1 text-[11.5px] transition-colors',
                waiting ? 'border-warning/40 bg-warning/10 hover:bg-warning/20'
                        : 'border-brand/25 bg-surface hover:border-brand')}
            >
              {waiting
                ? <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-warning" />
                : <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-brand" />}
              <span className="font-semibold text-ink">{nameOf(r.project_id)}</span>
              <span className="text-muted">
                {isFlow2 ? 'Sprint Delivery' : 'BRD'} · {waiting ? 'awaiting approval' : r.status.toLowerCase()}
              </span>
              <ArrowRight className="h-3.5 w-3.5 text-brand opacity-0 transition-opacity group-hover:opacity-100" />
              <span
                role="button"
                title="Abandon this run"
                onClick={(e) => dismiss(e, r)}
                className="rounded p-0.5 text-muted hover:bg-danger/10 hover:text-danger"
              >
                <X className="h-3 w-3" />
              </span>
            </button>
          )
        })}
        {runs.length > 3 && (
          <span className="text-[11px] text-muted">+{runs.length - 3} more</span>
        )}
        {runs.length > 1 && (
          <button onClick={clearAll}
            className="ml-auto text-[11px] font-semibold text-muted underline hover:text-danger">
            Clear all ({runs.length})
          </button>
        )}
      </div>
    </div>
  )
}
