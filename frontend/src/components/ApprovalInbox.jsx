import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const GATE_LABEL = {
  concept_note_gate: 'Concept Note sign-off',
  requirement_docs_gate: 'Requirement Documentation sign-off',
}

export default function ApprovalInbox({ projectId, refreshKey, onDecided }) {
  const [approvals, setApprovals] = useState([])
  const [comment, setComment] = useState({})
  const [busy, setBusy] = useState(null)

  const load = () => projectId && api.approvals(projectId).then(setApprovals)
  useEffect(() => { load() }, [projectId, refreshKey])

  const decide = async (a, decision) => {
    setBusy(a.id)
    const text = (comment[a.id] || '').trim()
    try {
      await api.decide(a.id, {
        decision,
        comments: text
          ? text.split('\n').filter(Boolean).map((body) => ({ author: a.approver_email, body }))
          : [],
      })
      setComment((c) => ({ ...c, [a.id]: '' }))
      await load()
      onDecided?.()
    } catch (e) {
      alert(e.message)
    } finally {
      setBusy(null)
    }
  }

  const pending = approvals.filter((a) => a.status === 'PENDING')
  const decided = approvals.filter((a) => a.status !== 'PENDING')

  return (
    <div className="panel">
      <h2>Approval inbox <span className="chip warn">{pending.length} pending</span></h2>
      <div className="body">
        {pending.length === 0 && <div className="small muted">Nothing awaiting your sign-off.</div>}

        {pending.map((a) => (
          <div className="approval" key={a.id}>
            <div className="gate">{GATE_LABEL[a.gate] || a.gate}</div>
            <div className="meta">
              Round {a.round} · {a.approver_email}
              <br />Expires {new Date(a.expires_at).toLocaleString()}
            </div>
            <label>Comments (one per line — these are fed back to the agent and stored as memory)</label>
            <textarea
              rows={3}
              value={comment[a.id] || ''}
              placeholder="e.g. Retry cap conflict is unresolved — state it explicitly as a risk."
              onChange={(e) => setComment((c) => ({ ...c, [a.id]: e.target.value }))}
            />
            <div className="row" style={{ marginTop: 10 }}>
              <button disabled={busy === a.id} onClick={() => decide(a, 'APPROVED')}>Approve</button>
              <button className="secondary" disabled={busy === a.id} onClick={() => decide(a, 'CHANGES_REQUESTED')}>
                Request changes
              </button>
              <button className="danger" disabled={busy === a.id} onClick={() => decide(a, 'REJECTED')}>Reject</button>
            </div>
          </div>
        ))}

        {decided.length > 0 && (
          <>
            <div className="small muted" style={{ margin: '14px 0 8px' }}>Decision history</div>
            {decided.map((a) => (
              <div className="row small" key={a.id} style={{ padding: '4px 0' }}>
                <span className={`chip ${a.status === 'APPROVED' ? 'ok' : a.status === 'REJECTED' ? 'err' : 'warn'}`}>
                  {a.status}
                </span>
                <span className="muted">{GATE_LABEL[a.gate] || a.gate} · round {a.round}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
