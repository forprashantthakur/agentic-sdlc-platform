import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Inbox, Mail, Send, Sparkles, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Empty, Input, Label, Textarea, useToast } from '../components/ui'
import { cn } from '../lib/utils'

const SAMPLE = {
  from: 'treasury.head@hdfcbank.com',
  subject: 'New requirement — Corporate FX self-service booking portal',
  body: `Hi team,

We need a self-service portal so our corporate treasury clients can book FX forward contracts without calling the dealing desk.

Every trade must carry an FEMA purpose code before it can settle.
Any single deal above USD 10 million should escalate to Market Risk before booking.
The system must retrieve any trade for 10 years for audit.
Live rate quotes should reach the treasurer within 2 seconds.
Customers must be able to see all their booked deals in one blotter.

Regards,
Head of Treasury`,
}

/**
 * Email intake — the "write a mail and it flows into the agent" feature.
 *
 * Left: compose an email exactly as a business user would. Right: the intake queue of drafts the
 * system has received (from this form OR a real forwarded email hitting the same endpoint), each
 * showing what the Requirement Gathering agent detected. A human accepts before the pipeline runs —
 * an inbound email is untrusted, so it earns a review step, not a straight line to a spend.
 */
export default function Intake({ setProject, setRun }) {
  const nav = useNavigate()
  const toast = useToast()
  const [form, setForm] = useState({ from: '', subject: '', body: '' })
  const [sending, setSending] = useState(false)
  const [queue, setQueue] = useState([])
  const [approvers, setApprovers] = useState('cio@hdfcbank.com')
  const [busy, setBusy] = useState('')

  const load = useCallback(() => { api.intakeQueue().then(setQueue).catch(() => {}) }, [])
  useEffect(() => { load() }, [load])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const send = async () => {
    if (!form.from.trim() || !form.body.trim()) {
      toast('A From address and a body are required', { tone: 'warning' })
      return
    }
    setSending(true)
    try {
      const d = await api.intakeSend(form)
      toast('Email received into the pipeline', {
        detail: `Detected ${d.preview?.candidate_count ?? 0} candidate requirements — now in the intake queue for review.`,
        tone: 'success',
      })
      setForm({ from: '', subject: '', body: '' })
      load()
    } catch (e) {
      toast('Could not accept the email', { detail: e.message, tone: 'error' })
    } finally {
      setSending(false)
    }
  }

  const accept = async (d) => {
    setBusy(d.id)
    try {
      const list = approvers.split(',').map((s) => s.trim()).filter(Boolean)
      const r = await api.intakeAccept(d.id, { approvers: list, base_url: window.location.origin })
      // Hand the just-started run to the app so the live 6-agent view can attach to it, then land
      // on the same AI-Analysis step the in-app flow shows — email and in-app converge here.
      const proj = await api.project(d.id).catch(() => ({ id: d.id, name: d.name }))
      setProject?.(proj)
      setRun?.({ id: r.run_id, status: 'RUNNING' })
      toast(`Pipeline started for "${d.name}"`, { detail: 'Watch the agents run — it will pause at Gate 1 for sign-off.', tone: 'success' })
      load()
      nav('/new', { state: { step: 'analysis', completed: ['context', 'ingestion', 'discovery'] } })
      return r
    } catch (e) {
      toast('Could not start the pipeline', { detail: e.message, tone: 'error' })
    } finally {
      setBusy('')
    }
  }

  const discard = async (d) => {
    setBusy(d.id)
    try {
      await api.intakeDiscard(d.id)
      load()
    } catch (e) {
      toast('Could not discard', { detail: e.message, tone: 'error' })
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Email Intake</h1>
        <p className="text-[13px] text-muted mt-1">
          Write a requirements email — or forward a real one to the intake address — and it flows
          straight into the Requirement Gathering agent. Drafts land in the queue on the right for a
          quick human review before the pipeline runs.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.05fr_1fr]">
        {/* ── compose ── */}
        <Card>
          <CardHeader>
            <Mail className="h-4 w-4 text-brand" />
            <CardTitle>Compose a requirements email</CardTitle>
            <button
              onClick={() => setForm(SAMPLE)}
              className="ml-auto text-[11.5px] font-semibold text-brand hover:underline"
            >
              <Sparkles className="mr-1 inline h-3.5 w-3.5" />Use a sample
            </button>
          </CardHeader>
          <CardBody className="space-y-3">
            <div>
              <Label>From</Label>
              <Input type="email" placeholder="requester@hdfcbank.com" value={form.from} onChange={set('from')} />
            </div>
            <div>
              <Label>Subject</Label>
              <Input placeholder="New requirement — …" value={form.subject} onChange={set('subject')} />
            </div>
            <div>
              <Label>Requirements (email body)</Label>
              <Textarea
                className="min-h-[240px] font-mono text-[12.5px]"
                placeholder="Describe what you need. Sentences with 'must', 'should', 'within N seconds' and the like are picked up as candidate requirements."
                value={form.body}
                onChange={set('body')}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-muted">
                Goes to <code className="font-mono">POST /api/intake/email</code> — the same endpoint a real inbound webhook uses.
              </span>
              <Button onClick={send} loading={sending}>
                <Send className="mr-1.5 h-4 w-4" />Send into pipeline
              </Button>
            </div>
          </CardBody>
        </Card>

        {/* ── queue ── */}
        <Card>
          <CardHeader>
            <Inbox className="h-4 w-4 text-brand" />
            <CardTitle>Intake queue</CardTitle>
            <Badge tone="brand" className="ml-auto">{queue.length}</Badge>
          </CardHeader>
          <CardBody>
            <div className="mb-3">
              <Label>Approvers for accepted requests (comma-separated)</Label>
              <Input value={approvers} onChange={(e) => setApprovers(e.target.value)} placeholder="cio@hdfcbank.com, cto@hdfcbank.com" />
            </div>
            {queue.length === 0 ? (
              <Empty icon={Inbox} title="No emails waiting" hint="Send one from the left, or forward a requirements email to the intake address." />
            ) : (
              <div className="space-y-3">
                <AnimatePresence>
                  {queue.map((d) => (
                    <motion.div
                      key={d.id}
                      layout
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, height: 0 }}
                      className="rounded-xl border border-line bg-bg/40 p-3.5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-[13px] font-semibold leading-snug">{d.name}</p>
                          <p className="mt-0.5 text-[11px] text-muted">
                            from {d.from} · {d.preview?.word_count ?? 0} words
                          </p>
                        </div>
                        <Badge tone={d.preview?.candidate_count ? 'success' : 'warning'}>
                          {d.preview?.candidate_count ?? 0} detected
                        </Badge>
                      </div>

                      {d.preview?.candidate_requirements?.length > 0 && (
                        <ul className="mt-2.5 space-y-1">
                          {d.preview.candidate_requirements.slice(0, 4).map((r, i) => (
                            <li key={i} className="flex gap-1.5 text-[11.5px] leading-snug text-ink">
                              <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-brand" />
                              <span className="line-clamp-2">{r}</span>
                            </li>
                          ))}
                          {d.preview.candidate_count > 4 && (
                            <li className="pl-4 text-[11px] text-muted">+{d.preview.candidate_count - 4} more — the agent extracts the full set on accept</li>
                          )}
                        </ul>
                      )}

                      <div className="mt-3 flex items-center gap-2">
                        <Button size="sm" onClick={() => accept(d)} loading={busy === d.id}>
                          Accept & run pipeline
                        </Button>
                        <button
                          onClick={() => discard(d)}
                          disabled={busy === d.id}
                          className="rounded-lg p-1.5 text-muted hover:bg-danger/10 hover:text-danger transition-colors"
                          title="Discard draft"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
