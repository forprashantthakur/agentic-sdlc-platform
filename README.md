# HDFC Bank — Enterprise Agentic AI SDLC Platform

Six-agent platform on **Gemini 2.5 Pro** that takes the messy front end of the SDLC —
meeting notes, email threads, voice transcripts — and turns it into an approved,
version-controlled, traceable requirement documentation set and a Jira backlog.

Built as a **POC**: everything runs offline with `MOCK_MODE=true`, and every external
system (Gemini, Vertex, Figma, Gmail, Drive, Jira) is behind an adapter with a real
implementation and a mock implementation.

---

## Quick start (zero credentials required)

```bash
cp .env.example .env      # MOCK_MODE=true is the default
docker compose up --build
```

- Console → http://localhost:5173
- API docs → http://localhost:8000/docs
- Integration status → http://localhost:8000/health

Then, in the console:

1. **Load demo project (UPI AutoPay)** — seeds three real, mutually contradictory sources:
   workshop notes, an email thread, and a sponsor call transcript.
2. **Start SDLC run.** Agents 1 → 2 execute, then the run *suspends* at the concept-note gate.
3. In the **Approval inbox**, type a comment and hit **Request changes**. Watch Agent 2 regenerate,
   producing a **v2** with a viewable diff, and re-open the gate as a new round.
4. **Approve.** Agents 3 → 4 run, the run suspends at the documentation gate.
5. **Approve.** Agent 6 plans the sprints and writes the Jira backlog. Run completes.

## Going live

Flip integrations on independently — each one activates the moment its credential exists.

| Set in `.env` | Turns on |
|---|---|
| `MOCK_MODE=false` + `GOOGLE_API_KEY` | Gemini 2.5 Pro via Google AI Studio |
| `USE_VERTEX=true` + `VERTEX_PROJECT` | Gemini via Vertex AI (VPC-SC, CMEK, `asia-south1` residency) |
| `FIGMA_TOKEN` + `FIGMA_MCP_URL` | Agent 3 authors real Figma frames over MCP |
| `GOOGLE_SA_JSON` + `GMAIL_SENDER` | Agent 5 sends real threaded approval emails |
| `GOOGLE_SA_JSON` + `GDRIVE_ROOT_FOLDER_ID` | Approved artifacts pushed to Google Drive |
| `JIRA_TOKEN` + `JIRA_BASE_URL` | Agent 6 creates real epics and stories |

`/health` always tells you which of these are `live` and which are `mock` — so nobody
demos a "live" run that was quietly mocked.

## Tests

```bash
cd backend
DATABASE_URL="sqlite:////tmp/t.db" MOCK_MODE=true pytest -q
```

Covers the full six-agent run including a **rejected round and a regeneration**, the
content-addressed versioning rules, and namespaced RAG retrieval.

---

## The agents

| # | Agent | In | Out |
|---|---|---|---|
| 1 | Requirement Gathering | Meeting notes, emails, voice transcripts | Structured business requirements, stakeholders, **conflicts**, **gaps** |
| 2 | Concept Note | Requirements | Objectives, scope, out-of-scope, business rules, assumptions, dependencies, risks |
| 3 | Wireframe | Concept note | Screen spec + Figma frames (via **MCP**) |
| 4 | Requirement Document | Concept note + wireframes | BRD, FRD, SRS, User Stories, Acceptance Criteria, API Requirements, NFRs |
| 5 | Approval | Any artifact version | Threaded approval emails, comment capture, version approval, workflow resume |
| 6 | Sprint | Approved docs | Epics, features, stories, points, ACs → **Jira** |

Agents 1 and 4 are deliberately conservative: they emit **gaps** and **conflicts** rather
than resolving ambiguity themselves. An agent that quietly invents a missing requirement is
a liability in a bank; one that escalates is an analyst.

## Layout

