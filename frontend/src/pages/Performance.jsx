import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, CircleDollarSign, Cpu, Gauge, RefreshCw, ShieldAlert, Timer, Zap,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Empty } from '../components/ui'
import { cn } from '../lib/utils'

const ms = (v) => (v == null ? '—' : v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(1)} s`)
const num = (v) => (v == null ? '—' : v.toLocaleString('en-IN'))
const inr = (v) => (v == null ? '—' : `₹${v.toFixed(2)}`)
const pct = (v) => `${(v * 100).toFixed(1)}%`

const AGENT_LABEL = {
  ingest: 'Ingestion',
  agent1_requirements: 'A1 · Requirements',
  agent2_concept_note: 'A2 · Concept Note',
  agent3_wireframe: 'A3 · Wireframes',
  agent4_requirement_docs: 'A4 · Requirement Docs',
  agent5_approval: 'A5 · Approval',
  agent6_sprint: 'A6 · Sprint Plan',
  request_concept_approval: 'Gate 1 · Concept',
  request_docs_approval: 'Gate 2 · Documents',
  finalise: 'Finalise',
}

function Stat({ icon: Icon, label, value, sub, tone = 'default' }) {
  return (
    <Card>
      <CardBody className="flex items-start gap-3 py-4">
        <div
          className={cn(
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
            tone === 'warn' ? 'bg-warning/10 text-warning' : 'bg-brand-soft text-brand',
          )}
        >
          <Icon className="h-[18px] w-[18px]" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
          <div className="mt-0.5 truncate text-xl font-semibold tabular-nums">{value}</div>
          {sub ? <div className="mt-0.5 text-xs text-muted">{sub}</div> : null}
        </div>
      </CardBody>
    </Card>
  )
}

/** A latency bar scaled against the slowest row, so the eye finds the bottleneck before the brain
 *  reads the number. p95 is drawn as a notch on the same bar — mean alone hides the tail, and the
 *  tail is what the user actually waits for. */
function LatencyRow({ label, s, max }) {
  const w = max > 0 ? Math.max((s.mean_ms / max) * 100, 1.5) : 0
  const p95 = max > 0 ? Math.min((s.p95_ms / max) * 100, 100) : 0
  return (
    <div className="grid grid-cols-[minmax(150px,1.1fr)_2fr_auto] items-center gap-3 py-1.5">
      <div className="truncate text-sm">{label}</div>
      <div className="relative h-2 rounded-full bg-line">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-brand"
          initial={{ width: 0 }}
          animate={{ width: `${w}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
        {s.p95_ms > s.mean_ms ? (
          <div
            className="absolute inset-y-[-2px] w-0.5 rounded bg-warning"
            style={{ left: `${p95}%` }}
            title={`p95 ${ms(s.p95_ms)}`}
          />
        ) : null}
      </div>
      <div className="text-right text-xs tabular-nums text-muted">
        <span className="font-medium text-ink">{ms(s.mean_ms)}</span>
        <span className="ml-2">p95 {ms(s.p95_ms)}</span>
        <span className="ml-2">×{s.calls}</span>
      </div>
    </div>
  )
}

