import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

/**
 * The page an approver lands on from the email button.
 *
 * This is what makes "decide from your inbox" real: the Approve / Request-changes buttons in the
 * approval email link here with a signed token in the URL. No login — the token IS the authority,
 * and it is single-gate and expiring. APPROVED records with one click; CHANGES_REQUESTED asks for a
 * comment first, because "no" without a reason just sends the agent round the loop blind.
 */
export default function Approve() {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token') || ''
  const initial = (params.get('decision') || 'APPROVED').toUpperCase()

  const [decision] = useState(initial)
  const [comment, setComment] = useState('')
  const [state, setState] = useState(initial === 'APPROVED' ? 'confirm' : 'comment')
  // states: confirm (approve, one click) · comment (changes, needs a note) · sending · done · error
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const isApprove = decision === 'APPROVED'

  const submit = async () => {
    setState('sending')
    try {
      const body = {
        decision,
        comments: comment.trim()
          ? [{ author: 'email-approver', body: comment.trim() }]
          : [],
      }
      const r = await api.decideByToken(token, body)
      setResult(r)
      setState('done')
    } catch (e) {
      setError(e.message || 'Could not record the decision.')
      setState('error')
    }
  }

  // Approve is genuinely one-click: auto-submit on load, but leave a visible confirm as a fallback
  // if the auto-submit is blocked.
  useEffect(() => {
    if (state === 'confirm' && token) submit()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const shell = (children) => (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#F4F5F6', fontFamily: 'Inter, Segoe UI, Arial, sans-serif' }}>
      <div style={{ width: 480, maxWidth: '92vw', background: '#fff', borderRadius: 12, boxShadow: '0 8px 30px rgba(0,0,0,.08)', overflow: 'hidden' }}>
        <div style={{ background: '#004C8F', color: '#fff', padding: '16px 22px' }}>
          <div style={{ fontSize: 11, letterSpacing: '.12em', opacity: 0.85 }}>HDFC BANK · AGENTIC SDLC PLATFORM</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>Approval decision</div>
        </div>
        <div style={{ padding: 24 }}>{children}</div>
      </div>
    </div>
  )

  if (!token) {
    return shell(
      <div style={{ textAlign: 'center', color: '#9B2C2C' }}>
        <XCircle size={40} style={{ margin: '0 auto 12px' }} />
        <p style={{ fontWeight: 600 }}>This link is missing its approval token.</p>
        <p style={{ fontSize: 13, color: '#63666A' }}>Open the Approve button directly from the email you were sent.</p>
      </div>
    )
  }

  if (state === 'sending') {
    return shell(
      <div style={{ textAlign: 'center', color: '#004C8F' }}>
        <Loader2 size={38} style={{ margin: '0 auto 12px', animation: 'spin 1s linear infinite' }} />
        <p style={{ fontWeight: 600 }}>Recording your decision…</p>
        <style>{'@keyframes spin{to{transform:rotate(360deg)}}'}</style>
      </div>
    )
  }

  if (state === 'done') {
    const resumed = result?.status === 'RESUMED'
    const waiting = result?.status === 'WAITING_FOR_OTHER_APPROVERS'
    return shell(
      <div style={{ textAlign: 'center' }}>
        <CheckCircle2 size={44} color={isApprove ? '#16A34A' : '#E8A33D'} style={{ margin: '0 auto 14px' }} />
        <p style={{ fontSize: 18, fontWeight: 700, color: '#1A1A1A' }}>
          {isApprove ? 'Approved' : 'Changes requested'}
        </p>
        <p style={{ fontSize: 13.5, color: '#63666A', marginTop: 8, lineHeight: 1.5 }}>
          {resumed && isApprove && 'Your approval is recorded and the pipeline has resumed. You can close this tab.'}
          {resumed && !isApprove && 'Recorded. The agent will revise the artifact against your comments and come back for another look.'}
          {waiting && 'Recorded. This gate has more than one approver — it will proceed once the others decide.'}
          {!resumed && !waiting && 'Your decision has been recorded. You can close this tab.'}
        </p>
      </div>
    )
  }

  if (state === 'error') {
    return shell(
      <div style={{ textAlign: 'center', color: '#9B2C2C' }}>
        <XCircle size={40} style={{ margin: '0 auto 12px' }} />
        <p style={{ fontWeight: 600 }}>We could not record that decision.</p>
        <p style={{ fontSize: 13, color: '#63666A', marginTop: 6 }}>{error}</p>
        <p style={{ fontSize: 12, color: '#9AA3AB', marginTop: 10 }}>
          The link may have expired, or this gate may already have been decided.
        </p>
      </div>
    )
  }

  // state === 'comment'  → request changes needs a reason
  return shell(
    <div>
      <p style={{ fontSize: 14, color: '#1A1A1A', fontWeight: 600 }}>Request changes</p>
      <p style={{ fontSize: 13, color: '#63666A', margin: '8px 0 14px', lineHeight: 1.5 }}>
        Tell the agent what to fix. Your note is recorded against this gate and drives the revision —
        so be specific.
      </p>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="e.g. The NFR section is missing latency targets; add the 2-second quote SLA from the email."
        style={{ width: '100%', minHeight: 120, padding: 12, borderRadius: 8, border: '1px solid #DBE3ED', fontSize: 13, fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box' }}
      />
      <button
        onClick={submit}
        disabled={!comment.trim()}
        style={{
          marginTop: 14, width: '100%', padding: '12px 0', borderRadius: 8, border: 0,
          background: comment.trim() ? '#ED232A' : '#E4E6E8', color: '#fff', fontSize: 14,
          fontWeight: 600, cursor: comment.trim() ? 'pointer' : 'not-allowed',
        }}
      >
        Submit — request changes
      </button>
    </div>
  )
}
