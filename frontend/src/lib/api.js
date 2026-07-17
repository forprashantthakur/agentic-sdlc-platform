const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function req(path, opts = {}) {
  const r = await fetch(`${BASE}${path}`, {
    headers: opts.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) {
    let detail = await r.text()
    try { detail = JSON.parse(detail).detail ?? detail } catch { /* plain text */ }
    throw new Error(detail || `${r.status} ${r.statusText}`)
  }
  return r.status === 204 ? null : r.json()
}

export const API_BASE = BASE

export const api = {
  // A generic GET. Its absence is why the Stitch probe and the Performance page both died with
  // "api.get is not a function" — in the browser, before the request was ever sent.
  get: (path) => req(path),
  post: (path, b) => req(path, { method: 'POST', body: b ? JSON.stringify(b) : undefined }),

  health: () => req('/health'),
  metrics: () => req('/api/metrics'),
  stitchProbe: () => req('/api/integrations/wireframes/probe'),
  discoverySample: (pid) => req(`/api/projects/${pid}/discovery/sample`),
  stats: () => req('/api/dashboard/stats'),
  queue: () => req('/api/dashboard/queue'),

  projects: () => req('/api/projects'),
  project: (id) => req(`/api/projects/${id}`),
  createProject: (b) => req('/api/projects', { method: 'POST', body: JSON.stringify(b) }),
  updateContext: (id, ctx) => req(`/api/projects/${id}/context`, { method: 'PATCH', body: JSON.stringify(ctx) }),
  demoCatalog: () => req('/api/projects/demo/catalog'),
  seedProject: (key = 'upi_autopay') => req(`/api/projects/seed?key=${key}`, { method: 'POST' }),
  seedAll: () => req('/api/projects/seed/all', { method: 'POST' }),
  deleteImpact: (id) => req(`/api/projects/${id}/impact`),
  deleteProject: (id, confirm) =>
    req(`/api/projects/${id}?confirm=${encodeURIComponent(confirm)}`, { method: 'DELETE' }),

  sources: (pid) => req(`/api/projects/${pid}/sources`),
  addSource: (pid, b) => req(`/api/projects/${pid}/sources`, { method: 'POST', body: JSON.stringify(b) }),
  deleteSource: (pid, sid) => req(`/api/projects/${pid}/sources/${sid}`, { method: 'DELETE' }),
  upload: (pid, files) => {
    const fd = new FormData()
    for (const f of files) fd.append('files', f)
    return req(`/api/projects/${pid}/upload`, { method: 'POST', body: fd })
  },

  startRun: (b) => req('/api/runs', { method: 'POST', body: JSON.stringify(b) }),
  runs: (pid) => req(`/api/runs${pid ? `?project_id=${pid}` : ''}`),
  events: (id, after = 0) => req(`/api/runs/${id}/events?after=${after}`),

  artifacts: (pid) => req(`/api/artifacts?project_id=${pid}`),
  version: (vid) => req(`/api/artifacts/versions/${vid}`),
  diff: (vid) => req(`/api/artifacts/versions/${vid}/diff`),
  exportUrl: (vid, fmt) => `${BASE}/api/artifacts/versions/${vid}/export?format=${fmt}`,
  packUrl: (pid, fmt, approvedOnly = false) =>
    `${BASE}/api/artifacts/pack?project_id=${pid}&format=${fmt}&approved_only=${approvedOnly}`,

  approvals: (pid) => req(`/api/approvals${pid ? `?project_id=${pid}` : ''}`),
  decide: (id, b) => req(`/api/approvals/${id}/decide`, { method: 'POST', body: JSON.stringify(b) }),
  decideByToken: (token, b) => req(`/api/approvals/by-token/${token}/decide`, { method: 'POST', body: JSON.stringify(b) }),
  intakeSend: (b) => req('/api/intake/email', { method: 'POST', body: JSON.stringify(b) }),
  intakeQueue: () => req('/api/intake'),
  intakeAccept: (id, b) => req(`/api/intake/${id}/accept`, { method: 'POST', body: JSON.stringify(b) }),
  intakeDiscard: (id) => req(`/api/intake/${id}/discard`, { method: 'POST' }),

  memorySearch: (pid, q, k = 8) =>
    req(`/api/memory/search?project_id=${pid}&q=${encodeURIComponent(q)}&k=${k}`),
  copilotChat: (b) => req('/api/copilot/chat', { method: 'POST', body: JSON.stringify(b) }),
  copilotInsights: (pid) => req(`/api/copilot/insights?project_id=${pid}`),

  stream: (runId, onEvent) => {
    const es = new EventSource(`${BASE}/api/runs/${runId}/stream`)
    es.onmessage = (e) => { try { onEvent(JSON.parse(e.data)) } catch { /* keep-alive */ } }
    es.onerror = () => es.close()
    return () => es.close()
  },
}
