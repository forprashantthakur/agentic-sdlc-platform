import { CheckCircle2, CircleDashed, GitBranch, Loader2, Rocket, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Empty, Input, Label, useToast } from '../components/ui'
import { cn } from '../lib/utils'

// The Flow-2 pipeline, in order — what the timeline maps events onto.
const STAGES = [
  { node: 'agent7_backlog', label: 'Agent 7 · Backlog Refinement', sub: 'Stories, AC, estimates → Jira + Confluence' },
  { node: 'request_btg_gate', label: 'Gate · BTG Approval', sub: 'Stories & estimates sign-off', gate: true },
  { node: 'agent8_grooming', label: 'Agent 8 · Sprint Planning & Grooming', sub: 'Sprint composition' },
  { node: 'agent9_dev', label: 'Agent 9 · Development Assist', sub: 'Story context + code-review checklist' },
  { node: 'request_review_gate', label: 'Gate · Code Review', sub: 'Technical-Lead approval', gate: true },
  { node: 'agent10_qe', label: 'Agent 10 · Test Generation & QE', sub: 'Tests from AC · bug rework loop' },
  { node: 'request_completion_gate', label: 'Gate · PO & BTG Sign-off', sub: 'Completion approval', gate: true },
  { node: 'agent11_release', label: 'Agent 11 · Release & DevOps Hand-off', sub: 'Story → Done · production hand-off' },
]

/**
 * Sprint Delivery — Process Flow 2.
 *
 * Start delivery on a project whose Flow-1 pack is approved, then watch the five delivery agents run
 * through their gates and the bug rework loop. Approvals arrive by email exactly as Flow 1 — decide
 * them in the Review Center or the Approval Outbox; this page just shows the pipeline advancing.
 */
