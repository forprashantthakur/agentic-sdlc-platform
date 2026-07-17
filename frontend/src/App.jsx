import { Component, useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes, useNavigate } from 'react-router-dom'
import AppShell from './components/AppShell'
import DemoLibrary from './components/DemoLibrary'
import { ToastProvider, useToast } from './components/ui'
import { api } from './lib/api'
import Dashboard from './pages/Dashboard'
import Performance from './pages/Performance'
import Approve from './pages/Approve'
import Intake from './pages/Intake'
import Outbox from './pages/Outbox'
import SprintDelivery from './pages/SprintDelivery'
import NewBrd from './pages/NewBrd'
import { Agents, Documents, Integrations, Knowledge, Projects, ReviewCenter, Settings } from './pages/Misc'

function Shell() {
  const [project, setProject] = useState(null)
  const [run, setRun] = useState(null)
  const [health, setHealth] = useState(null)
  const [pending, setPending] = useState(0)
  const [intakeCount, setIntakeCount] = useState(0)
  const [library, setLibrary] = useState(false)
  const toast = useToast()
  const nav = useNavigate()

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth({ status: 'unreachable' })) }, [])

  // The approval count is the one number a reviewer looks for — keep it fresh.
  useEffect(() => {
    const tick = () => {
      api.intakeQueue().then((q) => setIntakeCount(q.length)).catch(() => {})
      api.approvals().then((a) => setPending(a.filter((x) => x.status === 'PENDING').length)).catch(() => {})
    }
    tick()
    const t = setInterval(tick, 8000)
    return () => clearInterval(t)
  }, [])

  return (
    <AppShell pending={pending} intakeCount={intakeCount} project={project} health={health}>
      <DemoLibrary
        open={library}
        onClose={() => setLibrary(false)}
        onSeeded={(p) => { setProject(p); nav('/new') }}
      />
      <Routes>
        <Route path="/" element={<Dashboard setProject={setProject} onSeed={() => setLibrary(true)} />} />
        <Route path="/new" element={<NewBrd project={project} setProject={setProject} run={run} setRun={setRun} />} />
        <Route path="/intake" element={<Intake setProject={setProject} setRun={setRun} />} />
        <Route path="/outbox" element={<Outbox />} />
        <Route path="/sprint-delivery" element={<SprintDelivery />} />
        <Route path="/projects" element={<Projects setProject={setProject} onSeed={() => setLibrary(true)} />} />
        <Route path="/knowledge" element={<Knowledge project={project} />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/review" element={<ReviewCenter setProject={setProject} />} />
        <Route path="/documents" element={<Documents project={project} />} />
        <Route path="/performance" element={<Performance />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </AppShell>
  )
}


/**
 * A last-resort boundary. A ReferenceError in any route used to take the WHOLE app down to a blank
 * white page with nothing in the UI to say why — which is exactly how a missing import shipped
 * unseen. Now a crash renders a message and, crucially, the actual error, so the next failure is
 * diagnosable from the screen instead of the console.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', fontFamily: 'Inter, Segoe UI, Arial, sans-serif', background: '#F4F5F6', padding: 24 }}>
          <div style={{ maxWidth: 560, background: '#fff', borderRadius: 12, padding: 28, boxShadow: '0 8px 30px rgba(0,0,0,.08)' }}>
            <div style={{ color: '#004C8F', fontSize: 12, letterSpacing: '.12em', fontWeight: 600 }}>HDFC BANK · AGENTIC SDLC PLATFORM</div>
            <h1 style={{ fontSize: 20, margin: '10px 0 6px', color: '#1A1A1A' }}>Something went wrong loading this screen</h1>
            <p style={{ fontSize: 13.5, color: '#63666A', lineHeight: 1.5 }}>
              Try reloading. If it persists, this message shows what failed:
            </p>
            <pre style={{ marginTop: 12, background: '#FEF2F2', color: '#9B2C2C', padding: 12, borderRadius: 8, fontSize: 12, whiteSpace: 'pre-wrap' }}>
              {String(this.state.error?.message || this.state.error)}
            </pre>
            <button onClick={() => window.location.reload()} style={{ marginTop: 14, padding: '10px 18px', border: 0, borderRadius: 8, background: '#004C8F', color: '#fff', fontWeight: 600, cursor: 'pointer' }}>
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <Routes>
        {/* The approver's landing page from the email — deliberately OUTSIDE the app chrome.
            An external approver clicking a link should see one clean decision screen, not the
            full console with a nav they have no login for. */}
        <Route path="/approve" element={<Approve />} />
        <Route path="/*" element={<ToastProvider><Shell /></ToastProvider>} />
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  )
}
