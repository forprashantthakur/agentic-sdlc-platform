import { Bot, ClipboardList, Send, Sparkles, Wand2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { cn } from '../../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Empty, Textarea } from '../../components/ui'

/* The interview a good BA would run. Answers are indexed as evidence, so a requirement traced to
   "Discovery interview" is as citable as one traced to a meeting note. */
const INTERVIEW = [
  { section: 'Users & Actors', q: 'Who are the primary users, and which internal actors touch this journey?' },
  { section: 'Pain Points', q: 'What specifically breaks today? Give me numbers if you have them.' },
  { section: 'Systems & Integrations', q: 'Which upstream and downstream systems are impacted?' },
  { section: 'Business Rules', q: 'What thresholds, limits or decision rules govern this capability?' },
  { section: 'Approvals & Controls', q: 'Are there maker-checker or approval workflows involved?' },
  { section: 'Compliance', q: 'Which regulations apply, and what do they mandate here?' },
  { section: 'Non-functional', q: 'What are the latency, availability and scale expectations?' },
  { section: 'Data', q: 'What data is captured, where does it live, and how long is it retained?' },
  { section: 'Success Metrics', q: 'How will we know this worked? Metric and baseline, please.' },
  { section: 'Risks & Dependencies', q: 'What could sink this, and what are we depending on?' },
]

export default function Discovery({ project, onNext, onBack }) {
  const [answers, setAnswers] = useState({})
  const [i, setI] = useState(0)
  const [draft, setDraft] = useState('')
  const [thread, setThread] = useState([{ role: 'ai', text: INTERVIEW[0].q, section: INTERVIEW[0].section }])
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [thread, busy])

  // One click fills the whole interview from the project's sample answers. Each answer is still
  // indexed as a source, exactly as if it had been typed — so the citations downstream are real, not
  // stagecraft. The 220ms stagger is deliberate: it reads as the interview being conducted rather
  // than a form being stuffed, and it lets the audience see the thread build.
  const autofill = async () => {
    if (busy) return
    setBusy(true)
    try {
      const { answers: sample } = await api.discoverySample(project.id)
      for (const { section, answer } of sample) {
        const q = INTERVIEW.find((x) => x.section === section)?.q || section
        setThread((t) => [...t, { role: 'user', text: answer }])
        setAnswers((a) => ({ ...a, [section]: answer }))
        try {
          await api.addSource(project.id, {
            kind: 'MEETING_NOTES',
            title: `Discovery interview — ${section}`,
            content: `Q: ${q}\nA: ${answer}`,
          })
        } catch { /* non-fatal */ }
        await new Promise((r) => setTimeout(r, 220))
      }
      setI(INTERVIEW.length)
      setThread((t) => [...t, {
        role: 'ai', done: true,
        text: 'Interview complete — filled from this project\'s sample answers. Every one is indexed as evidence, so the agents cite it exactly as they would a typed answer. Ready for AI Analysis.',
      }])
    } catch (e) {
      setThread((t) => [...t, { role: 'ai', text: `No sample interview for this project — ${e.message}` }])
    } finally {
      setBusy(false)
    }
  }

  const submit = async () => {
    const text = draft.trim()
    if (!text || busy || i >= INTERVIEW.length) return
    const current = INTERVIEW[i]
    setDraft('')
    setThread((t) => [...t, { role: 'user', text }])
    setAnswers((a) => ({ ...a, [current.section]: text }))
    setBusy(true)

    // The answer becomes evidence — indexed into project memory so agents can cite it.
    try {
      await api.addSource(project.id, {
        kind: 'MEETING_NOTES',
        title: `Discovery interview — ${current.section}`,
        content: `Q: ${current.q}\nA: ${text}`,
      })
    } catch { /* non-fatal: the answer still shows in the structured form */ }

    setTimeout(() => {
      const next = INTERVIEW[i + 1]
      if (next) {
        setThread((t) => [...t, { role: 'ai', text: next.q, section: next.section }])
        setI(i + 1)
      } else {
        setI(INTERVIEW.length)
        setThread((t) => [...t, {
          role: 'ai', done: true,
          text: 'That covers the interview. Every answer is indexed as evidence — the agents can cite it directly. Ready for AI Analysis.',
        }])
      }
      setBusy(false)
    }, 450)
  }

  if (!project) return <Empty icon={Bot} title="No project selected" />
  const answered = Object.keys(answers).length

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Requirement Discovery</h1>
          <p className="text-[13px] text-muted mt-1">
            Answers are indexed as evidence, so requirements derived from them stay traceable.
          </p>
        </div>
        <Badge tone={answered === INTERVIEW.length ? 'success' : 'brand'}>
          {answered} / {INTERVIEW.length} answered
        </Badge>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader>
            <Sparkles className="h-4 w-4 text-brand" />
            <CardTitle>Discovery interview</CardTitle>
            {i < INTERVIEW.length && (
              <Button size="sm" variant="secondary" className="ml-auto" onClick={autofill} loading={busy}>
                <Wand2 className="mr-1.5 h-3.5 w-3.5" />
                Fill sample answers
              </Button>
            )}
          </CardHeader>
          <CardBody className="flex-1 space-y-3 max-h-[480px] overflow-y-auto">
            {thread.map((m, k) => (
              <div key={k} className={cn('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div className={cn('max-w-[85%] rounded-xl px-3.5 py-2.5 text-[12.5px] leading-relaxed',
                  m.role === 'user' ? 'rounded-br-sm bg-brand text-brand-fg'
                    : cn('rounded-bl-sm border bg-bg', m.done ? 'border-success/30 text-success' : 'border-line text-ink'))}>
                  {m.section && <div className="text-[10px] font-semibold uppercase tracking-wider opacity-70 mb-1">{m.section}</div>}
                  {m.text}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex gap-1 px-2">
                {[0, 1, 2].map((k) => (
                  <span key={k} className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse" style={{ animationDelay: `${k * 150}ms` }} />
                ))}
              </div>
            )}
            <div ref={endRef} />
          </CardBody>
          <div className="border-t border-line p-3">
            <Textarea rows={2} value={draft} onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
              placeholder={i < INTERVIEW.length ? 'Answer, or say "not known" — a flagged gap beats a guess…' : 'Interview complete'}
              disabled={i >= INTERVIEW.length} />
            <div className="mt-2 flex justify-end">
              <Button size="sm" onClick={submit} disabled={!draft.trim() || i >= INTERVIEW.length}>
                <Send className="h-3.5 w-3.5" /> Send
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <ClipboardList className="h-4 w-4 text-brand" />
            <CardTitle>Structured capture</CardTitle>
            <span className="ml-auto text-[11px] text-muted">Auto-filled from the interview</span>
          </CardHeader>
          <CardBody className="space-y-3 max-h-[560px] overflow-y-auto">
            {INTERVIEW.map((s, k) => (
              <div key={s.section} className={cn('rounded-xl border p-3 transition-colors',
                answers[s.section] ? 'border-success/25 bg-success/5'
                  : k === i ? 'border-brand bg-brand-soft' : 'border-line bg-bg/40')}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[11.5px] font-semibold">{s.section}</span>
                  {answers[s.section] && <Badge tone="success">Captured</Badge>}
                  {k === i && !answers[s.section] && <Badge tone="brand">In progress</Badge>}
                </div>
                <p className="text-[11.5px] text-muted leading-snug">
                  {answers[s.section] || <span className="italic opacity-70">Awaiting answer…</span>}
                </p>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-3 pb-2">
        <Button variant="secondary" onClick={onBack}>← Back</Button>
        <Button onClick={onNext}>Continue to AI Analysis →</Button>
        {answered < INTERVIEW.length && (
          <span className="text-[11.5px] text-muted">
            You can skip ahead — unanswered areas surface as gaps rather than invented requirements.
          </span>
        )}
      </div>
    </div>
  )
}