export default function SprintDelivery() {
  const nav = useNavigate()
  const toast = useToast()
  const [projects, setProjects] = useState([])
  const [approvers, setApprovers] = useState('po@hdfcbank.com, btg@hdfcbank.com')
  const [busy, setBusy] = useState('')
  const [run, setRun] = useState(null)
  const [events, setEvents] = useState([])
  const [pending, setPending] = useState([])
  const [deciding, setDeciding] = useState('')

  const loadProjects = useCallback(() => { api.projects().then(setProjects).catch(() => {}) }, [])
  useEffect(() => { loadProjects() }, [loadProjects])

  // On mount, reconnect to an in-progress Flow-2 run. Leaving this page to approve used to unmount
  // it and lose the run, which read as "the pipeline never advanced" when in fact it had.
  useEffect(() => {
    (async () => {
      try {
        const runs = await api.runs()
        const f2 = runs.filter((r) => (r.thread_id || '').startsWith('f2-')
          && !['COMPLETED', 'FAILED', 'REJECTED'].includes(r.status))
        if (f2[0]) {
          const projs = await api.projects().catch(() => [])
          const pr = projs.find((x) => x.id === f2[0].project_id)
          setRun({ id: f2[0].id, project_id: f2[0].project_id,
                   project_name: pr?.name || 'Project', status: f2[0].status })
        }
      } catch { /* nothing in progress */ }
    })()
  }, [])

  // Poll the SPECIFIC run by id — not "the newest f2 run", which drifts to another attempt when
  // several exist. Also load this run's pending gate so it can be decided in place.
  useEffect(() => {
    if (!run?.id) return undefined
    const tick = async () => {
      try {
        const j = await api.get(`/api/runs/${run.id}`)
        setRun((prev) => ({ ...prev, status: j.status }))
        setEvents(await api.events(run.id))
        if (j.status === 'WAITING_APPROVAL') {
          const aps = await api.approvals(run.project_id)
          setPending(aps.filter((a) => a.status === 'PENDING' && a.run_id === run.id))
        } else {
          setPending([])
        }
      } catch { /* transient */ }
    }
    tick()
    const t = setInterval(tick, 2500)
    return () => clearInterval(t)
  }, [run?.id, run?.project_id])

  const decide = async (approval, decision) => {
    setDeciding(approval.id)
    try {
      await api.decide(approval.id, { decision, comments: [] })
      setPending((ps) => ps.filter((a) => a.id !== approval.id))
      toast(decision === 'APPROVED' ? 'Approved — pipeline resuming' : 'Changes requested',
            { tone: decision === 'APPROVED' ? 'success' : 'warning' })
    } catch (e) {
      toast('Could not record the decision', { detail: e.message, tone: 'error' })
    } finally {
      setDeciding('')
    }
  }

  const start = async (p) => {
    setBusy(p.id)
    try {
      const list = approvers.split(',').map((s) => s.trim()).filter(Boolean)
      const r = await api.startFlow2({ project_id: p.id, approvers: list, base_url: window.location.origin })
      setRun({ id: r.id, project_id: p.id, project_name: p.name, status: r.status })
      setEvents([])
      toast('Sprint delivery started', { detail: `Flow 2 is running for "${p.name}". Approvals will arrive by email.`, tone: 'success' })
    } catch (e) {
      toast('Could not start sprint delivery', {
        detail: e.message.includes('user stories')
          ? 'This project has no approved requirement pack yet — run Flow 1 (New BRD) to completion first.'
          : e.message,
        tone: 'error',
      })
    } finally {
      setBusy('')
    }
  }

  const stageState = (node) => {
    const nodes = events.map((e) => e.node)
    const idx = nodes.lastIndexOf(node)
    if (idx === -1) return 'pending'
    const finished = events.some((e) => e.node === node && /finished/.test(e.message))
    if (run?.status === 'WAITING_APPROVAL' && node === nodes[nodes.length - 1]) return 'wait'
    return finished ? 'done' : 'active'
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Sprint Delivery <span className="text-muted font-normal">· Process Flow 2</span></h1>
        <p className="mt-1 text-[13px] text-muted">
          Take an approved requirement pack through sprint planning, development and testing to a
          governed DevOps hand-off. Five agents, three gates, and the bug rework loop — approvals
          arrive by email, decided in the Review Center or Approval Outbox.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        {/* start */}
        <Card>
          <CardHeader>
            <Rocket className="h-4 w-4 text-brand" />
            <CardTitle>Start sprint delivery</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <div>
              <Label>Approvers (BTG · Tech Lead · PO — comma-separated)</Label>
              <Input value={approvers} onChange={(e) => setApprovers(e.target.value)} />
            </div>
            <div className="space-y-2">
              {projects.length === 0 ? (
                <Empty icon={GitBranch} title="No projects" hint="Complete a BRD in New BRD first, then start delivery here." />
              ) : projects.map((p) => (
                <div key={p.id} className="flex items-center justify-between gap-3 rounded-xl border border-line bg-bg/40 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold">{p.name}</p>
                    <p className="text-[11px] text-muted">{p.business_unit}</p>
                  </div>
                  <Button size="sm" onClick={() => start(p)} loading={busy === p.id}>
                    Start delivery
                  </Button>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-muted">
              Requires an approved Flow-1 pack (user stories & acceptance criteria). If a project
              isn’t ready, you’ll be told to finish its BRD first.
            </p>
          </CardBody>
        </Card>

        {/* timeline */}
        <Card>
          <CardHeader>
            <GitBranch className="h-4 w-4 text-brand" />
            <CardTitle>Delivery pipeline</CardTitle>
            {run && (
              <Badge tone={run.status === 'COMPLETED' ? 'success' : run.status === 'FAILED' || run.status === 'REJECTED' ? 'danger' : run.status === 'WAITING_APPROVAL' ? 'warning' : 'brand'} className="ml-auto">
                {run.status}
              </Badge>
            )}
          </CardHeader>
          <CardBody>
            {!run ? (
              <Empty icon={Rocket} title="No delivery running" hint="Start delivery on a project to watch the agents run." />
            ) : (
              <div className="space-y-1.5">
                <p className="mb-3 text-[12.5px]"><span className="text-muted">Project:</span> <span className="font-semibold">{run.project_name}</span></p>
                {STAGES.map((s) => {
                  const st = stageState(s.node)
                  const Icon = st === 'done' ? CheckCircle2 : st === 'wait' ? ShieldCheck : st === 'active' ? Loader2 : CircleDashed
                  return (
                    <div key={s.node} className={cn('flex items-start gap-2.5 rounded-lg px-2.5 py-2',
                      st === 'active' && 'bg-brand-soft', st === 'wait' && 'bg-warning/10')}>
                      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0',
                        st === 'done' ? 'text-success' : st === 'wait' ? 'text-warning' : st === 'active' ? 'text-brand animate-spin' : 'text-muted/50')} />
                      <div className="min-w-0">
                        <p className={cn('text-[12.5px] leading-snug', st === 'pending' ? 'text-muted' : 'font-medium text-ink', s.gate && 'flex items-center gap-1.5')}>
                          {s.label}
                          {s.gate && <Badge tone="warning">HITL</Badge>}
                        </p>
                        <p className="text-[11px] text-muted">{s.sub}</p>
                      </div>
                    </div>
                  )
                })}
                {run.status === 'WAITING_APPROVAL' && (
                  <div className="mt-3 space-y-2">
                    {pending.length === 0 ? (
                      <div className="rounded-lg bg-warning/10 px-3 py-2.5 text-[12px] text-warning">
                        Awaiting an approval — loading the pending gate…
                      </div>
                    ) : pending.map((a) => (
                      <div key={a.id} className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5">
                        <p className="text-[12px] font-semibold text-ink">
                          {a.gate.replaceAll('_', ' ')} · approver {a.approver_email}
                        </p>
                        <p className="mb-2 text-[11px] text-muted">
                          Decide here, or open the email in the Approval Outbox.
                        </p>
                        <div className="flex items-center gap-2">
                          <Button size="sm" onClick={() => decide(a, 'APPROVED')} loading={deciding === a.id}>Approve</Button>
                          <Button size="sm" variant="secondary" onClick={() => decide(a, 'CHANGES_REQUESTED')} loading={deciding === a.id}>Request changes</Button>
                          <button className="ml-auto text-[11px] font-semibold text-brand underline" onClick={() => nav('/outbox')}>View email</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {run.status === 'COMPLETED' && (
                  <div className="mt-3 rounded-lg bg-success/10 px-3 py-2.5 text-[12px] text-success">
                    Delivery complete — stories marked Done in Jira and handed to DevOps. See the artifacts in{' '}
                    <button className="font-semibold underline" onClick={() => nav('/documents')}>Documents</button>.
                  </div>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
