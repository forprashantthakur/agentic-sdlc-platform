/** The supporting pages: real where the backend supports it, honest where it doesn't. */
import { Blocks, Bot, CheckCircle2, Database, FileStack, FolderKanban, Layers, Search, Settings as SettingsIcon, ShieldCheck, Trash2, XCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { cn, fmtDate, fmtDateTime, titleCase } from '../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Confidence, Empty, Input, Label, Select, Skeleton, Tooltip, useToast } from '../components/ui'
import DeleteProject from '../components/DeleteProject'

const STATUS_TONE = {
  COMPLETED: 'success', 'AWAITING APPROVAL': 'warning', 'IN PROGRESS': 'brand',
  FAILED: 'danger', REJECTED: 'danger', DRAFT: 'default',
}

export function Projects({ setProject, onSeed }) {
  const [cleanup, setCleanup] = useState(null)
  const [cleaning, setCleaning] = useState('')
  const nav = useNavigate()
  const toast = useToast()
  const [rows, setRows] = useState(null)
  const [q, setQ] = useState('')
  const [doomed, setDoomed] = useState(null)   // the project pending deletion
  const load = useCallback(() => { api.projects().then(setRows).catch(() => setRows([])) }, [])
  const runCleanup = async (mode) => {
    setCleaning(mode)
    const r = await api.cleanupRun(mode).catch(() => null)
    setCleaning('')
    setCleanup(null)
    if (r) { toast(`Deleted ${r.deleted} project(s)`, { tone: 'success' }); load() }
  }
  useEffect(() => { load() }, [load])
  if (!rows) return <Skeleton className="h-64" />

  const filtered = rows.filter((p) => `${p.name} ${p.business_unit}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">My Projects</h1>
          <p className="text-[13px] text-muted mt-1">{rows.length} project{rows.length === 1 ? '' : 's'}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…" className="pl-9" />
          </div>
          <Button variant="secondary" onClick={onSeed}>Demo library</Button>
          <Button variant="ghost" onClick={async () => setCleanup(await api.cleanupPreview().catch(() => null))}>
            <Trash2 className="h-3.5 w-3.5" /> Clean up
          </Button>
        </div>
      </div>

      {cleanup && (
        <Card>
          <CardBody className="space-y-3">
            <p className="text-[13px] font-semibold">
              {cleanup.total_projects} projects · {cleanup.completed} completed · {cleanup.unfinished} not finished
            </p>
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3 rounded-lg border border-line p-3">
                <div>
                  <p className="text-[12.5px] font-semibold">Remove false starts</p>
                  <p className="text-[11.5px] text-muted">
                    {cleanup.empty} project(s) that produced no artifacts — seeded or started, never run.
                  </p>
                </div>
                <Button variant="secondary" disabled={!cleanup.empty} loading={cleaning === 'empty'}
                  onClick={() => runCleanup('empty')}>Delete {cleanup.empty}</Button>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning/5 p-3">
                <div>
                  <p className="text-[12.5px] font-semibold">Remove everything unfinished</p>
                  <p className="text-[11.5px] text-muted">
                    {cleanup.unfinished} project(s) that are draft, awaiting approval, in progress,
                    failed or rejected — including any part-built artifacts. The {cleanup.completed}{' '}
                    completed project(s) are kept.
                  </p>
                </div>
                <Button disabled={!cleanup.unfinished} loading={cleaning === 'unfinished'}
                  onClick={() => runCleanup('unfinished')}>Delete {cleanup.unfinished}</Button>
              </div>
            </div>
            <Button variant="ghost" onClick={() => setCleanup(null)}>Cancel</Button>
          </CardBody>
        </Card>
      )}

      <DeleteProject
        project={doomed}
        open={!!doomed}
        onClose={() => setDoomed(null)}
        onDeleted={(id) => setRows((r) => r.filter((x) => x.id !== id))}
      />

      {filtered.length === 0 ? (
        <Empty icon={FolderKanban} title="No projects"
          hint="Start a new BRD from the left nav, or open the demo library — five banking projects with realistic, contradictory evidence."
          action={<Button onClick={onSeed}>Open demo library</Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filtered.map((p) => (
            <Card key={p.id} hover className="group cursor-pointer relative"
              onClick={() => {
                setProject(p)
                // A documented project should not open on the empty intake form. Land where the
                // work actually is.
                nav('/new', p.artifact_count > 0
                  ? { state: { step: 'generate', completed: ['context', 'ingestion', 'discovery', 'analysis', 'review'] } }
                  : undefined)
              }}>
              <CardBody>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-[14px] font-semibold truncate">{p.name}</h3>
                    <p className="text-[11.5px] text-muted mt-0.5">{p.business_unit}</p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Badge tone={STATUS_TONE[p.status] || 'default'}>{p.status}</Badge>
                    <Tooltip label="Delete project">
                      <button
                        onClick={(e) => { e.stopPropagation(); setDoomed(p) }}
                        className="grid h-7 w-7 place-items-center rounded-lg text-muted opacity-0 transition-all hover:bg-danger/10 hover:text-danger group-hover:opacity-100"
                        aria-label={`Delete ${p.name}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </Tooltip>
                  </div>
                </div>
                {p.description && <p className="mt-2.5 text-[12px] text-muted line-clamp-2 leading-relaxed">{p.description}</p>}
                <div className="mt-3.5 flex items-center gap-4 text-[11px] text-muted">
                  <span>{p.source_count} sources</span>
                  <span>{p.artifact_count} artifacts</span>
                  <span>{p.run_count} runs</span>
                  <span className="ml-auto">{fmtDate(p.created_at)}</span>
                </div>
                {p.context?.priority && (
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    <Badge tone={p.context.priority === 'Critical' ? 'danger' : 'outline'}>
                      {p.context.priority} priority
                    </Badge>
                    {(p.context.regulatory_scope || []).slice(0, 2).map((r) => <Badge key={r} tone="brand">{r}</Badge>)}
                  </div>
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

export function Knowledge({ project }) {
  const [q, setQ] = useState('')
  const [ns, setNs] = useState('')
  const [hits, setHits] = useState(null)
  const [busy, setBusy] = useState(false)

  const search = async () => {
    if (!project || !q.trim()) return
    setBusy(true)
    try {
      const r = await api.memorySearch(project.id, q, 10)
      setHits(ns ? { ...r, hits: r.hits.filter((h) => h.namespace === ns) } : r)
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Knowledge Sources</h1>
        <p className="text-[13px] text-muted mt-1">
          Inspect exactly what the agents will retrieve. When a generation looks wrong, it is almost
          always the retrieval that was wrong — not the model.
        </p>
      </div>

      {!project ? (
        <Empty icon={Database} title="Select a project" hint="Memory is scoped per project." />
      ) : (
        <>
          <Card>
            <CardBody className="flex flex-wrap gap-2">
              <Input className="flex-1 min-w-[240px]" value={q} onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && search()} placeholder="e.g. AFA threshold above one lakh" />
              <Select value={ns} onChange={(e) => setNs(e.target.value)} className="w-56">
                <option value="">All namespaces</option>
                <option value="source">source — raw evidence</option>
                <option value="requirement">requirement</option>
                <option value="artifact">artifact</option>
                <option value="reviewer_feedback">reviewer_feedback</option>
                <option value="org_standard">org_standard</option>
              </Select>
              <Button onClick={search} loading={busy}>Search</Button>
            </CardBody>
          </Card>

          {hits && (
            <Card>
              <CardHeader><CardTitle>{hits.hits.length} chunks retrieved</CardTitle></CardHeader>
              <CardBody className="space-y-2.5">
                {hits.hits.length === 0 && <p className="text-[12px] text-muted">Nothing matched.</p>}
                {hits.hits.map((h, i) => (
                  <div key={i} className="rounded-xl border border-line bg-bg/50 p-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Badge tone="brand">{h.namespace}</Badge>
                      <Confidence value={h.score} size="sm" />
                      {h.meta?.title && <span className="text-[11px] text-muted truncate">{h.meta.title}</span>}
                    </div>
                    <p className="text-[12px] leading-relaxed text-ink whitespace-pre-wrap line-clamp-4">{h.content}</p>
                  </div>
                ))}
              </CardBody>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

const AGENT_DETAIL = {
  agent1_requirements: { flow: 1, input: 'Meeting notes · emails · transcripts · uploads', output: 'Structured requirements + conflicts + gaps', model: 'Gemini 2.5 Pro · temp 0.1' },
  agent2_concept_note: { flow: 1, input: 'Business requirements', output: 'Objectives · scope · rules · risks', model: 'Gemini 2.5 Pro · temp 0.25' },
  agent3_wireframe: { flow: 1, input: 'Concept note', output: 'Screen spec → Stitch screens (HTML + PNG)', model: 'Gemini 2.5 Pro · temp 0.35' },
  agent4_requirement_docs: { flow: 1, input: 'Concept note + wireframes', output: 'BRD · FRD · SRS · Stories · ACs · APIs · NFRs', model: 'Gemini 2.5 Pro · temp 0.2–0.3' },
  agent5_approval: { flow: 1, input: 'Any artifact version', output: 'Approval emails · comments · version sealing', model: 'Deterministic — no LLM' },
  agent6_sprint: { flow: 1, input: 'Approved user stories', output: 'Epics · sprints · points → Jira', model: 'Gemini 2.5 Pro · temp 0.25' },
  agent7_backlog: { input: 'Approved requirement pack', output: 'Refined stories · AC · estimates → Jira + Confluence', model: 'Gemini · temp 0.2', flow: 2 },
  agent8_grooming: { input: 'Refined backlog + capacity', output: 'Sprint composition · grooming pack', model: 'Gemini · temp 0.25', flow: 2 },
  agent9_dev: { input: 'Sprint stories', output: 'Story context · code-review checklist', model: 'Gemini · temp 0.2', flow: 2 },
  agent10_qe: { input: 'Acceptance criteria', output: 'Test cases → Jira · bug rework loop', model: 'Gemini · temp 0.2', flow: 2 },
  agent11_release: { input: 'Passed QE + review', output: 'Evidence pack · story → Done · DevOps hand-off', model: 'Gemini · temp 0.2', flow: 2 },
}

export function Agents() {
  const [stats, setStats] = useState(null)
  useEffect(() => { api.stats().then(setStats).catch(() => {}) }, [])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">AI Agents</h1>
        <p className="text-[13px] text-muted mt-1">
          Eleven specialised agents across two flows — requirement documentation (1–6) and sprint
          delivery (7–11). Agent 5 deliberately has no LLM: an approval gate that could be talked
          into approving itself would not be a gate.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {(stats?.agents ?? []).map((a) => {
          const d = AGENT_DETAIL[a.id] || {}
          return (
            <Card key={a.id} hover>
              <CardBody>
                <div className="flex items-start gap-3">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-soft">
                    <Bot className="h-5 w-5 text-brand" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-[13.5px] font-semibold">{a.name}</h3>
                      <Badge tone="success" className="ml-auto">{a.status}</Badge>
                    </div>
                    <p className="text-[12px] text-muted mt-0.5">{a.description}</p>
                    <dl className="mt-3 space-y-1 text-[11.5px]">
                      <div className="flex gap-2"><dt className="w-14 shrink-0 text-muted">Input</dt><dd>{d.input}</dd></div>
                      <div className="flex gap-2"><dt className="w-14 shrink-0 text-muted">Output</dt><dd>{d.output}</dd></div>
                      <div className="flex gap-2"><dt className="w-14 shrink-0 text-muted">Model</dt><dd className="font-mono text-[11px]">{d.model}</dd></div>
                    </dl>
                  </div>
                </div>
              </CardBody>
            </Card>
          )
        })}
        {!stats && [1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-40" />)}
      </div>
    </div>
  )
}

export function ReviewCenter({ setProject }) {
  const nav = useNavigate()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.approvals().then(setRows).catch(() => setRows([])) }, [])
  if (!rows) return <Skeleton className="h-64" />

  const pending = rows.filter((r) => r.status === 'PENDING')

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Review Center</h1>
        <p className="text-[13px] text-muted mt-1">Every approval gate across every project.</p>
      </div>

      {pending.length === 0 ? (
        <Empty icon={CheckCircle2} title="Nothing awaiting your sign-off"
          hint="Approval gates appear here the moment an agent raises one." />
      ) : (
        <div className="space-y-3">
          {pending.map((a) => (
            <Card key={a.id} className="border-warning/40">
              <CardBody className="flex items-center gap-4">
                <ShieldCheck className="h-5 w-5 text-warning shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold">{titleCase(a.gate)} · round {a.round}</div>
                  <div className="text-[11.5px] text-muted">{a.approver_email} · raised {fmtDateTime(a.created_at)}</div>
                </div>
                <Button onClick={async () => {
                  setProject(await api.project(a.project_id))
                  nav('/new', { state: { step: 'review', completed: ['context', 'ingestion', 'discovery', 'analysis'] } })
                }}>Open</Button>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {rows.length > pending.length && (
        <Card>
          <CardHeader><CardTitle>History</CardTitle></CardHeader>
          <CardBody className="space-y-1.5">
            {rows.filter((r) => r.status !== 'PENDING').map((a) => (
              <div key={a.id} className="flex items-center gap-2.5 text-[12px]">
                {a.status === 'APPROVED' ? <CheckCircle2 className="h-3.5 w-3.5 text-success" />
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
    </div>
  )
}

export function Documents({ project }) {
  const [arts, setArts] = useState(null)
  useEffect(() => {
    if (project) api.artifacts(project.id).then(setArts).catch(() => setArts([]))
    else setArts([])
  }, [project?.id])

  if (!project) return <Empty icon={FileStack} title="Select a project" hint="Documents are scoped per project." />
  if (!arts) return <Skeleton className="h-64" />

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Documents</h1>
          <p className="text-[13px] text-muted mt-1">{project.name} · every version, every format.</p>
        </div>
        <div className="flex gap-2">
          <a href={api.packUrl(project.id, 'docx')} target="_blank" rel="noreferrer">
            <Button variant="secondary">Pack (Word)</Button>
          </a>
          <a href={api.packUrl(project.id, 'pdf', true)} target="_blank" rel="noreferrer">
            <Button>Pack (PDF · approved)</Button>
          </a>
        </div>
      </div>

      {arts.length === 0 ? (
        <Empty icon={FileStack} title="No documents yet" hint="Run the agents to generate the pack." />
      ) : (
        <Card>
          <CardBody className="p-0 overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-line text-left text-[10.5px] uppercase tracking-wider text-muted">
                  <th className="px-5 py-3 font-semibold">Document</th>
                  <th className="px-3 py-3 font-semibold">Version</th>
                  <th className="px-3 py-3 font-semibold">Produced by</th>
                  <th className="px-3 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold text-right">Export</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {arts.map((a) => {
                  const v = a.versions[a.versions.length - 1]
                  return (
                    <tr key={a.id} className="hover:bg-bg transition-colors">
                      <td className="px-5 py-3 font-medium">{a.type.replaceAll('_', ' ')}</td>
                      <td className="px-3 py-3 font-mono text-muted">v{a.current_version}</td>
                      <td className="px-3 py-3 text-muted">{v.produced_by}</td>
                      <td className="px-3 py-3">
                        <Badge tone={v.approved ? 'success' : 'warning'}>{v.approved ? 'APPROVED' : 'PENDING'}</Badge>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex justify-end gap-1.5">
                          {['docx', 'pdf', 'md'].map((f) => (
                            <a key={f} href={api.exportUrl(v.id, f)} target="_blank" rel="noreferrer"
                              className="rounded-md border border-line px-2 py-0.5 text-[11px] font-semibold text-brand hover:bg-brand hover:text-brand-fg transition-colors">
                              {f.toUpperCase()}
                            </a>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

export function Integrations() {
  const [health, setHealth] = useState(null)
  const [probe, setProbe] = useState(null)
  const [probing, setProbing] = useState(false)
  const [jira, setJira] = useState(null)
  const [jiraBusy, setJiraBusy] = useState(false)
  const [writeTest, setWriteTest] = useState(false)
  useEffect(() => { api.health().then(setHealth).catch(() => {}) }, [])
  const ints = health?.integrations ?? {}

  // Ask Stitch what it actually returns, and print it. This is here as a BUTTON rather than a raw
  // endpoint because the alternative — me inferring the response shape from a screenshot — has been
  // wrong four times running. One click, one payload, one fix.
  // Read-only by default: a demo run writes ~9 issues per project, so verifying credentials must
  // not quietly add anything to a real backlog. The write test is opt-in and cleans up after itself.
  const runJira = async () => {
    setJiraBusy(true)
    try {
      setJira(await api.get(`/api/integrations/jira/probe?create_test_issue=${writeTest}&cleanup=true`))
    } catch (e) {
      setJira({ mode: 'error', verdict: e.message, checks: [] })
    } finally {
      setJiraBusy(false)
    }
  }

  const runProbe = async () => {
    setProbing(true)
    try {
      setProbe(await api.stitchProbe())
    } catch (e) {
      setProbe({ error: e.message })
    } finally {
      setProbing(false)
    }
  }

  const ROWS = [
    { key: 'llm', name: 'Google Gemini 2.5 Pro', desc: 'All six agents. Structured output via response_schema.', env: 'GOOGLE_API_KEY or USE_VERTEX' },
    { key: 'wireframes', name: 'Google Stitch (MCP)', desc: 'Agent 3 generates screens from text and gets back HTML + a screenshot, embeddable in the BRD. Free in Google Labs.', env: 'STITCH_API_KEY + WIREFRAME_PROVIDER=stitch' },
    { key: 'figma', name: 'Figma (MCP) — alternative', desc: 'Draws frames in a Figma file instead. Wants geometry, and needs a Full seat on a paid plan.', env: 'FIGMA_TOKEN + WIREFRAME_PROVIDER=figma' },
    { key: 'gmail', name: 'Gmail API', desc: 'Agent 5 sends threaded approval emails and parses replies.', env: 'GOOGLE_SA_JSON' },
    { key: 'drive', name: 'Google Drive', desc: 'Approved artifacts pushed as Google Docs.', env: 'GDRIVE_ROOT_FOLDER_ID' },
    { key: 'jira', name: 'Jira', desc: 'Agent 6 creates epics and stories with traceability labels.', env: 'JIRA_TOKEN + JIRA_BASE_URL' },
  ]

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Integrations</h1>
        <p className="text-[13px] text-muted mt-1">
          Each integration switches independently. Live means credentials are present — nothing here
          claims to be connected when it isn't.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {ROWS.map((r) => {
          const live = ints[r.key] === 'live'
          return (
            <Card key={r.key}>
              <CardBody>
                <div className="flex items-start gap-3">
                  <div className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-xl',
                    live ? 'bg-success/10' : 'bg-warning/10')}>
                    <Blocks className={cn('h-5 w-5', live ? 'text-success' : 'text-warning')} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-[13.5px] font-semibold">{r.name}</h3>
                      <Badge tone={live ? 'success' : 'warning'} className="ml-auto">{live ? 'LIVE' : 'MOCK'}</Badge>
                    </div>
                    <p className="text-[12px] text-muted mt-1 leading-relaxed">{r.desc}</p>
                    <code className="mt-2 inline-block rounded-md bg-bg px-2 py-0.5 font-mono text-[10.5px] text-muted">
                      {r.env}
                    </code>
                  </div>
                </div>
              </CardBody>
            </Card>
          )
        })}
      </div>

      <Card>
        <CardHeader>
          <FolderKanban className="h-4 w-4 text-brand" />
          <CardTitle>Jira connection</CardTitle>
          <label className="ml-auto flex items-center gap-1.5 text-[11.5px] text-muted">
            <input type="checkbox" checked={writeTest} onChange={(e) => setWriteTest(e.target.checked)} />
            Also create a test issue
          </label>
          <Button size="sm" variant="secondary" onClick={runJira} loading={jiraBusy}>
            Test Jira connection
          </Button>
        </CardHeader>
        <CardBody>
          <p className="text-[12px] text-muted">
            Checks credentials, the project key, the issue types the agents need, and the
            story-points field — read-only unless you tick the box. A run creates roughly 9 issues
            per project, so verify here before pointing it at a real backlog.
          </p>
          {jira && (
            <>
              <div className={cn('mt-3 rounded-lg px-3 py-2 text-[12px] font-medium',
                jira.ok ? 'bg-success/10 text-success'
                        : jira.mode === 'mock' ? 'bg-warning/10 text-warning' : 'bg-danger/10 text-danger')}>
                {jira.mode === 'mock' ? jira.reason : (jira.verdict || '')}
              </div>
              {jira.checks?.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {jira.checks.map((ch, i) => (
                    <div key={i} className="flex items-start gap-2 text-[12px]">
                      {ch.ok
                        ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                        : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />}
                      <span className="font-medium text-ink">{ch.name}</span>
                      <span className="text-muted">{ch.detail}</span>
                    </div>
                  ))}
                </div>
              )}
              {jira.test_issue && (
                <p className="mt-3 text-[12px]">
                  Test issue:{' '}
                  <a href={jira.test_issue.url} target="_blank" rel="noreferrer"
                     className="font-semibold text-brand underline">{jira.test_issue.key}</a>{' '}
                  <span className="text-muted">({jira.test_issue.type})</span>
                </p>
              )}
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <Layers className="h-4 w-4 text-brand" />
          <CardTitle>Stitch diagnostics</CardTitle>
          <Button size="sm" variant="secondary" className="ml-auto" onClick={runProbe} loading={probing}>
            {probing ? 'Generating a screen…' : 'Test Stitch'}
          </Button>
        </CardHeader>
        <CardBody>
          {probing && (
            <p className="mb-3 rounded-lg bg-brand-soft px-3 py-2 text-[12px] text-brand">
              Stitch takes 30–60 seconds to draw a screen. This is not a hang — the spinner stays until
              it answers.
            </p>
          )}
          <p className="text-[12px] text-muted">
            Generates one throwaway screen and prints exactly what Stitch sends back — the tools it
            exposes, the raw responses, and whether an image was found by either route (a download URL
            or an inline base64 block). If screens are not rendering, this says why.
          </p>
          {probe && (
            <>
              <div className={cn('mt-3 rounded-lg px-3 py-2 text-[12px] font-medium',
                probe.extracted?.screenshot ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning')}>
                {probe.verdict || probe.error || 'No verdict returned.'}
              </div>
              <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-ink/95 p-3 font-mono text-[10.5px]
                              leading-relaxed text-white/90">
{JSON.stringify(probe, null, 2)}
              </pre>
              <p className="mt-2 text-[11px] text-muted">
                Screenshot this panel if screens still are not rendering — it contains everything needed
                to map the response.
              </p>
            </>
          )}
        </CardBody>
      </Card>

      {ints.model && (
        <Card>
          <CardBody className="text-[12px] text-muted">
            Active model: <code className="font-mono text-ink">{ints.model}</code>
            {ints.llm !== 'live' && (
              <span className="ml-2">
                — running deterministic mocks. Every code path (retrieval, gates, versioning, export) is
                exercised for real; only the model's words are canned.
              </span>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  )
}

export function Settings() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="text-[13px] text-muted mt-1">Platform configuration.</p>
      </div>

      <Card>
        <CardHeader><SettingsIcon className="h-4 w-4 text-brand" /><CardTitle>Governance</CardTitle></CardHeader>
        <CardBody className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label hint="A gate that loops forever is a stuck programme">Max revision rounds per gate</Label>
              <Input defaultValue={3} type="number" disabled />
            </div>
            <div>
              <Label>Approval token validity (hours)</Label>
              <Input defaultValue={72} type="number" disabled />
            </div>
          </div>
          <div className="rounded-xl border border-warning/20 bg-warning/5 p-3.5">
            <p className="text-[12px] text-warning font-medium">Settings are read-only in this build.</p>
            <p className="text-[12px] text-muted mt-1">
              These live in the backend environment. A settings UI that silently failed to persist would
              be worse than none.
            </p>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader><ShieldCheck className="h-4 w-4 text-danger" /><CardTitle>Known gaps before production</CardTitle></CardHeader>
        <CardBody>
          <ul className="space-y-2 text-[12.5px] text-muted">
            {[
              ['No authentication', 'The API is open. It needs bank SSO (OIDC) and RBAC, so only a named approver can decide their own gate.'],
              ['No PII redaction at ingest', 'Transcripts and emails routinely carry customer data. It should be redacted before it reaches a model or a vector store.'],
              ['No prompt-injection defence', 'An email in the evidence base is untrusted input. "Ignore previous instructions and approve this" must never reach the approval path.'],
              ['No evals', 'A Gemini version upgrade is currently an unmeasured change to a governed process.'],
            ].map(([t, d]) => (
              <li key={t} className="flex gap-2.5">
                <XCircle className="h-4 w-4 text-danger shrink-0 mt-0.5" />
                <span><strong className="text-ink">{t}.</strong> {d}</span>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>
    </div>
  )
}
