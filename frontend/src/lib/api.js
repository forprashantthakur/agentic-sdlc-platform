const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function req(path, opts = {}) {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.status === 204 ? null : r.json()
}

export const api = {
  health: () => req('/health'),

  projects: () => req('/api/projects'),
  seedProject: () => req('/api/projects/seed', { method: 'POST' }),
  sources: (pid) => req(`/api/projects/${pid}/sources`),

  startRun: (body) => req('/api/runs', { method: 'POST', body: JSON.stringify(body) }),
  runs: (pid) => req(`/api/runs?project_id=${pid}`),
  run: (id) => req(`/api/runs/${id}`),
  events: (id, after = 0) => req(`/api/runs/${id}/events?after=${after}`),
  history: (id) => req(`/api/runs/${id}/history`),

  artifacts: (pid) => req(`/api/artifacts?project_id=${pid}`),
  exportUrl: (vid, fmt) => `${BASE}/api/artifacts/versions/${vid}/export?format=${fmt}`,
  packUrl: (pid, fmt, approvedOnly = false) =>
    `${BASE}/api/artifacts/pack?project_id=${pid}&format=${fmt}&approved_only=${approvedOnly}`,
  version: (vid) => req(`/api/artifacts/versions/${vid}`),
  diff: (vid) => req(`/api/artifacts/versions/${vid}/diff`),

  approvals: (pid) => req(`/api/approvals?project_id=${pid}`),
  decide: (id, body) => req(`/api/approvals/${id}/decide`, { method: 'POST', body: JSON.stringify(body) }),

  // Server-sent events: the run timeline streams instead of polling.
  stream: (runId, onEvent) => {
    const es = new EventSource(`${BASE}/api/runs/${runId}/stream`)
    es.onmessage = (e) => { try { onEvent(JSON.parse(e.data)) } catch { /* keep-alive */ } }
    es.onerror = () => es.close()
    return () => es.close()
  },
}
