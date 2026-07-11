export default function RunTimeline({ events, status }) {
  const cls = { COMPLETED: 'ok', FAILED: 'err', REJECTED: 'err', WAITING_APPROVAL: 'warn' }[status] || ''
  return (
    <div className="panel" style={{ marginTop: 16 }}>
      <h2>
        Run timeline <span className={`chip ${cls}`} style={{ marginLeft: 8 }}>{status || 'IDLE'}</span>
      </h2>
      <div className="body timeline">
        {events.length === 0 && <div className="empty">No run yet. Start one to watch the agents work.</div>}
        {events.map((e) => (
          <div className="ev" key={e.id}>
            <div className="node">{e.node}</div>
            <div className="msg">{e.message}</div>
            {e.data?.external?.jira?.length > 0 && (
              <div className="small muted">
                Jira: {e.data.external.jira.map((i) => i.key).join(', ')}
              </div>
            )}
            {e.data?.external?.figma?.file_url && (
              <a className="small" href={e.data.external.figma.file_url} target="_blank" rel="noreferrer">
                Open Figma file
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
