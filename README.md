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
