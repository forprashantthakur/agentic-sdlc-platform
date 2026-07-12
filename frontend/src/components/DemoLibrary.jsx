import { AlertTriangle, HelpCircle, Loader2, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { cn } from '../lib/utils'
import { Badge, Button, Dialog, useToast } from './ui'

/**
 * The demo library.
 *
 * Every project here ships with a *deliberately flawed* evidence base — a real conflict between
 * two sources, and a real gap nobody thought to state. That is the point. A seed corpus where
 * every source agrees would make the agents look brilliant and prove nothing; what is worth
 * demonstrating is that Agent 1 escalates the disagreement instead of quietly picking a side.
 *
 * So we show the planted conflict and gap on the card, up front. If a demo is going to be
 * impressive, it should be impressive for the right reason.
 */
export default function DemoLibrary({ open, onClose, onSeeded }) {
  const toast = useToast()
  const [catalog, setCatalog] = useState(null)
  const [busy, setBusy] = useState(null)

  useEffect(() => {
    if (open && !catalog) api.demoCatalog().then(setCatalog).catch(() => setCatalog([]))
  }, [open])

  const seed = async (key, name) => {
    setBusy(key)
    try {
      const p = await api.seedProject(key)
      toast(`${name} loaded`, {
        tone: 'success',
        detail: 'Its sources disagree with each other on purpose. Watch Agent 1 escalate rather than resolve.',
        duration: 6500,
      })
      onSeeded?.(p)
      onClose?.()
    } catch (e) {
      toast('Could not load the project', { tone: 'error', detail: e.message })
    } finally { setBusy(null) }
  }

  const seedAll = async () => {
    setBusy('__all__')
    try {
      const ps = await api.seedAll()
      toast(`${ps.length} projects loaded`, { tone: 'success', detail: 'Five business units, 15 source documents.' })
      onSeeded?.(ps[0])
      onClose?.()
    } catch (e) {
      toast('Could not load the catalogue', { tone: 'error', detail: e.message })
    } finally { setBusy(null) }
  }

  return (
    <Dialog
      open={open} onClose={onClose} wide
      title="Demo library"
      description="Five banking IT projects, each with a realistic — and deliberately contradictory — evidence base."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={seedAll} loading={busy === '__all__'}>Load all five</Button>
        </>
      }
    >
      {!catalog ? (
        <div className="flex items-center justify-center py-10 text-muted">
          <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading catalogue…
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-[12px] text-muted leading-relaxed">
            Each project's sources <strong>disagree with each other</strong>, and each leaves something
            obvious unsaid. That is deliberate: an evidence base where everyone agrees would make the
            agents look clever and prove nothing. What is worth watching is Agent 1 flagging the
            conflict instead of quietly picking a side.
          </p>

          {catalog.map((p) => (
            <div key={p.key}
              className="rounded-xl border border-line bg-surface p-4 hover:border-brand transition-colors">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <h3 className="text-[13.5px] font-semibold">{p.name}</h3>
                    <Badge tone={p.priority === 'Critical' ? 'danger' : 'warning'}>{p.priority}</Badge>
                  </div>
                  <p className="text-[11.5px] text-muted mt-0.5">{p.business_unit}</p>
                  <p className="text-[12px] text-muted mt-1.5 leading-relaxed">{p.description}</p>

                  <div className="mt-2.5 space-y-1.5">
                    <div className="flex gap-2 rounded-lg border border-danger/20 bg-danger/5 px-2.5 py-1.5">
                      <ShieldAlert className="h-3.5 w-3.5 text-danger shrink-0 mt-0.5" />
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-danger">Planted conflict</span>
                        <p className="text-[11.5px] text-ink leading-snug">{p.planted_conflict}</p>
                      </div>
                    </div>
                    <div className="flex gap-2 rounded-lg border border-warning/20 bg-warning/5 px-2.5 py-1.5">
                      <HelpCircle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" />
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-warning">Planted gap</span>
                        <p className="text-[11.5px] text-ink leading-snug">{p.planted_gap}</p>
                      </div>
                    </div>
                  </div>

                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    <span className="text-[10.5px] text-muted">{p.source_count} sources ·</span>
                    {p.regulatory_scope.map((r) => <Badge key={r} tone="brand">{r}</Badge>)}
                  </div>
                </div>

                <Button size="sm" onClick={() => seed(p.key, p.name)} loading={busy === p.key} className="shrink-0">
                  Load
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Dialog>
  )
}
