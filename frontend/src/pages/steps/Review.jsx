import {
  ArrowRight, CheckCircle2, FileSearch, Loader2, MessageSquare, ShieldQuestion,
  ThumbsDown, ThumbsUp, XCircle,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { fmtDateTime, titleCase } from '../../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Confidence, Empty, Textarea, useToast } from '../../components/ui'

const PRIORITY = { MUST: 'danger', SHOULD: 'warning', COULD: 'default', WONT: 'outline' }

/**
 * What the graph ACTUALLY does after each gate.
 *
 * The stepper used to run Review → "Generate BRD", which is a lie. After Gate 1 the graph runs
 * Agent 3 (wireframes) and Agent 4 (the whole documentation set) and then SUSPENDS AGAIN at Gate 2.
 * Promising a BRD that two agents and a second approval stand in front of is exactly the sort of
 * thing that falls apart the moment someone in the room asks a follow-up question — and it hides the
 * second gate, which is half the governance story.
 */
const AFTER_GATE = {
  concept_note_gate: {
    next: 'Agent 3 (wireframes) → Agent 4 (BRD · FRD · SRS · stories · APIs · NFRs) → Gate 2',
    then: 'The run suspends again at Gate 2. Nothing reaches the sprint plan without a second sign-off.',
  },
  requirement_docs_gate: {
    next: 'Agent 6 (epics, stories, points → Jira) → the run completes',
    then: 'This is the last gate. Approving it seals the documentation set.',
  },
}

export default function Review({ project, onNext, onBack, onWatchRun }) {
  const toast = useToast()
  const [approvals, setApprovals] = useState([])
  const [requirements, setRequirements] = useState([])
  const [comments, setComments] = useState({})
  const [busy, setBusy] = useState(null)
  const [run, setRun] = useState(null)

  const load = useCallback(async () => {
    if (!project) return
    const [aps, arts, runs] = await Promise.all([
      api.approvals(project.id), api.artifacts(project.id), api.runs(project.id),
    ])
    setApprovals(aps)
    setRun(runs[0] || null)
    const reqArt = arts.find((a) => a.type === 'BUSINESS_REQUIREMENTS')
    if (reqArt) {
      const v = await api.version(reqArt.versions[reqArt.versions.length - 1].id)
      setRequirements(v.payload.requirements || [])
    }
  }, [project])

  useEffect(() => { load() }, [load])

  // While the agents are mid-flight the next gate has not been raised yet. Poll, rather than showing
  // an empty screen that implies nothing is happening.
  useEffect(() => {
    if (run?.status !== 'RUNNING' && run?.status !== 'PENDING') return
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [run?.status, load])

  const decide = async (a, decision) => {
    setBusy(a.id)
    const text = (comments[a.id] || '').trim()
    try {
      await api.decide(a.id, {
        decision,
        comments: text ? text.split('\n').filter(Boolean).map((body) => ({ author: a.approver_email, body })) : [],
      })
      setComments((c) => ({ ...c, [a.id]: '' }))
      const next = AFTER_GATE[a.gate]?.next
      toast(
        decision === 'APPROVED' ? 'Approved — the graph resumes' : 'Changes requested — the agent will regenerate',
        {
          tone: decision === 'APPROVED' ? 'success' : 'warning',
          detail: decision === 'APPROVED'
            ? `This exact version is sealed as approved. Now running: ${next || 'the next stage'}.`
            : 'Your comments are injected into the agent’s prompt and stored as long-term memory.',
          duration: 7000,
        },
      )
      setTimeout(load, 900)
    } catch (e) {
      toast('Decision failed', { tone: 'error', detail: e.message })
    } finally {
      setBusy(null)
    }
  }

  if (!project) return <Empty icon={ShieldQuestion} title="No project selected" />

  const pending = approvals.filter((a) => a.status === 'PENDING')
  const decided = approvals.filter((a) => a.status !== 'PENDING')
  const conceptApproved = decided.some((a) => a.gate === 'concept_note_gate' && a.status === 'APPROVED')
  const docsApproved = decided.some((a) => a.gate === 'requirement_docs_gate' && a.status === 'APPROVED')
  const running = run?.status === 'RUNNING' || run?.status === 'PENDING'
  // Concept note signed off, docs gate not yet raised: Agents 3 and 4 are working right now.
  const mid = conceptApproved && !docsApproved && !pending.length && running

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Review Center</h1>
          <p className="text-[13px] text-muted mt-1">
            Nothing proceeds without a named human approving a named version. Comments become the
            agent's next prompt — and permanent memory.
          </p>
        </div>
        <Badge tone={pending.length ? 'warning' : mid ? 'brand' : 'success'}>
          {pending.length ? `${pending.length} awaiting you` : mid ? 'Agents running' : 'Nothing pending'}
        </Badge>
      </div>

      {/* Between the gates: say so, loudly. An empty Review screen looks like a dead end. */}
      {mid && (
        <Card className="border-brand/40 bg-brand-soft/40">
          <CardBody className="flex items-center gap-4">
            <Loader2 className="h-5 w-5 shrink-0 animate-spin text-brand" />
            <div className="flex-1">
              <p className="text-[13px] font-semibold text-brand">
                Concept note approved — Agents 3 and 4 are running now
              </p>
              <p className="mt-0.5 text-[12px] text-muted">
                Wireframes, then the BRD, FRD, SRS, user stories, API requirements and NFRs. The run
                will suspend again at <strong>Gate 2</strong> and come back here for your second
                sign-off. The BRD does not exist yet.
              </p>
            </div>
            <Button variant="soft" onClick={onWatchRun}>Watch the pipeline →</Button>
          </CardBody>
        </Card>
      )}

      {pending.map((a) => (
        <Card key={a.id} className="border-warning/40">
          <CardHeader className="bg-warning/5">
            <ShieldQuestion className="h-4 w-4 text-warning" />
            <CardTitle>{titleCase(a.gate)} · round {a.round}</CardTitle>
            <Badge tone="warning" className="ml-auto">Awaiting decision</Badge>
          </CardHeader>
          <CardBody className="space-y-3">
            <p className="text-[12px] text-muted">
              Approver: <strong className="text-ink">{a.approver_email}</strong>
              {a.expires_at && <> · expires {fmtDateTime(a.expires_at)}</>}
            </p>

            {AFTER_GATE[a.gate] && (
              <div className="rounded-xl border border-line bg-bg/60 px-3.5 py-3">
                <p className="text-[10.5px] font-semibold uppercase tracking-wider text-muted">
                  If you approve, what runs next
                </p>
                <p className="mt-1 flex items-center gap-1.5 text-[12.5px] font-medium text-ink">
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-brand" />
                  {AFTER_GATE[a.gate].next}
                </p>
                <p className="mt-1 text-[11.5px] text-muted">{AFTER_GATE[a.gate].then}</p>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">
                Comments <span className="font-normal">— one per line. These drive the regeneration.</span>
              </label>
              <Textarea rows={3} value={comments[a.id] || ''}
                onChange={(e) => setComments((c) => ({ ...c, [a.id]: e.target.value }))}
                placeholder="e.g. The retry-cap conflict is unresolved — state it explicitly as a risk." />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="success" onClick={() => decide(a, 'APPROVED')} loading={busy === a.id}>
                <ThumbsUp className="h-3.5 w-3.5" /> Approve
              </Button>
              <Button variant="secondary" onClick={() => decide(a, 'CHANGES_REQUESTED')} loading={busy === a.id}>
                <MessageSquare className="h-3.5 w-3.5" /> Request changes
              </Button>
              <Button variant="danger" onClick={() => decide(a, 'REJECTED')} loading={busy === a.id}>
                <ThumbsDown className="h-3.5 w-3.5" /> Reject
              </Button>
            </div>
          </CardBody>
        </Card>
      ))}

      <Card>
        <CardHeader>
          <FileSearch className="h-4 w-4 text-brand" />
          <CardTitle>Extracted requirements</CardTitle>
          <span className="ml-auto text-[11px] text-muted hidden md:inline">
            Every one cites its source. None were invented.
          </span>
        </CardHeader>
        <CardBody className={requirements.length ? 'space-y-2.5' : ''}>
          {requirements.length === 0 ? (
            running ? (
              <Empty icon={Loader2} title="Agent 1 is still working"
                hint="Requirements appear the moment it finishes. This screen refreshes itself." />
            ) : run?.status === 'FAILED' ? (
              <Empty icon={XCircle} title="The run failed before requirements were extracted"
                hint={(run.error || '').slice(0, 160) || 'See the timeline on the AI Analysis step.'} />
            ) : (
              <Empty icon={FileSearch} title="No requirements yet" hint="Run the agents from AI Analysis." />
            )
          ) : requirements.map((r) => (
            <div key={r.id} className="rounded-xl border border-line bg-surface p-4 hover:shadow-card transition-shadow">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5 mb-1">
                    <code className="font-mono text-[11px] font-bold text-brand">{r.id}</code>
                    <span className="text-[13px] font-semibold">{r.title}</span>
                    <Badge tone={PRIORITY[r.priority] || 'default'}>{r.priority}</Badge>
                    <Badge tone="outline">{r.category}</Badge>
                  </div>
                  <p className="text-[12.5px] text-muted leading-relaxed">{r.statement}</p>

                  {r.open_question && (
                    <div className="mt-2 rounded-lg border border-warning/20 bg-warning/5 px-2.5 py-1.5">
                      <p className="text-[11.5px] text-warning"><strong>Open question:</strong> {r.open_question}</p>
                    </div>
                  )}

                  <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">Traced to</span>
                      {(r.source_evidence || []).map((s, i) => <Badge key={i} tone="brand">{s}</Badge>)}
                    </div>
                    {r.actors?.length > 0 && (
                      <span className="text-[11px] text-muted">Actors: {r.actors.join(', ')}</span>
                    )}
                  </div>
                </div>
                {/* Confidence deliberately not shown. In offline mode it was 0.84 + a hash of the
                    statement; live, it is the model's own self-report, which is uncalibrated and
                    reliably over-confident. A precise-looking percentage that cannot survive the
                    question "so is an 87% requirement wrong 13% of the time?" is worse than no
                    number at all. The VALUE is still computed and still drives the low-confidence
                    risk flag (<0.75) in the concept note — it just no longer masquerades as a
                    measurement on screen. */}
              </div>
            </div>
          ))}
        </CardBody>
      </Card>

      {decided.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Decision history</CardTitle></CardHeader>
          <CardBody className="space-y-1.5">
            {decided.map((a) => (
              <div key={a.id} className="flex items-center gap-2.5 text-[12px]">
                {a.status === 'APPROVED'
                  ? <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                  : <XCircle className="h-3.5 w-3.5 text-danger" />}
                <span className="font-medium">{titleCase(a.gate)}</span>
                <span className="text-muted">round {a.round}</span>
                <Badge tone={a.status === 'APPROVED' ? 'success' : 'danger'} className="ml-auto">
                  {a.status.replaceAll('_', ' ')}
                </Badge>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-3 pb-2">
        <Button variant="secondary" onClick={onBack}>← Back</Button>

        {mid ? (
          <>
            <Button onClick={onWatchRun}>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Agents 3 &amp; 4 running — watch
            </Button>
            <span className="text-[11.5px] text-muted">
              The BRD does not exist yet. Agent 4 writes it, and Gate 2 stands in front of it.
            </span>
          </>
        ) : docsApproved ? (
          <Button onClick={onNext}>Generate BRD →</Button>
        ) : (
          <Button variant="secondary" onClick={onNext}>View documents →</Button>
        )}
      </div>
    </div>
  )
}
