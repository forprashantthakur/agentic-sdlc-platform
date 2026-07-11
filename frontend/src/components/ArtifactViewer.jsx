import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { mdToHtml } from '../lib/md'

const ORDER = [
  'BUSINESS_REQUIREMENTS', 'CONCEPT_NOTE', 'WIREFRAME', 'BRD', 'FRD', 'SRS',
  'USER_STORIES', 'ACCEPTANCE_CRITERIA', 'API_REQUIREMENTS', 'NFR', 'SPRINT_PLAN',
]

export default function ArtifactViewer({ projectId, refreshKey }) {
  const [artifacts, setArtifacts] = useState([])
  const [active, setActive] = useState(null)
  const [version, setVersion] = useState(null)
  const [diff, setDiff] = useState(null)
  const [showDiff, setShowDiff] = useState(false)

  useEffect(() => {
    if (!projectId) return
    api.artifacts(projectId).then((rows) => {
      const sorted = [...rows].sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type))
      setArtifacts(sorted)
      if (sorted.length && !sorted.find((a) => a.id === active?.id)) setActive(sorted[0])
    })
  }, [projectId, refreshKey])

  const open = async (artifact, versionId) => {
    setActive(artifact)
    setShowDiff(false)
    const vid = versionId || artifact.versions[artifact.versions.length - 1].id
    setVersion(await api.version(vid))
    setDiff(await api.diff(vid).catch(() => null))
  }

  useEffect(() => { if (active && !version) open(active) }, [active])

  if (!artifacts.length) {
    return (
      <div className="panel">
        <h2>Artifacts</h2>
        <div className="empty">Artifacts appear here as the agents produce them.</div>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2>Artifacts &amp; versions</h2>
      <div className="tabs">
        {artifacts.map((a) => (
          <button
            key={a.id}
            className={`tab ${active?.id === a.id ? 'active' : ''}`}
            onClick={() => open(a)}
          >
            {a.type.replaceAll('_', ' ')}<span className="v">v{a.current_version}</span>
          </button>
        ))}
      </div>

      {version && (
        <>
          <div className="row" style={{ padding: '10px 16px', borderBottom: '1px solid var(--line)', flexWrap: 'wrap' }}>
            <span className={`chip ${version.approved ? 'ok' : 'warn'}`}>
              {version.approved ? 'APPROVED' : 'PENDING APPROVAL'}
            </span>
            <span className="chip">{version.produced_by}</span>
            <span className="chip">{version.model}</span>
            {active.versions.map((v) => (
              <button
                key={v.id}
                className="ghost"
                style={{ fontWeight: v.id === version.id ? 700 : 400 }}
                onClick={() => open(active, v.id)}
              >
                v{v.version}
              </button>
            ))}
            <span style={{ flex: 1 }} />
            {version.external_ref && (
              <a className="small" href={version.external_ref} target="_blank" rel="noreferrer">External ↗</a>
            )}
            {active.versions.length > 1 && (
              <button className="secondary" onClick={() => setShowDiff((s) => !s)}>
                {showDiff ? 'View document' : 'View diff'}
              </button>
            )}
          </div>

          <div className="doc">
            {version.change_summary && (
              <div className="small muted" style={{ marginBottom: 12 }}>{version.change_summary}</div>
            )}
            {showDiff && diff ? (
              <pre>{diff.diff}</pre>
            ) : (
              <div dangerouslySetInnerHTML={{ __html: mdToHtml(version.rendered_md) }} />
            )}
          </div>
        </>
      )}
    </div>
  )
}
