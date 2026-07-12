import { motion } from 'framer-motion'
import {
  Activity, Bot, CheckCircle2, Clock, FilePlus2, FileStack, FolderKanban, Layers, ShieldQuestion, Sparkles, TrendingUp,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { cn, fmtDate } from '../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Confidence, Empty, Skeleton } from '../components/ui'

const STATUS_TONE = {
  COMPLETED: 'success', 'AWAITING APPROVAL': 'warning', 'IN PROGRESS': 'brand',
  FAILED: 'danger', REJECTED: 'danger', DRAFT: 'default',
}

export default function Dashboard({ setProject, onSeed }) {
  const nav = useNavigate()
  const [stats, setStats] = useState(null)
  const [projects, setProjects] = useState([])
  const [queue, setQueue] = useState([])

  useEffect(() => {
    api.stats().then(setStats).catch(() => {})
    api.projects().then(setProjects).catch(() => {})
    api.queue().then(setQueue).catch(() => {})
  }, [])

  const metrics = [
    { label: 'Projects', value: stats?.projects, icon: FolderKanban, hint: 'Across all business units' },
    { label: 'Requirements extracted', value: stats?.requirements_extracted, icon: Layers, hint: 'Every one cited to a source' },
    { label: 'Documents processed', value: stats?.documents_processed, icon: FileStack, hint: 'Notes, emails, transcripts, uploads' },
    { label: 'Artifacts generated', value: stats?.artifacts_generated, icon: Sparkles, hint: 'Versioned and attributed' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-[13px] text-muted mt-1">Requirement gathering and documentation, across the bank.</p>
        </div>
        <div className="flex gap-2">
          {projects.length === 0 && <Button variant="secondary" onClick={onSeed}>Load demo project</Button>}
          <Button onClick={() => nav('/new')}><FilePlus2 className="h-3.5 w-3.5" /> New BRD</Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((m, i) => {
          const Icon = m.icon
          return (
            <motion.div key={m.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card hover>
                <CardBody>
                  <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-soft">
                    <Icon className="h-[18px] w-[18px] text-brand" />
                  </div>
                  <div className="mt-3">
                    {stats ? <div className="font-mono text-2xl font-semibold tabular-nums">{m.value ?? 0}</div>
                      : <Skeleton className="h-8 w-16" />}
                    <div className="text-[12px] font-medium mt-0.5">{m.label}</div>
                    <div className="text-[10.5px] text-muted mt-0.5">{m.hint}</div>
                  </div>
                </CardBody>
              </Card>
            </motion.div>
          )
        })}
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <FolderKanban className="h-4 w-4 text-brand" />
            <CardTitle>Recent projects</CardTitle>
            <Button variant="ghost" size="sm" className="ml-auto" onClick={() => nav('/projects')}>View all</Button>
          </CardHeader>
          <CardBody className={projects.length ? 'p-0' : ''}>
            {projects.length === 0 ? (
              <Empty icon={FolderKanban} title="No projects yet"
                hint="Start a new BRD, or load the demo project to watch all six agents run end to end."
                action={<Button onClick={onSeed}>Load demo project</Button>} />
            ) : (
              <ul className="divide-y divide-line">
                {projects.slice(0, 6).map((p) => (
                  <li key={p.id}>
                    <button onClick={() => { setProject(p); nav('/new') }}
                      className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-bg transition-colors">
                      <div className="min-w-0 flex-1">
                        <div className="text-[13px] font-medium truncate">{p.name}</div>
                        <div className="text-[11px] text-muted truncate">
                          {p.business_unit} · {p.source_count} sources · {p.artifact_count} artifacts · {fmtDate(p.created_at)}
                        </div>
                      </div>
                      <Badge tone={STATUS_TONE[p.status] || 'default'}>{p.status}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader><TrendingUp className="h-4 w-4 text-brand" /><CardTitle>Extraction confidence</CardTitle></CardHeader>
            <CardBody>
              {stats?.mean_confidence != null ? (
                <>
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-3xl font-semibold tabular-nums">
                      {Math.round(stats.mean_confidence * 100)}%
                    </span>
                    <Confidence value={stats.mean_confidence} />
                  </div>
                  <p className="mt-2 text-[11.5px] text-muted leading-snug">
                    The model's own confidence across every extracted requirement — not a marketing metric.
                    Treat anything under 80% as needing human confirmation.
                  </p>
                </>
              ) : <p className="text-[12px] text-muted">No extractions yet.</p>}
            </CardBody>
          </Card>

          <Card>
            <CardHeader><ShieldQuestion className="h-4 w-4 text-warning" /><CardTitle>Pending reviews</CardTitle></CardHeader>
            <CardBody>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-3xl font-semibold tabular-nums">{stats?.pending_reviews ?? 0}</span>
                <span className="text-[12px] text-muted">awaiting sign-off</span>
              </div>
              <Button variant="soft" size="sm" className="mt-3 w-full" onClick={() => nav('/review')}>
                Open Review Center
              </Button>
            </CardBody>
          </Card>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><Bot className="h-4 w-4 text-brand" /><CardTitle>Agent status</CardTitle>
            <Badge tone="success" className="ml-auto">All ready</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            {(stats?.agents ?? []).map((a) => (
              <div key={a.id} className="flex items-center gap-3 rounded-lg border border-line bg-bg/50 px-3 py-2">
                <span className="h-1.5 w-1.5 rounded-full bg-success shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-[12.5px] font-medium truncate">{a.name}</div>
                  <div className="text-[10.5px] text-muted truncate">{a.description}</div>
                </div>
                <Badge tone="outline">{a.status}</Badge>
              </div>
            ))}
            {!stats && [1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}
          </CardBody>
        </Card>

        <Card>
          <CardHeader><Activity className="h-4 w-4 text-brand" /><CardTitle>Processing queue</CardTitle></CardHeader>
          <CardBody className={queue.length ? 'space-y-2' : ''}>
            {queue.length === 0 ? (
              <Empty icon={CheckCircle2} title="Queue is clear" hint="No runs in flight." />
            ) : queue.map((q) => (
              <div key={q.run_id} className="flex items-center gap-3 rounded-lg border border-line px-3 py-2">
                <Clock className={cn('h-3.5 w-3.5 shrink-0',
                  q.status === 'WAITING_APPROVAL' ? 'text-warning' : 'text-brand animate-pulse')} />
                <div className="min-w-0 flex-1">
                  <div className="text-[12.5px] font-medium truncate">{q.project}</div>
                  <code className="text-[10.5px] text-muted font-mono">{q.node || '—'}</code>
                </div>
                <Badge tone={q.status === 'WAITING_APPROVAL' ? 'warning' : 'brand'}>
                  {q.status.replaceAll('_', ' ')}
                </Badge>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
