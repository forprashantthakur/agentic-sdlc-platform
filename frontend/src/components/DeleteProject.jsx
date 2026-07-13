import { AlertTriangle, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Badge, Button, Dialog, Input, useToast } from './ui'

/**
 * Deleting a project is not deleting a row.
 *
 * It destroys the audit trail: which named human approved which version of which document, produced
 * by which agent, on which model. In a governed process that record IS the product. So this dialog
 * does three things a normal delete confirm does not:
 *
 *   1. It tells you exactly what will be destroyed, fetched from the server — not a guess.
 *   2. It calls out approved versions and recorded decisions separately, because those are the ones
 *      that actually matter.
 *   3. It makes you type the project's name. Not a checkbox — a deliberate act. A one-click delete
 *      next to a project card is a trap, and the person who falls into it will be tired and in a hurry.
 */
export default function DeleteProject({ project, open, onClose, onDeleted }) {
  const toast = useToast()
  const [impact, setImpact] = useState(null)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !project) return
    setTyped('')
    setImpact(null)
    api.deleteImpact(project.id).then(setImpact).catch(() => setImpact(null))
  }, [open, project?.id])

  const armed = typed.trim() === project?.name

  const destroy = async () => {
    setBusy(true)
    try {
      const r = await api.deleteProject(project.id, project.name)
      toast(`“${r.deleted}” deleted`, {
        tone: 'success',
        detail: `${r.approvals_purged} approval record(s) and its long-term memory were purged.`,
      })
      onDeleted?.(project.id)
      onClose?.()
    } catch (e) {
      toast('Delete failed', { tone: 'error', detail: e.message })
    } finally {
      setBusy(false)
    }
  }

  const hasHistory = impact && (impact.approved_versions > 0 || impact.recorded_decisions > 0)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Delete “${project?.name}”?`}
      description="This cannot be undone."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" onClick={destroy} disabled={!armed} loading={busy}>
            <Trash2 className="h-3.5 w-3.5" /> Delete permanently
          </Button>
        </>
      }
    >
      {!impact ? (
        <div className="flex items-center gap-2 py-6 text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Checking what this would destroy…
        </div>
      ) : (
        <div className="space-y-4">
          <div className={`rounded-xl border p-3.5 ${hasHistory
            ? 'border-danger/25 bg-danger/5' : 'border-warning/25 bg-warning/5'}`}>
            <div className="flex gap-2.5">
              <AlertTriangle className={`h-4 w-4 shrink-0 mt-0.5 ${hasHistory ? 'text-danger' : 'text-warning'}`} />
              <p className={`text-[12.5px] leading-relaxed ${hasHistory ? 'text-danger' : 'text-warning'}`}>
                {impact.warning}
              </p>
            </div>
          </div>

          <div>
            <p className="mb-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted">
              What will be destroyed
            </p>
            <div className="grid grid-cols-2 gap-2">
              {[
                ['Source documents', impact.sources, false],
                ['Runs', impact.runs, false],
                ['Artifacts', impact.artifacts, false],
                ['Artifact versions', impact.artifact_versions, false],
                ['Approved versions', impact.approved_versions, impact.approved_versions > 0],
                ['Recorded decisions', impact.recorded_decisions, impact.recorded_decisions > 0],
              ].map(([label, n, critical]) => (
                <div key={label}
                  className={`flex items-center justify-between rounded-lg border px-3 py-2 ${
                    critical ? 'border-danger/25 bg-danger/5' : 'border-line bg-bg'}`}>
                  <span className={`text-[12px] ${critical ? 'font-medium text-danger' : 'text-muted'}`}>
                    {label}
                  </span>
                  <span className={`font-mono text-[13px] font-semibold tabular-nums ${
                    critical ? 'text-danger' : 'text-ink'}`}>{n}</span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-muted">
              Its long-term memory is purged too — otherwise a deleted project keeps answering the
              copilot.
            </p>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted">
              Type <span className="font-semibold text-ink">{project?.name}</span> to confirm
            </label>
            <Input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={project?.name}
              invalid={typed.length > 0 && !armed}
              autoFocus
            />
            {typed.length > 0 && !armed && (
              <p className="mt-1 text-[11px] text-danger">Names do not match.</p>
            )}
          </div>
        </div>
      )}
    </Dialog>
  )
}