```
backend/app/
  agents/      a1…a6 + shared base + JSON schemas for constrained decoding
  graph/       LangGraph state, nodes, gates, routing
  memory/      short-term (checkpointer) · long-term (pgvector RAG) · vector store
  adapters/    figma_mcp · gmail · gdrive · jira  (+ mock twins, credential-aware registry)
  services/    versioning · rendering · run lifecycle
  api/         projects · runs (SSE) · artifacts (+diff) · approvals · memory
  llm/         Gemini client (AI Studio / Vertex / mock)
frontend/src/  React console: pipeline, live timeline, artifact+version viewer, approval inbox
```

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the design decisions and the
trade-offs behind them.

---

## Deploying it live

Split deployment, because the two halves have different needs: the console is a static
bundle, the backend is a long-running container with a database.

**Backend → Render** (reads `render.yaml`, provisions Postgres automatically)

1. [render.com](https://render.com) → **New** → **Blueprint** → connect this repo.
2. Render reads `render.yaml`: builds `backend/Dockerfile`, provisions Postgres 16,
   wires `DATABASE_URL`, generates `JWT_SECRET`. Deploy.
3. Copy the service URL, e.g. `https://sdlc-backend.onrender.com`. Check `/health` — it
   reports which integrations are live vs mocked.

**Frontend → Vercel**

1. [vercel.com/new](https://vercel.com/new) → import this repo. `vercel.json` supplies the
   build config; leave the framework preset alone.
2. Add an environment variable: `VITE_API_BASE` = your Render backend URL.
3. Deploy.

**Then close the CORS loop:** back in Render, set `CORS_ORIGINS` to your Vercel URL
(e.g. `https://agentic-sdlc-platform.vercel.app`) and redeploy. Until you do, the browser
will block every API call — `allowed_origins` fails *closed* in prod by design.

### Why not all of it on Vercel?

The backend cannot run serverless, and this is architectural rather than a config gap:

- runs execute on a **background thread** and would be killed the moment the function returns;
- the **SSE** timeline outlives a serverless invocation's duration cap;
- **pgvector** needs a real Postgres;
- and the whole point of the LangGraph Postgres checkpointer is that a run **suspended at an
  approval gate for days** survives a redeploy. Serverless has nowhere to survive.

Agent 4 alone makes seven Gemini 2.5 Pro calls. That is minutes, not seconds.

Cloud Run is the better long-term home — same GCP project as Vertex, `asia-south1` residency
intact — and the same `Dockerfile` deploys there unchanged.

### A note on running it publicly

The deployed default is `MOCK_MODE=true`. That is deliberate: the platform has **no
authentication** (see `docs/ARCHITECTURE.md` §7), so a public URL with a live `GOOGLE_API_KEY`
is an unauthenticated LLM endpoint — a quota drain and a prompt-injection target. The mock
demo is fully functional: six agents, both approval gates, the revision loop, versioned diffs.
Add auth before you add a real key.


---

## Taking Figma live (Agent 3)

Figma's MCP server gained **write-to-canvas** in Feb 2026. Before that, file content was
read-only over the REST API and generating wireframes into Figma was impossible without a
custom plugin. So this is newly possible — and the adapter is built for the fact that the
server's tool names are version- and plan-dependent.

**It does not guess tool names.** It calls `tools/list`, discovers what the server actually
offers, and resolves `create_file` / `create_frame` / `export` against that. If a tool is
missing it says so, loudly, naming what *was* available.

1. **Seat:** write-to-canvas needs a **Full seat on a paid plan**. Dev seats are read-only
   outside drafts; Starter/View seats get ~6 tool calls a month. Check this before anything else.

2. **Configure:**
   ```bash
   FIGMA_MCP_URL=https://mcp.figma.com/mcp   # remote; the local 127.0.0.1:3845 server needs
                                             # the desktop app on the same machine
   FIGMA_TOKEN=<your token>
   FIGMA_MOCK=false                          # live Figma, everything else still mocked
   ```

3. **Discover the real tool set:**
   ```bash
   curl -s https://<your-backend>/api/integrations/figma/tools | python3 -m json.tool
   ```
   Returns every advertised tool with its input schema, plus `resolved_operations` (what the
   adapter mapped) and `missing_operations` (what it could not). If `missing_operations` is
   empty, Agent 3 will author real frames on the next run.

4. **If an operation is missing**, add the server's actual tool name to `TOOL_CANDIDATES` in
   `backend/app/adapters/figma_mcp.py`. One line per rename — cheaper than rewriting call sites.

**Worth weighing first:** write-to-canvas is in beta and Figma have signalled it becomes
usage-based paid afterwards. Agent 3 already produces a structured screen spec, and that spec
— not the Figma frames — is what Agent 4 consumes downstream. The frames are for humans to look
at. Decide whether that is worth a paid seat plus per-call billing.


---

## Exporting documents

Every artifact — Concept Note, BRD, FRD, SRS, Wireframes, User Stories, Acceptance Criteria,
API Requirements, NFRs, Sprint Plan, Business Requirements — exports to **Word (.docx)**,
**PDF** and **Markdown**, from the console or the API.

```
GET /api/artifacts/versions/{version_id}/export?format=docx|pdf|md
GET /api/artifacts/pack?project_id={id}&format=docx|pdf&approved_only=true
```

The **pack** is the one that matters in practice: every artifact in one document, ordered as a
requirements pack reads (Requirements → Concept Note → Wireframes → BRD → FRD → SRS → Stories →
ACs → APIs → NFRs → Sprint Plan), with a cover page and — on every document — its version,
producing agent, model and approval status. `approved_only=true` exports only signed-off
versions, which is the artifact you hand an auditor.

**Why there is only one renderer.** `render.py` turns each structured payload into markdown;
that markdown is what the reviewer sees on screen and what the diff engine compares. Export
parses *that same markdown* into a block model and renders it to Word and PDF. Writing a
separate renderer per format per artifact type would be nine types × three formats of drift
waiting to happen — the PDF would eventually, quietly, disagree with the screen. One source of
truth, three outputs.

PDF uses WeasyPrint (real tables, repeating headers across page breaks, page numbers), which
links against pango/cairo — those system libraries are installed in `backend/Dockerfile`.
Without them the import succeeds at build time and fails on the first PDF request.


---

## The console

A six-step guided flow — **Business Context → Knowledge Ingestion → Requirement Discovery →
AI Analysis → Review → Generate BRD** — with a persistent, grounded **AI Copilot** on the right,
a nine-item left nav (Dashboard, New BRD, Projects, Knowledge Sources, AI Agents, Review Center,
Documents, Integrations, Settings) and dark mode throughout. Tailwind + a hand-rolled
shadcn-equivalent design system; no Radix, no Next.js — the deployed Vite SPA stays deployed.

**Business Context** captures the brief (sponsor, owner, priority, objective, problem statement,
KPIs, business value, timeline, budget, regulatory scope) and **indexes it into project memory**,
so the copilot and the agents can cite what the business actually asked for.

**Knowledge Ingestion** does real extraction: PDF, Word, Excel, PowerPoint, email and transcripts
are parsed, chunked and embedded. Images and audio are **accepted and honestly marked**
`OCR_PENDING` / `TRANSCRIPTION_PENDING` — an agent that cannot read a document must not pretend it
did. Connector cards state plainly whether an adapter exists behind them.

**The AI Copilot is grounded, not decorative.** Every answer retrieves from that project's memory
first; the model is instructed to answer only from it and to say so when the evidence doesn't
cover the question. Citations come back with each response. An ungrounded copilot in a
requirements tool invents a requirement, a BA pastes it into the BRD, and nobody can trace where
it came from.

**On the unbuilt.** Some actions (Publish, Generate test cases, Generate FSD, 9 of the 13
connectors) have no backend. They render — the flow reads end-to-end — but clicking them says
*"preview — not wired"* rather than failing silently. In a governance review, a button that lies
costs more credibility than a button that is honestly absent.
