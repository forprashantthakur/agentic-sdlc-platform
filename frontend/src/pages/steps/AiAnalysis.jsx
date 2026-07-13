import { motion } from 'framer-motion'
import { Bot, CheckCircle2, CircleDot, Loader2, Play, ShieldQuestion, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { cn, fmtDateTime } from '../../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Empty, Input, Label, Progress, useToast } from '../../components/ui'

/* Node ids match backend/app/graph/builder.py exactly. If they drift, the UI lights up the wrong
   step — so they stay literal rather than prettified. */
const PIPELINE = [
  { node: 'ingest', label: 'Ingest & Index', sub: 'Sources → long-term memory (RAG)' },
  { node: 'agent1_requirements', label: 'Agent 1 · Requirement Gathering', sub: 'Extract, cite, flag conflicts and gaps' },
  { node: 'agent2_concept_note', label: 'Agent 2 · Concept Note', sub: 'Objectives, scope, business rules, risks' },
  { node: 'request_concept_approval', label: 'Gate 1 · Human Approval', sub: 'Agent 5 — the run suspends here', gate: true },
  { node: 'agent3_wireframe', label: 'Agent 3 · Wireframes', sub: 'Screen spec → Stitch via MCP' },
  { node: 'agent4_requirement_docs', label: 'Agent 4 · Requirement Documents', sub: 'BRD · FRD · SRS · Stories · APIs · NFRs' },
  { node: 'request_docs_approval', label: 'Gate 2 · Human Approval', sub: 'Agent 5 — the run suspends here', gate: true },
  { node: 'agent6_sprint', label: 'Agent 6 · Sprint Plan', sub: 'Epics, stories, points → Jira' },
  { node: 'finalise', label: 'Finalise', sub: 'Seal the audit trail' },
]

export default function AiAnalysis({ project, run, setRun, onNext, onBack }) {
  const toast = useToast()
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState(run?.status || null)
  const [approvers, setApprovers] = useState('compliance@hdfcbank.com')
  const [velocity, setVelocity] = useState(15)
  const [starting, setStarting] = useState(false)
  const close = useRef(null)

  useEffect(() => {
    if (!project) return
    api.runs(project.id).then((rs) => rs[0] && attach(rs[0])).catch(() => {})
    return () => close.current?.()
  }, [project?.id])

  const attach = async (r) => {
    setRun(r)
    setStatus(r.status)
    setEvents(await api.events(r.id))
    close.current?.()
    close.current = api.stream(r.id, (e) => {
      if (e.terminal) { setStatus(e.status); return }
      setEvents((prev) => (prev.some((p) => p.id === e.id) ? prev : [...prev, e]))
      setStatus(e.status)
    })
  }

  const start = async () => {
    setStarting(true)
    try {
      const r = await api.startRun({
        project_id: project.id,
        approvers: approvers.split(',').map((s) => s.trim()).filter(Boolean),
        velocity: Number(velocity),
        base_url: window.location.origin,
      })
      setEvents([])
      attach(r)
      toast('Agents dispatched', { tone: 'success', detail: 'The run will suspend at Gate 1 for your sign-off.' })
    } catch (e) {
      toast('Could not start the run', { tone: 'error', detail: e.message })
    } finally {
      setStarting(false)
    }
  }

  const seen = new Set(events.map((e) => e.node))
  const last = events.length ? events[events.length - 1].node : null
  const stateOf = (node) => {
    if (!seen.has(node)) return 'idle'
    if (node === last && status === 'WAITING_APPROVAL') return 'wait'
    if (node === last && status === 'RUNNING') return 'run'
    if (node === last && status === 'FAILED') return 'fail'
    return 'done'
  }
  const pct = Math.round((PIPELINE.filter((p) => seen.has(p.node)).length / PIPELINE.length) * 100)

  if (!project) return <Empty icon={Bot} title="No project selected" />

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">AI Analysis</h1>
          <p className="text-[13px] text-muted mt-1">
            Six agents in a stateful graph. The run <strong>suspends</strong> at each approval gate and
            resumes only when a human decides — even days later, across a redeploy.
          </p>
        </div>
        {status && (
          <Badge tone={status === 'COMPLETED' ? 'success'
            : status === 'FAILED' || status === 'REJECTED' ? 'danger'
            : status === 'WAITING_APPROVAL' ? 'warning' : 'brand'}>
            {status.replaceAll('_', ' ')}
          </Badge>
        )}
      </div>

      {!run && (
        <Card>
          <CardHeader><Play className="h-4 w-4 text-brand" /><CardTitle>Dispatch the agents</CardTitle></CardHeader>
          <CardBody className="grid gap-4 md:grid-cols-3 items-end">
            <div className="md:col-span-2">
              <Label hint="Every approver on a gate must approve for it to pass">Approvers</Label>
              <Input value={approvers} onChange={(e) => setApprovers(e.target.value)} />
            </div>
            <div>
              <Label hint="Points per sprint">Team velocity</Label>
              <Input type="number" value={velocity} onChange={(e) => setVelocity(e.target.value)} />
            </div>
            <div className="md:col-span-3">
              <Button onClick={start} loading={starting} size="lg">
                <Play className="h-4 w-4" /> Start agentic run
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {run && (
        <>
          <Card>
            <CardBody className="pb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[12px] font-medium text-muted">Pipeline progress</span>
                <span className="font-mono text-[12px] font-semibold tabular-nums">{pct}%</span>
              </div>
              <Progress value={pct} />
            </CardBody>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader><Bot className="h-4 w-4 text-brand" /><CardTitle>Agent pipeline</CardTitle></CardHeader>
              <CardBody className="space-y-1">
                {PIPELINE.map((p) => {
                  const st = stateOf(p.node)
                  const Icon = { done: CheckCircle2, run: Loader2, wait: ShieldQuestion, fail: XCircle, idle: CircleDot }[st]
                  return (
                    <div key={p.node} className={cn('flex items-start gap-3 rounded-lg px-2.5 py-2 transition-colors',
                      st === 'run' && 'bg-brand-soft', st === 'wait' && 'bg-warning/5')}>
                      <Icon className={cn('h-4 w-4 shrink-0 mt-0.5',
                        st === 'done' && 'text-success', st === 'run' && 'text-brand animate-spin',
                        st === 'wait' && 'text-warning', st === 'fail' && 'text-danger', st === 'idle' && 'text-line')} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className={cn('text-[12.5px] font-medium', st === 'idle' && 'text-muted')}>{p.label}</span>
                          {p.gate && <Badge tone="warning">HITL</Badge>}
                        </div>
                        <p className="text-[11px] text-muted leading-snug">{p.sub}</p>
                      </div>
                    </div>
                  )
                })}
              </CardBody>
            </Card>

            <Card>
              <CardHeader><CardTitle>Live timeline</CardTitle>
                <span className="ml-auto text-[11px] text-muted">{events.length} events</span>
              </CardHeader>
              <CardBody className="max-h-[520px] overflow-y-auto space-y-2.5">
                {events.length === 0 && <p className="text-[12px] text-muted">Waiting for the first event…</p>}
                {events.map((e) => (
                  <motion.div key={e.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
                    className="border-b border-line pb-2.5 last:border-0">
                    <div className="flex items-center gap-2">
                      <code className={cn('font-mono text-[10.5px] font-semibold',
                        e.level === 'error' ? 'text-danger' : 'text-brand')}>{e.node}</code>
                      <span className="text-[10px] text-muted ml-auto">{fmtDateTime(e.created_at)}</span>
                    </div>
                    <p className="text-[12px] mt-0.5 leading-snug">{e.message}</p>
                  </motion.div>
                ))}
              </CardBody>
            </Card>
          </div>

          {status === 'WAITING_APPROVAL' && (
            <Card className="border-warning/40 bg-warning/5">
              <CardBody className="flex items-center gap-4">
                <ShieldQuestion className="h-5 w-5 text-warning shrink-0" />
                <div className="flex-1">
                  <p className="text-[13px] font-semibold text-warning">Awaiting human sign-off</p>
                  <p className="text-[12px] text-muted mt-0.5">
                    The run is suspended at an approval gate — safely checkpointed — until a decision is recorded.
                  </p>
                </div>
                <Button onClick={onNext}>Go to Review →</Button>
              </CardBody>
            </Card>
          )}
        </>
      )}

      <div className="flex gap-3 pb-2">
        <Button variant="secondary" onClick={onBack}>← Back</Button>
        {run && <Button variant="secondary" onClick={onNext}>Review →</Button>}
      </div>
    </div>
  )
}