export default function Performance() {
  const [m, setM] = useState(null)
  const [err, setErr] = useState(null)
  const [live, setLive] = useState(true)

  const load = useCallback(async () => {
    try {
      setM(await api.get('/api/metrics'))
      setErr(null)
    } catch (e) {
      setErr(e.message)
    }
  }, [])

  useEffect(() => {
    load()
    if (!live) return undefined
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [load, live])

  if (err) return <Empty icon={AlertTriangle} title="Telemetry unavailable" hint={err} />
  if (!m) return <div className="py-14 text-center text-sm text-muted">Reading telemetry…</div>

  const t = m.totals
  const agents = Object.entries(m.by_agent).sort((a, b) => b[1].mean_ms - a[1].mean_ms)
  const models = Object.entries(m.by_model).sort((a, b) => b[1].calls - a[1].calls)
  const maxAgent = Math.max(...agents.map(([, s]) => s.mean_ms), 0)
  const maxModel = Math.max(...models.map(([, s]) => s.mean_ms), 0)
  const rag = m.by_stage.rag
  const pipe = m.by_stage.pipeline
  const breakers = Object.entries(m.circuit_breakers || {})
  const tripped = breakers.filter(([, b]) => b.state !== 'closed')
  const hitRate = t.llm_calls + t.cache_hits > 0 ? t.cache_hits / (t.llm_calls + t.cache_hits) : 0

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Performance</h1>
          <p className="mt-0.5 text-sm text-muted">
            Measured in-process, not modelled. Uptime {Math.round(m.uptime_s / 60)} min · peak
            concurrency {m.peak_concurrency}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={live ? 'secondary' : 'ghost'} size="sm" onClick={() => setLive((v) => !v)}>
            <Activity className={cn('mr-1.5 h-4 w-4', live && 'text-success')} />
            {live ? 'Live' : 'Paused'}
          </Button>
          <Button variant="ghost" size="sm" onClick={load}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {tripped.length > 0 ? (
        <Card className="border-warning/30 bg-warning/5">
          <CardBody className="flex items-center gap-3 py-3">
            <ShieldAlert className="h-5 w-5 shrink-0 text-warning" />
            <div className="text-sm">
              <span className="font-medium">Circuit breaker engaged.</span>{' '}
              {tripped.map(([k, b]) => `${k} is ${b.state}`).join(' · ')}. Traffic is being routed to
              the fallback chain — runs continue, on a different model.
            </div>
          </CardBody>
        </Card>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Timer}
          label="Pipeline p95"
          value={ms(pipe?.p95_ms)}
          sub={`mean ${ms(pipe?.mean_ms)} · ${pipe?.calls ?? 0} node runs`}
        />
        <Stat
          icon={Zap}
          label="Model calls"
          value={num(t.llm_calls)}
          sub={`${num(t.tokens_in)} in · ${num(t.tokens_out)} out`}
        />
        <Stat
          icon={RefreshCw}
          label="Retry rate"
          value={pct(t.retry_rate)}
          tone={t.retry_rate > 0.2 ? 'warn' : 'default'}
          sub={`${num(t.retries)} retries`}
        />
        <Stat icon={CircleDollarSign} label="Spend" value={inr(t.cost_inr)} sub="this process" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-brand" />
              Where the time goes
            </CardTitle>
            <p className="text-xs text-muted mt-0.5">Mean per node, with the p95 notch. The longest bar is your bottleneck.</p>
          </CardHeader>
          <CardBody className="pt-1">
            {agents.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">
                No runs yet. Generate a BRD and this fills in.
              </p>
            ) : (
              agents.map(([k, s]) => (
                <LatencyRow key={k} label={AGENT_LABEL[k] ?? k} s={s} max={maxAgent} />
              ))
            )}
          </CardBody>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-brand" />
              By model
            </CardTitle>
            <p className="text-xs text-muted mt-0.5">Routing, latency and spend per model.</p>
          </CardHeader>
            <CardBody className="pt-1">
              {models.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted">No model calls recorded.</p>
              ) : (
                models.map(([k, s]) => (
                  <div key={k} className="border-b border-line py-2 last:border-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-xs">{k}</span>
                      {s.errors > 0 ? (
                        <Badge tone="warning">{s.errors} err</Badge>
                      ) : (
                        <Badge tone="success">healthy</Badge>
                      )}
                    </div>
                    <div className="mt-1 flex justify-between text-xs tabular-nums text-muted">
                      <span>
                        {s.calls} calls · {ms(s.mean_ms)} · p95 {ms(s.p95_ms)}
                      </span>
                      <span>{inr(s.cost_inr)}</span>
                    </div>
                    <div className="mt-1.5 h-1.5 rounded-full bg-line">
                      <div
                        className="h-full rounded-full bg-brand/70"
                        style={{ width: `${maxModel ? (s.mean_ms / maxModel) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                ))
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-brand" />
              Retrieval & cache
            </CardTitle>
          </CardHeader>
            <CardBody className="space-y-2 pt-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted">RAG lookups</span>
                <span className="tabular-nums">
                  {rag?.calls ?? 0} · {ms(rag?.mean_ms)} mean
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Retrieval reused in-run</span>
                <span className="tabular-nums">{num(rag?.cache_hits ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Response cache hit rate</span>
                <span className="tabular-nums">{pct(hitRate)}</span>
              </div>
              <p className="pt-1 text-xs leading-relaxed text-muted">
                The response cache keys on the exact prompt, model and schema — never on similarity.
                Two projects that merely <em>look</em> alike must never share a BRD.
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  )
}
