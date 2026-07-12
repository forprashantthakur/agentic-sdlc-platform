import { CheckCircle2, FileSearch, MessageSquare, ShieldQuestion, ThumbsDown, ThumbsUp, XCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { fmtDateTime, titleCase } from '../../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Confidence, Empty, Textarea, useToast } from '../../components/ui'

const PRIORITY = { MUST: 'danger', SHOULD: 'warning', COULD: 'default', WONT: 'outline' }

export default function Review({ project, onNext, onBack }) {
  const toast = useToast()
  const [approvals, setApprovals] = useState([])
  const [requirements, setRequirements] = useState([])
  const [comments, setComments] = useState({})
  const [busy, setBusy] = useState(null)

  const load = useCallback(async () => {
    if (!project) return
    const [aps, arts] = await Promise.all([api.approvals(project.id), api.artifacts(project.id)])
    setApprovals(aps)
    const reqArt = arts.find((a) => a.type === 'BUSINESS_REQUIREMENTS')
    if (reqArt) {
      const v = await api.version(reqArt.versions[reqArt.versions.length - 1].id)
      setRequirements(v.payload.requirements || [])
    }
  }, [project])

  useEffect(() => { load() }, [load])

  const decide = async (a, decision) => {
    setBusy(a.id)
    const text = (comments[a.id] || '').trim()
    try {
      await api.decide(a.id, {
        decision,
        comments: text ? text.split('\n').filter(Boolean).map((body) => ({ author: a.approver_email, body })) : [],
      })
      setComments((c) => ({ ...c, [a.id]: '' }))
      toast(decision === 'APPROVED' ? 'Approved — the graph resumes' : 'Changes requested — the agent will regenerate', {
        tone: decision === 'APPROVED' ? 'success' : 'warning',
        detail: decision === 'APPROVED'
          ? 'This exact version is sealed as approved. Later versions are not.'
          : 'Your comments are injected into the agent’s prompt and stored as long-term memory.',
        duration: 6000,
      })
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

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Review Center</h1>
          <p className="text-[13px] text-muted mt-1">
            Nothing proceeds without a named human approving a named version. Comments become the
            agent's next prompt — and permanent memory.
          </p>
        </div>
        <Badge tone={pending.length ? 'warning' : 'success'}>
          {pending.length ? `${pending.length} awaiting you` : 'Nothing pending'}
        </Badge>
      </div>

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
          <span className="ml-auto text-[11px] text-muted hidden md:inline">Every one cites its source. None were invented.</span>
        </CardHeader>
        <CardBody className={requirements.length ? 'space-y-2.5' : ''}>
          {requirements.length === 0 ? (
            <Empty icon={FileSearch} title="No requirements yet" hint="Run the agents from AI Analysis." />
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
                <div className="shrink-0"><Confidence value={r.confidence} /></div>
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

      <div className="flex gap-3 pb-2">
        <Button variant="secondary" onClick={onBack}>← Back</Button>
        <Button onClick={onNext}>Generate BRD →</Button>
      </div>
    </div>
  )
}
