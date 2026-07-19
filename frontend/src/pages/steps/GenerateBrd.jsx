import { Download, FileCheck2, FileText, FolderKanban, GitCompare, Loader2, Rocket, Send } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { cn, fmtDateTime } from '../../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Empty, useToast } from '../../components/ui'
import { mdToHtml, toc } from '../../lib/md'
import Wireframes from '../../components/Wireframes'

const ORDER = ['BRD', 'FRD', 'SRS', 'CONCEPT_NOTE', 'BUSINESS_REQUIREMENTS', 'WIREFRAME',
  'USER_STORIES', 'ACCEPTANCE_CRITERIA', 'API_REQUIREMENTS', 'NFR', 'SPRINT_PLAN',
  // Phase 2 — sprint delivery (Agents 7-11)
  'REFINED_BACKLOG', 'GROOMING_PACK', 'CODE_REVIEW', 'TEST_CASES', 'RELEASE_HANDOFF']

const PHASE2 = new Set(['REFINED_BACKLOG', 'GROOMING_PACK', 'CODE_REVIEW', 'TEST_CASES', 'RELEASE_HANDOFF'])

export default function GenerateBrd({ project, onBack }) {
  const toast = useToast()
  const nav = useNavigate()
  const [artifacts, setArtifacts] = useState([])
  const [active, setActive] = useState(null)
  const [version, setVersion] = useState(null)
  const [diff, setDiff] = useState(null)
  const [showDiff, setShowDiff] = useState(false)
  const [loading, setLoading] = useState(true)
  const [jira, setJira] = useState(null)

  const open = async (a, vid) => {
    setActive(a)
    setShowDiff(false)
    const id = vid || a.versions[a.versions.length - 1].id
    setVersion(await api.version(id))
    setDiff(await api.diff(id).catch(() => null))
  }

  const load = useCallback(async () => {
    if (!project) return
    setLoading(true)
    const rows = await api.artifacts(project.id)
    const sorted = [...rows].sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type))
    setArtifacts(sorted)
    if (sorted.length) await open(sorted[0])
    setLoading(false)
  }, [project])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (project) api.get(`/api/integrations/jira/backlog?project_id=${project.id}`).then(setJira).catch(() => {})
  }, [project?.id])

  const notWired = (what) =>
    toast(`${what} — preview only`, {
      tone: 'warning',
      detail: 'Not wired to a backend yet. It is shown so the flow reads end-to-end, not to pretend it works.',
      duration: 5000,
    })

  if (!project) return <Empty icon={FileText} title="No project selected" />
  if (loading) return <Empty icon={Loader2} title="Loading documents…" />
  if (!artifacts.length) {
    return <Empty icon={FileText} title="No documents generated yet"
      hint="Run the agents and approve both gates — the BRD, FRD, SRS and the rest appear here." />
  }

  const headings = version ? toc(version.rendered_md) : []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">BRD &amp; Document Pack</h1>
          <p className="text-[13px] text-muted mt-1">
            Every document carries its version, the agent that produced it and the exact model — the
            provenance a model-risk review will ask for.
          </p>
        </div>
        <div className="flex gap-2">
          <a href={api.packUrl(project.id, 'docx')} target="_blank" rel="noreferrer">
            <Button variant="secondary"><Download className="h-3.5 w-3.5" /> Pack (Word)</Button>
          </a>
          <a href={api.packUrl(project.id, 'pdf', true)} target="_blank" rel="noreferrer">
            <Button variant="secondary"><Download className="h-3.5 w-3.5" /> Pack (PDF · approved)</Button>
          </a>
          <Button onClick={() => nav('/sprint-delivery')}>
            <Rocket className="h-3.5 w-3.5" /> Continue to Sprint Delivery →
          </Button>
        </div>
      </div>

      {jira?.ready && (
        <Card>
          <CardHeader>
            <FolderKanban className="h-4 w-4 text-brand" />
            <CardTitle>Delivered to Jira — project {jira.project_key}</CardTitle>
            <Badge tone={jira.live ? 'success' : 'warning'} className="ml-auto">
              {jira.live ? 'LIVE' : 'MOCK'}
            </Badge>
          </CardHeader>
          <CardBody>
            <p className="text-[12.5px] text-muted">
              {jira.counts.epics} epic · {jira.counts.stories} user stories created from the approved
              requirements{jira.live ? '' : ' (mock — set JIRA_MOCK=false to write to a real Jira)'}.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <a href={jira.run_url} target="_blank" rel="noreferrer">
                <Button><FolderKanban className="h-3.5 w-3.5" /> Open these stories in Jira</Button>
              </a>
              <a href={jira.board_url} target="_blank" rel="noreferrer">
                <Button variant="secondary">Open the {jira.project_key} board</Button>
              </a>
            </div>
            <div className="mt-3 max-h-64 overflow-y-auto rounded-lg border border-line">
              <table className="w-full text-[12px]">
                <thead className="sticky top-0 bg-bg">
                  <tr className="text-left text-[10.5px] uppercase tracking-wider text-muted">
                    <th className="px-3 py-2 font-semibold">Key</th>
                    <th className="px-3 py-2 font-semibold">Type</th>
                    <th className="px-3 py-2 font-semibold">Summary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {jira.issues.map((i) => (
                    <tr key={i.key}>
                      <td className="px-3 py-1.5 font-mono">
                        <a href={i.url} target="_blank" rel="noreferrer" className="font-semibold text-brand hover:underline">{i.key}</a>
                      </td>
                      <td className="px-3 py-1.5 text-muted">{i.type}</td>
                      <td className="px-3 py-1.5">{i.summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
      {jira && !jira.ready && jira.error && (
        <div className="rounded-xl border border-danger/30 bg-danger/5 px-3.5 py-2.5 text-[12px] text-danger">
          Jira did not receive this backlog — {jira.error}
        </div>
      )}

      {[['Phase 1 · Requirement Documentation', artifacts.filter((a) => !PHASE2.has(a.type))],
        ['Phase 2 · Sprint Delivery (Agents 7-11)', artifacts.filter((a) => PHASE2.has(a.type))]]
        .map(([label, group]) => group.length === 0 ? null : (
        <div key={label} className="space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</p>
          <div className="flex flex-wrap gap-1.5">
            {group.map((a) => (
              <button key={a.id} onClick={() => open(a)}
                className={cn('rounded-lg border px-3 py-1.5 text-[11.5px] font-semibold transition-colors',
                  active?.id === a.id ? 'border-brand bg-brand text-brand-fg'
                    : 'border-line bg-surface text-muted hover:border-brand hover:text-brand')}>
                {a.type.replaceAll('_', ' ')}
                <span className="ml-1.5 font-mono opacity-70">v{a.current_version}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
      {!artifacts.some((a) => PHASE2.has(a.type)) && (
        <div className="rounded-xl border border-line bg-bg/40 px-3.5 py-2.5 text-[12px] text-muted">
          Phase 2 (Agents 7-11 — backlog, grooming, code review, QE, release) hasn't run for this
          project yet. Use <button className="font-semibold text-brand underline" onClick={() => nav('/sprint-delivery')}>Sprint Delivery</button> to start it, then its artifacts appear here.
        </div>
      )}

      {version && (
        <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
          <Card className="h-fit lg:sticky lg:top-24">
            <CardHeader><CardTitle>Contents</CardTitle></CardHeader>
            <CardBody className="space-y-0.5 max-h-[60vh] overflow-y-auto">
              {headings.length === 0 && <p className="text-[11.5px] text-muted">No sections.</p>}
              {headings.map((h) => (
                <a key={h.id} href={`#${h.id}`}
                  className={cn('block rounded-md px-2 py-1 text-[11.5px] text-muted hover:bg-bg hover:text-brand transition-colors',
                    h.level === 3 && 'pl-4 text-[11px]')}>
                  {h.text}
                </a>
              ))}
            </CardBody>
          </Card>

          <Card>
            <CardHeader className="flex-wrap gap-2">
              <Badge tone={version.approved ? 'success' : 'warning'}>
                {version.approved ? 'APPROVED' : 'PENDING APPROVAL'}
              </Badge>
              <Badge tone="outline">{version.produced_by}</Badge>
              <Badge tone="outline">{version.model}</Badge>
              <span className="text-[11px] text-muted hidden md:inline">{fmtDateTime(version.created_at)}</span>

              <div className="ml-auto flex items-center gap-1.5">
                {active.versions.map((v) => (
                  <button key={v.id} onClick={() => open(active, v.id)}
                    className={cn('rounded-md px-1.5 py-0.5 font-mono text-[11px] transition-colors',
                      v.id === version.id ? 'bg-brand text-brand-fg' : 'text-muted hover:bg-bg')}>
                    v{v.version}
                  </button>
                ))}
                {active.versions.length > 1 && (
                  <Button variant="ghost" size="sm" onClick={() => setShowDiff((s) => !s)}>
                    <GitCompare className="h-3.5 w-3.5" /> {showDiff ? 'Document' : 'Compare'}
                  </Button>
                )}
                <a href={api.exportUrl(version.id, 'docx')} target="_blank" rel="noreferrer">
                  <Button variant="ghost" size="sm">Word</Button>
                </a>
                <a href={api.exportUrl(version.id, 'pdf')} target="_blank" rel="noreferrer">
                  <Button variant="ghost" size="sm">PDF</Button>
                </a>
              </div>
            </CardHeader>

            <CardBody>
              {version.change_summary && (
                <p className="mb-4 rounded-lg border-l-2 border-brand bg-brand-soft px-3 py-2 text-[12px] text-brand">
                  {version.change_summary}
                </p>
              )}
              {active.type === 'WIREFRAME' && !showDiff && (
                <div className="mb-6">
                  <Wireframes payload={version.payload} />
                </div>
              )}
              {showDiff && diff ? (
                <pre className="overflow-x-auto rounded-xl bg-ink p-4 font-mono text-[11.5px] leading-relaxed text-bg">
                  {diff.diff}
                </pre>
              ) : (
                <div className="prose-doc max-w-none" dangerouslySetInnerHTML={{ __html: mdToHtml(version.rendered_md) }} />
              )}
            </CardBody>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader><FileCheck2 className="h-4 w-4 text-brand" /><CardTitle>Downstream actions</CardTitle></CardHeader>
        <CardBody className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => notWired('Regenerate')}>Regenerate</Button>
          <Button variant="secondary" onClick={() => notWired('Send for review')}>
            <Send className="h-3.5 w-3.5" /> Send for review
          </Button>
          <Button variant="secondary" onClick={() => notWired('Publish to Confluence')}>Publish</Button>
          <Button variant="secondary" onClick={() => notWired('Create Jira stories')}>
            Create Jira stories
            <Badge tone="success" className="ml-1">Agent 6 already does this</Badge>
          </Button>
          <Button variant="secondary" onClick={() => notWired('Generate test cases')}>Generate test cases</Button>
          <Button variant="secondary" onClick={() => notWired('Generate FSD')}>Generate FSD</Button>
          <Button variant="secondary" onClick={() => notWired('Generate technical design')}>Technical design</Button>
        </CardBody>
      </Card>

      <div className="pb-2">
        <Button variant="secondary" onClick={onBack}>← Back to Review</Button>
      </div>
    </div>
  )
}
