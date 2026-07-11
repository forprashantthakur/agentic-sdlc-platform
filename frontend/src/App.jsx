import { useEffect, useRef, useState } from 'react'
import { api } from './lib/api'
import AgentPipeline from './components/AgentPipeline'
import RunTimeline from './components/RunTimeline'
import ArtifactViewer from './components/ArtifactViewer'
import ApprovalInbox from './components/ApprovalInbox'

export default function App() {
  const [health, setHealth] = useState(null)
  const [projects, setProjects] = useState([])
  const [project, setProject] = useState(null)
  const [sources, setSources] = useState([])
  const [run, setRun] = useState(null)
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState(null)
  const [approvers, setApprovers] = useState('compliance@hdfcbank.com')
  const [velocity, setVelocity] = useState(15)
  const [refreshKey, setRefreshKey] = useState(0)
  const closeStream = useRef(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
    api.projects().then(setProjects)
  }, [])

  useEffect(() => {
    if (!project) return
    api.sources(project.id).then(setSources)
    api.runs(project.id).then((rs) => rs[0] && attach(rs[0]))
  }, [project])

  const attach = async (r) => {
    setRun(r)
    setStatus(r.status)
    setEvents(await api.events(r.id))
    closeStream.current?.()
    closeStream.current = api.stream(r.id, (e) => {
      if (e.terminal) { setStatus(e.status); setRefreshKey((k) => k + 1); return }
      setEvents((prev) => (prev.find((p) => p.id === e.id) ? prev : [...prev, e]))
      setStatus(e.status)
      setRefreshKey((k) => k + 1)
    })
  }

  const seed = async () => {
    const p = await api.seedProject()
    setProjects(await api.projects())
    setProject(p)
  }

  const start = async () => {
    const r = await api.startRun({
      project_id: project.id,
      approvers: approvers.split(',').map((s) => s.trim()).filter(Boolean),
      velocity: Number(velocity),
      base_url: window.location.origin,
    })
    setEvents([])
    attach(r)
  }

  const live = health?.integrations
  return (
    <>
      <header className="top">
        <div>
          <div className="brand">HDFC BANK · AGENTIC SDLC PLATFORM</div>
          <div className="sub">Requirement Gathering &amp; Documentation · Gemini 2.5 Pro · 6 agents · 2 approval gates</div>
        </div>
        <div className="spacer" />
        {live && (
          <>
            <span className="pill">LLM {live.llm}</span>
            <span className="pill">Figma {live.figma}</span>
            <span className="pill">Gmail {live.gmail}</span>
            <span className="pill">Jira {live.jira}</span>
          </>
        )}
      </header>

      <div className="layout">
        {/* ── left: project + controls + pipeline ─────────────────────────── */}
        <div>
          <div className="panel">
            <h2>Project</h2>
            <div className="body">
              <select
                value={project?.id || ''}
                onChange={(e) => setProject(projects.find((p) => p.id === e.target.value))}
              >
                <option value="">Select a project…</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>

              {!projects.length && (
                <button className="secondary" style={{ marginTop: 10, width: '100%' }} onClick={seed}>
                  Load demo project (UPI AutoPay)
                </button>
              )}

              {project && (
                <>
                  <div className="small muted" style={{ margin: '10px 0' }}>{project.description}</div>
                  <div className="small muted" style={{ marginBottom: 6 }}>Evidence base</div>
                  {sources.map((s) => (
                    <div key={s.id} className="row small" style={{ padding: '3px 0' }}>
                      <span className="chip">{s.kind.replaceAll('_', ' ')}</span>
                      <span className="muted" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.title}
                      </span>
                    </div>
                  ))}

                  <label>Approvers (comma separated)</label>
                  <input value={approvers} onChange={(e) => setApprovers(e.target.value)} />
                  <label>Sprint velocity (points)</label>
                  <input type="number" value={velocity} onChange={(e) => setVelocity(e.target.value)} />

                  <button
                    style={{ width: '100%', marginTop: 14 }}
                    disabled={status === 'RUNNING' || status === 'WAITING_APPROVAL'}
                    onClick={start}
                  >
                    {status === 'RUNNING' ? 'Running…' : 'Start SDLC run'}
                  </button>
                </>
              )}
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <AgentPipeline events={events} status={status} />
          </div>
        </div>

        {/* ── centre: artifacts + timeline ────────────────────────────────── */}
        <div>
          <ArtifactViewer projectId={project?.id} refreshKey={refreshKey} />
          <RunTimeline events={events} status={status} />
        </div>

        {/* ── right: human-in-the-loop ────────────────────────────────────── */}
        <div>
          <ApprovalInbox
            projectId={project?.id}
            refreshKey={refreshKey}
            onDecided={() => setRefreshKey((k) => k + 1)}
          />
        </div>
      </div>
    </>
  )
}
