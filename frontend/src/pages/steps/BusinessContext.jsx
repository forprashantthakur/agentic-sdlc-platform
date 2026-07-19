import { Building2, IndianRupee, Plus, Save, Target, TrendingUp, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../lib/api'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Input, Label, Select, Textarea, useToast } from '../../components/ui'

const BUSINESS_UNITS = [
  'Retail Banking — Digital Channels', 'Retail Banking — Liabilities', 'Retail Banking — Assets',
  'Wholesale Banking', 'Payments & Cards', 'Treasury', 'Wealth Management',
  'SME & Business Banking', 'Risk & Compliance', 'Operations & Technology',
]
const PRIORITIES = ['Critical', 'High', 'Medium', 'Low']
const REGULATIONS = ['RBI Master Direction', 'RBI e-Mandate', 'FEMA', 'PCI-DSS', 'DPDP Act 2023',
  'PMLA / KYC-AML', 'IRDAI', 'SEBI', 'Data Localisation']
const REQUIRED = ['name', 'business_unit', 'business_objective', 'problem_statement']

export default function BusinessContext({ project, onCreated, onNext }) {
  const toast = useToast()
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const [kpi, setKpi] = useState('')
  const [form, setForm] = useState(() => ({
    name: project?.name || '',
    business_unit: project?.business_unit || BUSINESS_UNITS[0],
    description: project?.description || '',
    business_owner: project?.context?.business_owner || '',
    project_sponsor: project?.context?.project_sponsor || '',
    priority: project?.context?.priority || 'High',
    business_objective: project?.context?.business_objective || '',
    problem_statement: project?.context?.problem_statement || '',
    current_challenges: project?.context?.current_challenges || '',
    desired_outcome: project?.context?.desired_outcome || '',
    expected_benefits: project?.context?.expected_benefits || '',
    business_kpis: project?.context?.business_kpis || [],
    estimated_business_value: project?.context?.estimated_business_value || '',
    timeline: project?.context?.timeline || '',
    budget: project?.context?.budget || '',
    regulatory_scope: project?.context?.regulatory_scope || [],
  }))

  const set = (k, v) => {
    setForm((f) => ({ ...f, [k]: v }))
    if (errors[k]) setErrors((e) => ({ ...e, [k]: false }))
  }

  const validate = () => {
    const e = {}
    for (const f of REQUIRED) if (!String(form[f] || '').trim()) e[f] = true
    setErrors(e)
    if (Object.keys(e).length) {
      toast('Fill the required fields', {
        tone: 'error',
        detail: 'Agent 1 grounds every requirement in evidence — a thin brief produces a thin BRD.',
      })
    }
    return !Object.keys(e).length
  }

  const persist = async (advance) => {
    if (advance && !validate()) return
    setSaving(true)
    try {
      const { name, business_unit, description, ...context } = form
      let p
      if (project) {
        await api.updateContext(project.id, context)
        p = await api.project(project.id)
      } else {
        p = await api.createProject({ name, business_unit, description, context })
      }
      onCreated?.(p)
      toast(advance ? 'Business context captured' : 'Draft saved', {
        tone: 'success',
        detail: advance ? 'Indexed into project memory — the copilot and the agents can now cite it.' : undefined,
      })
      if (advance) onNext?.()
    } catch (e) {
      toast('Could not save', { tone: 'error', detail: e.message })
    } finally {
      setSaving(false)
    }
  }

  const addKpi = () => {
    const v = kpi.trim()
    if (!v) return
    set('business_kpis', [...form.business_kpis, v])
    setKpi('')
  }
  const toggleReg = (r) =>
    set('regulatory_scope', form.regulatory_scope.includes(r)
      ? form.regulatory_scope.filter((x) => x !== r)
      : [...form.regulatory_scope, r])

  const filled = Object.values(form).filter((v) => (Array.isArray(v) ? v.length : String(v || '').trim())).length
  const completeness = Math.round((filled / Object.keys(form).length) * 100)

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Business Context</h1>
          <p className="text-[13px] text-muted mt-1">
            The brief the agents work from. It is indexed into project memory, so every requirement
            can be traced back to what the business actually asked for.
          </p>
        </div>
        <div className="text-right shrink-0 ml-6">
          <div className="text-[11px] text-muted mb-1" title="How much of this intake form is filled in. It scores the brief, not the project's progress.">Brief completeness</div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-24 rounded-full bg-line overflow-hidden">
              <div className={`h-full rounded-full transition-all ${completeness >= 70 ? 'bg-success' : 'bg-warning'}`}
                style={{ width: `${completeness}%` }} />
            </div>
            <span className="font-mono text-[12px] font-semibold tabular-nums">{completeness}%</span>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader><Building2 className="h-4 w-4 text-brand" /><CardTitle>Project identification</CardTitle></CardHeader>
        <CardBody className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <Label required>Project name</Label>
            <Input value={form.name} invalid={errors.name} onChange={(e) => set('name', e.target.value)}
              placeholder="e.g. UPI AutoPay Self-Service" />
          </div>
          <div>
            <Label required>Business unit</Label>
            <Select value={form.business_unit} onChange={(e) => set('business_unit', e.target.value)}>
              {BUSINESS_UNITS.map((b) => <option key={b}>{b}</option>)}
            </Select>
          </div>
          <div>
            <Label>Priority</Label>
            <Select value={form.priority} onChange={(e) => set('priority', e.target.value)}>
              {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
            </Select>
          </div>
          <div>
            <Label>Business owner</Label>
            <Input value={form.business_owner} onChange={(e) => set('business_owner', e.target.value)}
              placeholder="Accountable for the outcome" />
          </div>
          <div>
            <Label>Project sponsor</Label>
            <Input value={form.project_sponsor} onChange={(e) => set('project_sponsor', e.target.value)}
              placeholder="Signs off the concept note" />
          </div>
          <div className="md:col-span-2">
            <Label hint="One line — appears at the top of the BRD">Short description</Label>
            <Input value={form.description} onChange={(e) => set('description', e.target.value)}
              placeholder="Enable retail customers to create and manage UPI AutoPay mandates in MobileBanking." />
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <Target className="h-4 w-4 text-brand" />
          <CardTitle>The business case</CardTitle>
          <span className="ml-auto text-[11px] text-muted hidden md:inline">Agent 1 grounds requirements against this</span>
        </CardHeader>
        <CardBody className="grid gap-4">
          <div>
            <Label required hint="Outcome-based and measurable, not aspirational">Business objective</Label>
            <Textarea value={form.business_objective} invalid={errors.business_objective}
              onChange={(e) => set('business_objective', e.target.value)}
              placeholder="Reduce mandate-related call-centre volume by 40% within two quarters of launch." />
          </div>
          <div>
            <Label required hint="What is broken today — with numbers if you have them">Problem statement</Label>
            <Textarea value={form.problem_statement} invalid={errors.problem_statement}
              onChange={(e) => set('problem_statement', e.target.value)}
              placeholder="Mandate creation is an assisted journey: 12,400 tickets/month, AHT 7.4 min, 62% completion." />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Current challenges</Label>
              <Textarea value={form.current_challenges} onChange={(e) => set('current_challenges', e.target.value)}
                placeholder="Customers abandon at the authentication step; agents lack a mandate view." />
            </div>
            <div>
              <Label>Desired outcome</Label>
              <Textarea value={form.desired_outcome} onChange={(e) => set('desired_outcome', e.target.value)}
                placeholder="Customer creates, pauses and revokes a mandate without assistance." />
            </div>
          </div>
          <div>
            <Label>Expected benefits</Label>
            <Textarea value={form.expected_benefits} onChange={(e) => set('expected_benefits', e.target.value)}
              placeholder="Lower cost-to-serve, higher recurring-payment penetration, improved NPS." />
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader><TrendingUp className="h-4 w-4 text-brand" /><CardTitle>How success is measured</CardTitle></CardHeader>
        <CardBody className="space-y-4">
          <div>
            <Label hint="An objective without a baseline cannot be measured">Business KPIs</Label>
            <div className="flex gap-2">
              <Input value={kpi} onChange={(e) => setKpi(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addKpi() } }}
                placeholder="e.g. Mandate creation completion rate ≥ 85% (baseline 62%)" />
              <Button variant="secondary" onClick={addKpi} disabled={!kpi.trim()}>
                <Plus className="h-3.5 w-3.5" /> Add
              </Button>
            </div>
            {form.business_kpis.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {form.business_kpis.map((k, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5 rounded-lg border border-brand/20 bg-brand-soft px-2.5 py-1 text-[11.5px] text-brand">
                    {k}
                    <button onClick={() => set('business_kpis', form.business_kpis.filter((_, j) => j !== i))}
                      className="hover:text-danger" aria-label={`Remove ${k}`}>
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <Label>Estimated business value</Label>
              <Input value={form.estimated_business_value} onChange={(e) => set('estimated_business_value', e.target.value)}
                placeholder="INR 42 Cr annual" />
            </div>
            <div>
              <Label>Timeline</Label>
              <Input value={form.timeline} onChange={(e) => set('timeline', e.target.value)} placeholder="Q3–Q4 FY27" />
            </div>
            <div>
              <Label>Budget</Label>
              <Input value={form.budget} onChange={(e) => set('budget', e.target.value)} placeholder="INR 6.5 Cr" />
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <IndianRupee className="h-4 w-4 text-brand" />
          <CardTitle>Regulatory scope</CardTitle>
          <span className="ml-auto text-[11px] text-muted hidden md:inline">Drives the compliance requirements the agents must honour</span>
        </CardHeader>
        <CardBody>
          <div className="flex flex-wrap gap-2">
            {REGULATIONS.map((r) => {
              const on = form.regulatory_scope.includes(r)
              return (
                <button key={r} onClick={() => toggleReg(r)}
                  className={`rounded-lg border px-3 py-1.5 text-[12px] font-medium transition-colors ${
                    on ? 'border-brand bg-brand text-brand-fg' : 'border-line bg-surface text-muted hover:border-brand hover:text-brand'}`}>
                  {r}
                </button>
              )
            })}
          </div>
        </CardBody>
      </Card>

      <div className="flex flex-wrap items-center gap-3 pb-2">
        <Button variant="secondary" onClick={() => persist(false)} loading={saving}>
          <Save className="h-3.5 w-3.5" /> Save draft
        </Button>
        <Button onClick={() => persist(true)} loading={saving}>Continue to Knowledge Ingestion →</Button>
        {project && <Badge tone="success">Saved · {project.name}</Badge>}
      </div>
    </div>
  )
}
