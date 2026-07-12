import { AnimatePresence, motion } from 'framer-motion'
import {
  AudioLines, CheckCircle2, CloudUpload, Database, FileImage, FileSpreadsheet, FileText, FileType2,
  Loader2, Mail, Presentation, Trash2, TriangleAlert, Video, Workflow,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { cn, fmtBytes } from '../../lib/utils'
import { Badge, Button, Card, CardBody, CardHeader, CardTitle, Dialog, Empty, useToast } from '../../components/ui'

/* `live: false` means exactly that. The card says so, and clicking it explains what it would take
   to make it real. A connector card that pretends to connect is how a demo dies on stage. */
const CONNECTORS = [
  { id: 'sharepoint', name: 'SharePoint', cat: 'Documents', live: false },
  { id: 'confluence', name: 'Confluence', cat: 'Documents', live: false },
  { id: 'gdrive', name: 'Google Drive', cat: 'Documents', live: true, note: 'Adapter built · needs service-account credentials' },
  { id: 'onedrive', name: 'OneDrive', cat: 'Documents', live: false },
  { id: 'jira', name: 'Jira', cat: 'Delivery', live: true, note: 'Adapter built · Agent 6 writes epics and stories' },
  { id: 'ado', name: 'Azure DevOps', cat: 'Delivery', live: false },
  { id: 'servicenow', name: 'ServiceNow', cat: 'Enterprise', live: false },
  { id: 'salesforce', name: 'Salesforce', cat: 'Enterprise', live: false },
  { id: 'sap', name: 'SAP', cat: 'Enterprise', live: false },
  { id: 'oracle', name: 'Oracle', cat: 'Enterprise', live: false },
  { id: 'sql', name: 'SQL Database', cat: 'Data', live: false },
  { id: 'api', name: 'REST API', cat: 'Data', live: false },
  { id: 'gmail', name: 'Email Inbox', cat: 'Communication', live: true, note: 'Adapter built · Agent 5 sends approval threads' },
]

const FORMATS = [
  { icon: FileType2, label: 'PDF', parsed: true },
  { icon: FileText, label: 'Word', parsed: true },
  { icon: FileSpreadsheet, label: 'Excel', parsed: true },
  { icon: Presentation, label: 'PowerPoint', parsed: true },
  { icon: Mail, label: 'Email', parsed: true },
  { icon: FileText, label: 'Transcript', parsed: true },
  { icon: FileImage, label: 'Images', parsed: false, why: 'needs OCR' },
  { icon: AudioLines, label: 'Audio', parsed: false, why: 'needs speech-to-text' },
  { icon: Video, label: 'Video', parsed: false, why: 'needs speech-to-text' },
  { icon: Workflow, label: 'BPMN / Visio', parsed: false, why: 'no parser yet' },
]

const STATUS = {
  EXTRACTED: { tone: 'success', icon: CheckCircle2, label: 'Extracted & indexed' },
  OCR_PENDING: { tone: 'warning', icon: TriangleAlert, label: 'Needs OCR' },
  TRANSCRIPTION_PENDING: { tone: 'warning', icon: TriangleAlert, label: 'Needs transcription' },
  UNSUPPORTED: { tone: 'danger', icon: TriangleAlert, label: 'Unsupported' },
  TOO_LARGE: { tone: 'danger', icon: TriangleAlert, label: 'Too large' },
}

export default function KnowledgeIngestion({ project, onNext, onBack }) {
  const toast = useToast()
  const [sources, setSources] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState([])
  const [connector, setConnector] = useState(null)
  const inputRef = useRef(null)

  const load = useCallback(() => {
    if (project) api.sources(project.id).then(setSources).catch(() => {})
  }, [project])
  useEffect(() => { load() }, [load])

  const handleFiles = async (fileList) => {
    const files = [...fileList]
    if (!files.length || !project) return
    setUploading(files.map((f) => ({ name: f.name, size: f.size })))
    try {
      const r = await api.upload(project.id, files)
      const ok = r.files.filter((f) => f.status === 'EXTRACTED').length
      const partial = r.files.length - ok
      toast(`${ok} of ${r.files.length} file(s) extracted and indexed`, {
        tone: ok === r.files.length ? 'success' : 'warning',
        detail: partial
          ? `${partial} file(s) accepted but not readable yet — an agent cannot cite them until they are.`
          : `${r.files.reduce((a, f) => a + f.chunks, 0)} chunks added to project memory.`,
        duration: 6000,
      })
      load()
    } catch (e) {
      toast('Upload failed', { tone: 'error', detail: e.message })
    } finally {
      setUploading([])
    }
  }

  const remove = async (id) => {
    await api.deleteSource(project.id, id)
    toast('Source removed', { tone: 'info' })
    load()
  }

  const readable = sources.filter((s) => (s.meta?.status ?? 'EXTRACTED') === 'EXTRACTED')

  if (!project) {
    return <Empty icon={CloudUpload} title="No project yet"
      hint="Capture the business context first — uploads are indexed against a project." />
  }

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Knowledge Ingestion</h1>
          <p className="text-[13px] text-muted mt-1">
            Everything the agents will cite. Text is extracted, chunked and embedded into long-term
            memory — nothing is stored as an opaque blob.
          </p>
        </div>
        <div className="text-right shrink-0 ml-6">
          <div className="font-mono text-lg font-semibold tabular-nums">{readable.length}</div>
          <div className="text-[11px] text-muted">readable source{readable.length === 1 ? '' : 's'}</div>
        </div>
      </div>

      <Card className={cn('border-2 border-dashed transition-all', dragging && 'border-brand bg-brand-soft')}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}>
        <CardBody className="py-10 text-center">
          <motion.div animate={dragging ? { scale: 1.08, y: -3 } : { scale: 1, y: 0 }}
            className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-brand-soft">
            <CloudUpload className="h-6 w-6 text-brand" />
          </motion.div>
          <p className="text-[14px] font-semibold">{dragging ? 'Drop to ingest' : 'Drag documents here, or browse'}</p>
          <p className="mt-1 text-[12px] text-muted">
            Meeting notes · email threads · transcripts · requirement sheets · scope decks — up to 25 MB per file
          </p>
          <Button className="mt-4" onClick={() => inputRef.current?.click()}>
            <CloudUpload className="h-3.5 w-3.5" /> Browse files
          </Button>
          <input ref={inputRef} type="file" multiple hidden
            onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }} />

          <div className="mt-7 flex flex-wrap justify-center gap-1.5">
            {FORMATS.map((f) => {
              const Icon = f.icon
              return (
                <span key={f.label}
                  title={f.parsed ? 'Text extracted and indexed' : `Accepted, but ${f.why}`}
                  className={cn('inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-medium',
                    f.parsed ? 'border-line bg-surface text-muted' : 'border-warning/30 bg-warning/5 text-warning')}>
                  <Icon className="h-3.5 w-3.5" />
                  {f.label}
                  {!f.parsed && <span className="text-[9.5px] opacity-80">· {f.why}</span>}
                </span>
              )
            })}
          </div>
        </CardBody>
      </Card>

      <AnimatePresence>
        {uploading.length > 0 && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
            <Card>
              <CardBody className="space-y-2.5">
                {uploading.map((f) => (
                  <div key={f.name} className="flex items-center gap-3">
                    <Loader2 className="h-4 w-4 animate-spin text-brand shrink-0" />
                    <span className="text-[12.5px] font-medium truncate flex-1">{f.name}</span>
                    <span className="text-[11px] text-muted shrink-0">{fmtBytes(f.size)}</span>
                    <span className="text-[11px] text-brand shrink-0">Extracting & embedding…</span>
                  </div>
                ))}
              </CardBody>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      <Card>
        <CardHeader>
          <Database className="h-4 w-4 text-brand" />
          <CardTitle>Ingested sources</CardTitle>
          <Badge tone="brand" className="ml-auto">{sources.length}</Badge>
        </CardHeader>
        <CardBody className={sources.length ? 'p-0' : ''}>
          {sources.length === 0 ? (
            <Empty icon={FileText} title="Nothing ingested yet"
              hint="Upload the discovery notes, the sponsor's email thread and any call transcripts. Agent 1 cites these directly." />
          ) : (
            <ul className="divide-y divide-line">
              {sources.map((s) => {
                const st = STATUS[s.meta?.status ?? 'EXTRACTED'] ?? STATUS.EXTRACTED
                const Icon = st.icon
                return (
                  <li key={s.id} className="flex items-center gap-3 px-5 py-3 hover:bg-bg transition-colors group">
                    <div className={cn('grid h-8 w-8 shrink-0 place-items-center rounded-lg',
                      st.tone === 'success' ? 'bg-success/10' : st.tone === 'warning' ? 'bg-warning/10' : 'bg-danger/10')}>
                      <Icon className={cn('h-4 w-4',
                        st.tone === 'success' ? 'text-success' : st.tone === 'warning' ? 'text-warning' : 'text-danger')} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-medium truncate">{s.title}</span>
                        <Badge tone="outline">{s.kind.replaceAll('_', ' ')}</Badge>
                      </div>
                      <p className="text-[11px] text-muted mt-0.5 truncate">
                        {st.label} · {(s.chars ?? 0).toLocaleString()} chars
                        {s.meta?.pages ? ` · ${s.meta.pages} pages` : ''}
                        {s.meta?.note ? ` — ${s.meta.note}` : ''}
                      </p>
                    </div>
                    <button onClick={() => remove(s.id)}
                      className="opacity-0 group-hover:opacity-100 h-8 w-8 grid place-items-center rounded-lg text-muted hover:text-danger hover:bg-danger/10 transition-all"
                      aria-label={`Remove ${s.title}`}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <Workflow className="h-4 w-4 text-brand" />
          <CardTitle>Enterprise connectors</CardTitle>
          <span className="ml-auto text-[11px] text-muted">
            {CONNECTORS.filter((c) => c.live).length} of {CONNECTORS.length} have adapters built
          </span>
        </CardHeader>
        <CardBody className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {CONNECTORS.map((c) => (
            <button key={c.id} onClick={() => setConnector(c)}
              className={cn('group flex items-center gap-3 rounded-xl border p-3 text-left transition-all hover:shadow-card',
                c.live ? 'border-line bg-surface hover:border-brand' : 'border-line bg-bg/50 hover:border-muted')}>
              <div className={cn('grid h-9 w-9 shrink-0 place-items-center rounded-lg font-bold text-[13px]',
                c.live ? 'bg-brand-soft text-brand' : 'bg-line/60 text-muted')}>
                {c.name[0]}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] font-medium truncate">{c.name}</div>
                <div className="text-[10.5px] text-muted">{c.cat}</div>
              </div>
              <Badge tone={c.live ? 'success' : 'default'}>{c.live ? 'Adapter ready' : 'Not built'}</Badge>
            </button>
          ))}
        </CardBody>
      </Card>

      <Dialog open={!!connector} onClose={() => setConnector(null)} title={connector?.name}
        description={connector?.live ? 'Adapter implemented' : 'Not implemented yet'}
        footer={<Button variant="secondary" onClick={() => setConnector(null)}>Close</Button>}>
        {connector?.live ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-success/20 bg-success/5 p-3.5">
              <p className="text-[12.5px] text-success font-medium">This connector has a working adapter.</p>
              <p className="text-[12px] text-muted mt-1">{connector.note}</p>
            </div>
            <p className="text-[12.5px] text-muted leading-relaxed">
              It is running against a <strong>mock</strong> right now. Supply its credentials in the backend
              environment and it goes live on the next run — each integration switches independently, so you
              can take this one live without touching the others.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="rounded-xl border border-warning/20 bg-warning/5 p-3.5">
              <p className="text-[12.5px] text-warning font-medium">Not wired — and I'd rather tell you than fake it.</p>
              <p className="text-[12px] text-muted mt-1">
                This card is a placeholder. There is no {connector?.name} adapter behind it, and a
                “Connect” button would do nothing.
              </p>
            </div>
            <p className="text-[12.5px] text-muted leading-relaxed">
              The adapter pattern is already in place (<code className="font-mono text-[11px]">app/adapters/</code>) —
              a new connector is an interface implementation plus credentials, not a re-architecture. In the
              meantime, export from {connector?.name} and drop the file into the upload area above; the
              extraction path is identical.
            </p>
          </div>
        )}
      </Dialog>

      <div className="flex flex-wrap items-center gap-3 pb-2">
        <Button variant="secondary" onClick={onBack}>← Back</Button>
        <Button onClick={onNext} disabled={!readable.length}>Continue to Requirement Discovery →</Button>
        {!readable.length && (
          <span className="text-[11.5px] text-muted">
            At least one readable source is needed — the agents cite evidence, they don't invent it.
          </span>
        )}
      </div>
    </div>
  )
}
