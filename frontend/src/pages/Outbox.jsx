import { AlertCircle, Mail, RefreshCw, Send, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Empty } from '../components/ui'
import { cn } from '../lib/utils'

/**
 * Approval Outbox — the answer to "how do we demo the email trigger?".
 *
 * When a run hits an approval gate, the platform triggers an email to the approver. In mock mode it
 * is captured, not delivered; with SMTP/Gmail configured it is really sent. Either way the exact
 * message is shown here, rendered as the approver sees it, with its one-click buttons live — so on
 * stage you open this and say "here is the email the CIO just received," then click Approve.
 */
export default function Outbox() {
  const [data, setData] = useState(null)
  const [sel, setSel] = useState(0)
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    try {
      const d = await api.get('/api/integrations/outbox')
      setData(d)
      setErr('')
    } catch (e) {
      setErr(e.message)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)   // refresh so a new gate email appears without a manual poke
    return () => clearInterval(t)
  }, [load])

  const clear = async () => {
    await api.post('/api/integrations/outbox/clear').catch(() => {})
    setSel(0)
    load()
  }

  const items = data?.items ?? []
  const live = data?.live_delivery

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Approval Outbox</h1>
          <p className="mt-1 text-[13px] text-muted">
            Every email the platform has triggered to an approver. When a run reaches a gate, the
            message appears here — rendered exactly as the approver receives it, with working buttons.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={load}>
            <RefreshCw className="mr-1.5 h-4 w-4" />Refresh
          </Button>
          {items.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clear}>
              <Trash2 className="mr-1.5 h-4 w-4" />Clear
            </Button>
          )}
        </div>
      </div>

      {/* delivery-mode banner: never let the demo imply a real send when it was captured-only */}
      <div className={cn('flex items-center gap-2.5 rounded-xl border px-3.5 py-2.5 text-[12.5px]',
        live ? 'border-success/30 bg-success/5 text-success' : 'border-warning/30 bg-warning/10 text-warning')}>
        {live ? <Send className="h-4 w-4 shrink-0" /> : <AlertCircle className="h-4 w-4 shrink-0" />}
        <span>
          {live
            ? 'Live delivery is ON — these emails are actually sent to the approver’s inbox, and also shown here.'
            : 'Offline demo mode — emails are captured and shown here, not delivered. Set SMTP credentials on the server to send for real.'}
        </span>
      </div>

      {err ? (
        <Empty icon={AlertCircle} title="Outbox unavailable" hint={err} />
      ) : items.length === 0 ? (
        <Empty
          icon={Mail}
          title="No emails triggered yet"
          hint="Start a run and approve nothing — when it reaches the Concept Note gate, the approval email lands here."
        />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          {/* list */}
          <div className="space-y-2">
            {items.map((m, i) => (
              <button
                key={m.message_id}
                onClick={() => setSel(i)}
                className={cn('w-full rounded-xl border p-3 text-left transition-colors',
                  i === sel ? 'border-brand bg-brand-soft' : 'border-line bg-surface hover:bg-bg')}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[12px] font-semibold text-ink">{m.to.join(', ')}</span>
                  <Badge tone={m.error ? 'danger' : m.delivery === 'mock' ? 'warning' : 'success'}>
                    {m.error ? 'send failed' : m.delivery === 'mock' ? 'captured' : m.delivery}
                  </Badge>
                </div>
                <p className="mt-1 line-clamp-2 text-[11.5px] text-muted">{m.subject}</p>
                <p className="mt-1 text-[10.5px] text-muted/80">{new Date(m.sent_at).toLocaleString()}</p>
              </button>
            ))}
          </div>

          {/* rendered email */}
          <Card>
            <CardHeader>
              <Mail className="h-4 w-4 text-brand" />
              <CardTitle>As the approver sees it</CardTitle>
              {items[sel]?.error && <Badge tone="danger" className="ml-auto">{items[sel].error}</Badge>}
            </CardHeader>
            <CardBody>
              <div className="mb-3 space-y-0.5 text-[12px]">
                <div><span className="text-muted">To:</span> <span className="font-medium">{items[sel]?.to.join(', ')}</span></div>
                <div><span className="text-muted">Subject:</span> <span className="font-medium">{items[sel]?.subject}</span></div>
              </div>
              {/* srcdoc iframe renders the email HTML faithfully and sandboxed; the Approve /
                  Request-changes links inside are real and open the decision page. */}
              <iframe
                title="approval-email"
                srcDoc={items[sel]?.html}
                sandbox="allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
                className="h-[560px] w-full rounded-lg border border-line bg-white"
              />
              <p className="mt-2 text-[11px] text-muted">
                The buttons above are live — clicking Approve records the decision through the same
                secure one-time link the approver would use from their inbox.
              </p>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  )
}
