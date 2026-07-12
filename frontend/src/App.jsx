import { useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes, useNavigate } from 'react-router-dom'
import AppShell from './components/AppShell'
import DemoLibrary from './components/DemoLibrary'
import { ToastProvider, useToast } from './components/ui'
import { api } from './lib/api'
import Dashboard from './pages/Dashboard'
import NewBrd from './pages/NewBrd'
import { Agents, Documents, Integrations, Knowledge, Projects, ReviewCenter, Settings } from './pages/Misc'

function Shell() {
  const [project, setProject] = useState(null)
  const [run, setRun] = useState(null)
  const [health, setHealth] = useState(null)
  const [pending, setPending] = useState(0)
  const [library, setLibrary] = useState(false)
  const toast = useToast()
  const nav = useNavigate()

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth({ status: 'unreachable' })) }, [])

  // The approval count is the one number a reviewer looks for — keep it fresh.
  useEffect(() => {
    const tick = () =>
      api.approvals().then((a) => setPending(a.filter((x) => x.status === 'PENDING').length)).catch(() => {})
    tick()
    const t = setInterval(tick, 8000)
    return () => clearInterval(t)
  }, [])

  return (
    <AppShell pending={pending} project={project} health={health}>
      <DemoLibrary
        open={library}
        onClose={() => setLibrary(false)}
        onSeeded={(p) => { setProject(p); nav('/new') }}
      />
      <Routes>
        <Route path="/" element={<Dashboard setProject={setProject} onSeed={() => setLibrary(true)} />} />
        <Route path="/new" element={<NewBrd project={project} setProject={setProject} run={run} setRun={setRun} />} />
        <Route path="/projects" element={<Projects setProject={setProject} />} />
        <Route path="/knowledge" element={<Knowledge project={project} />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/review" element={<ReviewCenter setProject={setProject} />} />
        <Route path="/documents" element={<Documents project={project} />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider><Shell /></ToastProvider>
    </BrowserRouter>
  )
}
