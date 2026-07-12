import { motion } from 'framer-motion'
import { AlertTriangle, ArrowUp, BadgeCheck, Bot, HelpCircle, Lightbulb, Quote, Sparkles, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { cn } from '../lib/utils'
import { Badge, Confidence, Skeleton } from './ui'

const TABS = [
  { id: 'chat', label: 'Chat', icon: Bot },
  { id: 'insights', label: 'Insights', icon: Lightbulb },
  { id: 'questions', label: 'Questions', icon: HelpCircle },
]

const SUGGESTED = [
  'What are the regulatory constraints on this capability?',
  'Which requirements are least supported by evidence?',
  'What is explicitly out of scope?',
  'Summarise the sources I have uploaded.',
  'What is still missing before we can write the BRD?',
]

const RECOMMENDED = [
  { q: 'Who are the primary users of this capability?', why: 'Requirements without a named actor are untestable.' },
  { q: 'What pain points exist in the current journey?', why: 'Grounds the Problem Statement in the BRD.' },
  { q: 'Which upstream and downstream systems are impacted?', why: 'Drives the integration requirements section.' },
  { q: 'Are there approval workflows or maker-checker steps?', why: 'Banking controls are rarely stated but always assumed.' },
  { q: 'Which regulations apply — RBI, FEMA, PCI-DSS, DPDP?', why: 'Compliance requirements must trace to a circular.' },
  { q: 'What are the success metrics and their baselines?', why: 'An objective without a baseline cannot be measured.' },
  { q: 'What happens on the unhappy paths and error states?', why: 'The most common source of post-UAT rework.' },
  { q: 'What is the data retention and residency requirement?', why: 'RBI data localisation applies to customer data.' },
]

export default function Copilot({ project }) {
  const [tab, setTab] = useState('chat')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [insights, setInsights] = useState(null)
  const endRef = useRef(null)

  useEffect(() => { setMessages([]); setInsights(null) }, [project?.id])

  useEffect(() => {
    if (!project) return
    api.copilotInsights(project.id).then(setInsights).catch(() => setInsights(null))
  }, [project?.id, tab])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy])

  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || !project || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const data = await api.copilotChat({ project_id: project.id, message: q })
      setMessages((m) => [...m, { role: 'ai', text: data.answer, citations: data.citations }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'ai', text: `Could not reach the copilot: ${e.message}`, error: true }])
    } finally { setBusy(false) }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 px-4 py-3.5 border-b border-line">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-brand to-brand-deep grid place-items-center">
            <Sparkles className="h-3.5 w-3.5 text-brand-fg" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold leading-tight">AI Copilot</div>
            <div className="text-[10.5px] text-muted leading-tight truncate">
              {project ? `Grounded in ${project.name}` : 'Select a project to ground answers'}
            </div>
          </div>
        </div>
        <div className="mt-3 flex gap-1 rounded-lg bg-bg p-1">
          {TABS.map((t) => {
            const Icon = t.icon
            return (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={cn('flex-1 flex items-center justify-center gap-1.5 rounded-md py-1.5 text-[11.5px] font-medium transition-colors',
                  tab === t.id ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink')}>
                <Icon className="h-3.5 w-3.5" />{t.label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {tab === 'chat' && (
          <>
            {messages.length === 0 && (
              <div className="space-y-4">
                <div className="rounded-xl border border-brand/20 bg-brand-soft p-3.5">
                  <p className="text-[12px] text-brand leading-relaxed">
                    I answer <strong>only</strong> from this project's evidence — its sources, extracted
                    requirements, approved artifacts and reviewer comments. If the evidence doesn't
                    support an answer, I say so rather than invent one.
                  </p>
                </div>
                <div>
                  <p className="text-[10.5px] font-semibold uppercase tracking-wider text-muted mb-2">Suggested</p>
                  <div className="space-y-1.5">
                    {SUGGESTED.map((s) => (
                      <button key={s} onClick={() => send(s)} disabled={!project}
                        className="w-full text-left rounded-lg border border-line bg-surface px-3 py-2 text-[12px] text-ink hover:border-brand hover:bg-brand-soft transition-colors disabled:opacity-50">
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-3">
              {messages.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
                  {m.role === 'user' ? (
                    <div className="ml-6 rounded-xl rounded-br-sm bg-brand px-3.5 py-2.5 text-[12.5px] text-brand-fg">{m.text}</div>
                  ) : (
                    <div className="space-y-2">
                      <div className={cn('mr-4 rounded-xl rounded-bl-sm border px-3.5 py-2.5 text-[12.5px] leading-relaxed whitespace-pre-wrap',
                        m.error ? 'border-danger/30 bg-danger/5 text-danger' : 'border-line bg-bg text-ink')}>
                        {m.text.split('**').map((part, j) => (j % 2 ? <strong key={j}>{part}</strong> : <span key={j}>{part}</span>))}
                      </div>
                      {m.citations?.length > 0 && (
                        <div className="mr-4 space-y-1">
                          <p className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
                            <Quote className="h-3 w-3" /> Citations · traceable to source
                          </p>
                          {m.citations.slice(0, 3).map((c) => (
                            <div key={c.n} className="rounded-lg border border-line bg-surface px-2.5 py-1.5">
                              <div className="flex items-center gap-1.5 mb-0.5">
                                <Badge tone="brand">[{c.n}] {c.namespace}</Badge>
                                <Confidence value={c.score} size="sm" />
                              </div>
                              <p className="text-[11px] text-muted line-clamp-2 leading-snug">{c.excerpt}…</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </motion.div>
              ))}
              {busy && (
                <div className="mr-4 flex items-center gap-1.5 rounded-xl rounded-bl-sm border border-line bg-bg px-3.5 py-3">
                  {[0, 1, 2].map((i) => (
                    <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-brand"
                      animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
                      transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }} />
                  ))}
                  <span className="ml-1.5 text-[11px] text-muted">Retrieving from project memory…</span>
                </div>
              )}
              <div ref={endRef} />
            </div>
          </>
        )}

        {tab === 'insights' && <Insights insights={insights} project={project} />}

        {tab === 'questions' && (
          <div className="space-y-2">
            <p className="text-[11.5px] text-muted leading-relaxed mb-3">
              Questions to resolve with the business before the BRD is signed off.
            </p>
            {RECOMMENDED.map((r) => (
              <div key={r.q} className="rounded-xl border border-line bg-surface p-3 hover:border-brand transition-colors">
                <p className="text-[12.5px] font-medium leading-snug">{r.q}</p>
                <p className="text-[11px] text-muted mt-1 leading-snug">{r.why}</p>
                <button onClick={() => { setTab('chat'); send(r.q) }} disabled={!project}
                  className="mt-2 text-[11px] font-semibold text-brand hover:underline disabled:opacity-50">
                  Ask the copilot →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {tab === 'chat' && (
        <div className="shrink-0 border-t border-line p-3">
          <div className="relative">
            <textarea rows={1} value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder={project ? 'Ask about this project…' : 'Select a project first'}
              disabled={!project}
              className="w-full resize-none rounded-xl border border-line bg-bg py-2.5 pl-3.5 pr-10 text-[12.5px] placeholder:text-muted/70 focus:border-brand focus:ring-4 focus:ring-brand/10 outline-none transition-shadow disabled:opacity-60" />
            <button onClick={() => send()} disabled={!input.trim() || !project || busy}
              className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 grid place-items-center rounded-lg bg-brand text-brand-fg disabled:opacity-30">
              <ArrowUp className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="mt-1.5 text-[10px] text-muted text-center">
            Answers are grounded in project memory and cited. Verify before use.
          </p>
        </div>
      )}
    </div>
  )
}

function Insights({ insights, project }) {
  if (!project) return <p className="text-[12px] text-muted">Select a project to see insights.</p>
  if (!insights) return <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
  if (insights.state === 'NO_ANALYSIS') {
    return (
      <div className="rounded-xl border border-line bg-bg p-4 text-center">
        <Bot className="h-5 w-5 text-muted mx-auto mb-2" />
        <p className="text-[12px] text-muted">{insights.message}</p>
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-line bg-surface p-3.5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">Extraction confidence</span>
          <Confidence value={insights.mean_confidence} />
        </div>
        <p className="text-[11.5px] text-muted leading-snug">
          Mean confidence across {insights.requirement_count} extracted requirements. Anything below
          80% is flagged here and should be confirmed with the business.
        </p>
      </div>

      {insights.conflicts?.length > 0 && (
        <Section icon={TriangleAlert} tone="danger" title={`Conflicts (${insights.conflicts.length})`}
          hint="Two sources disagree. The agent refused to pick one — a human must.">
          {insights.conflicts.map((c, i) => (
            <div key={i} className="rounded-lg border border-danger/20 bg-danger/5 p-2.5">
              <p className="text-[11.5px] text-ink leading-snug">{c.description}</p>
              <div className="flex flex-wrap gap-1 mt-1.5">
                {(c.requirement_ids || []).map((id) => <Badge key={id} tone="danger">{id}</Badge>)}
                {c.resolution_needed_from && <Badge tone="outline">Owner: {c.resolution_needed_from}</Badge>}
              </div>
            </div>
          ))}
        </Section>
      )}

      {insights.gaps?.length > 0 && (
        <Section icon={AlertTriangle} tone="warning" title={`Missing information (${insights.gaps.length})`}
          hint="Absent from the evidence. Flagged rather than invented.">
          {insights.gaps.map((g, i) => (
            <div key={i} className="rounded-lg border border-warning/20 bg-warning/5 p-2.5">
              <p className="text-[11.5px] text-ink leading-snug">{g}</p>
            </div>
          ))}
        </Section>
      )}

      {insights.low_confidence?.length > 0 && (
        <Section icon={AlertTriangle} tone="warning" title={`Low-confidence requirements (${insights.low_confidence.length})`}
          hint="Evidence is thin or ambiguous. Confirm before sign-off.">
          {insights.low_confidence.map((r) => (
            <div key={r.id} className="rounded-lg border border-line bg-bg p-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11.5px] font-medium">{r.id} · {r.title}</span>
                <Confidence value={r.confidence} size="sm" />
              </div>
              {r.open_question && <p className="text-[11px] text-muted mt-1 leading-snug">{r.open_question}</p>}
            </div>
          ))}
        </Section>
      )}

      {insights.stakeholders?.length > 0 && (
        <Section icon={BadgeCheck} tone="brand" title="Stakeholders identified">
          {insights.stakeholders.map((s, i) => (
            <div key={i} className="rounded-lg border border-line bg-bg px-2.5 py-2">
              <p className="text-[11.5px] font-medium truncate">{s.name}</p>
              <p className="text-[10.5px] text-muted truncate">{s.role}</p>
            </div>
          ))}
        </Section>
      )}
    </div>
  )
}

const Section = ({ icon: Icon, tone, title, hint, children }) => (
  <div>
    <div className="flex items-center gap-1.5 mb-1.5">
      <Icon className={cn('h-3.5 w-3.5', tone === 'danger' ? 'text-danger' : tone === 'warning' ? 'text-warning' : 'text-brand')} />
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">{title}</span>
    </div>
    {hint && <p className="text-[11px] text-muted mb-2 leading-snug">{hint}</p>}
    <div className="space-y-1.5">{children}</div>
  </div>
)
