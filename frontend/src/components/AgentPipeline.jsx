const AGENTS = [
  { node: 'ingest', label: 'Ingest & Index', desc: 'Sources → long-term memory (RAG)' },
  { node: 'agent1_requirements', label: 'Agent 1 · Requirement Gathering', desc: 'Notes, emails, transcript → structured requirements' },
  { node: 'agent2_concept_note', label: 'Agent 2 · Concept Note', desc: 'Objectives, scope, rules, risks' },
  { node: 'request_concept_approval', label: 'Gate 1 · Approval', desc: 'Human sign-off — Agent 5', gate: true },
  { node: 'agent3_wireframe', label: 'Agent 3 · Wireframes', desc: 'Screen spec → Figma via MCP' },
  { node: 'agent4_requirement_docs', label: 'Agent 4 · Requirement Docs', desc: 'BRD · FRD · SRS · Stories · APIs · NFRs' },
  { node: 'request_docs_approval', label: 'Gate 2 · Approval', desc: 'Human sign-off — Agent 5', gate: true },
  { node: 'agent6_sprint', label: 'Agent 6 · Sprint Plan', desc: 'Epics, stories, points → Jira' },
]

export default function AgentPipeline({ events, status }) {
  const seen = new Set(events.map((e) => e.node))
  const last = events.length ? events[events.length - 1].node : null

  const stateOf = (node) => {
    if (!seen.has(node)) return ''
    if (node === last && status === 'WAITING_APPROVAL') return 'wait'
    if (node === last && status === 'RUNNING') return 'run'
    if (node === last && status === 'FAILED') return 'err'
    return 'done'
  }

  return (
    <div className="panel">
      <h2>Agent pipeline</h2>
      <div className="body">
        <ul className="agent-list">
          {AGENTS.map((a) => (
            <li key={a.node}>
              <span className={`dot ${stateOf(a.node)}`} />
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>
                  {a.label} {a.gate && <span className="chip warn">HITL</span>}
                </div>
                <div className="small muted">{a.desc}</div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
