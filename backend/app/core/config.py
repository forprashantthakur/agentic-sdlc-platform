from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    mock_mode: bool = True

    # Per-service overrides. None = inherit mock_mode. Set to false to force a single
    # integration live while everything else stays mocked (e.g. real Figma, mock Gemini).
    llm_mock: bool | None = None
    figma_mock: bool | None = None
    gmail_mock: bool | None = None
    drive_mock: bool | None = None
    jira_mock: bool | None = None

    database_url: str = "postgresql+psycopg://sdlc:sdlc@localhost:5432/sdlc"

    # Which provider the agents reason with: "gemini" | "anthropic".
    # Embeddings are ALWAYS Gemini — Anthropic has no embedding model — so GOOGLE_API_KEY stays
    # required even when Claude is doing the thinking.
    llm_provider: str = "gemini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    anthropic_fast_model: str = "claude-sonnet-5"

    # Per-agent overrides. JSON, e.g.
    #   AGENT_MODELS={"agent1_requirements":"anthropic:claude-opus-4-8",
    #                 "agent4_requirement_docs":"gemini-3.5-flash"}
    # Agent 1 is the judgement task — it decides whether two sources contradict each other and
    # refuses to resolve it. That is where a frontier model is worth paying for. The rest is
    # structured transformation, and a fast model does it well.
    agent_models: dict[str, str] = {}

    google_api_key: str = ""
    # Model names churn hard: 2.5 was retired for new keys, and gemini-3-pro now redirects.
    # These are current defaults, not guarantees — GET /api/integrations/llm/models asks YOUR key
    # what it can actually call, and that is the only answer that stays true.
    gemini_model: str = "gemini-3.1-pro"
    gemini_flash_model: str = "gemini-3.1-flash"
    # text-embedding-004 is gone from the current API version (404 on embedContent).
    gemini_embed_model: str = "gemini-embedding-001"

    # Gemini 2.5 Pro can emit long documents. Agent 4's SRS is the biggest single generation;
    # too low a budget truncates it into unparseable JSON.
    # The STARTING budget. On truncation the client doubles it (to a 65,536 ceiling) rather than
    # retrying the identical request — a retry that changes nothing is not a retry.
    max_output_tokens: int = 32768
    # PDF engine: "light" (fpdf2, pure-Python, low memory — safe on a 512MB host) or "weasyprint"
    # (prettier, but a multi-doc pack OOM-kills a small worker). Default light so downloads WORK;
    # set PDF_ENGINE=weasyprint on a bigger instance for nicer output.
    pdf_engine: str = "light"

    # Gemini 3.x THINKS before it answers, and that thinking is most of the latency you feel.
    #   -1  = model default (deep thinking; slowest, best judgement)
    #    0  = off (fastest)
    #   >0  = a token budget for reasoning
    #
    # Worth being deliberate about, because it is not a free lunch: Agent 1's whole job is to notice
    # that two sources contradict each other and REFUSE to resolve it. That is the one place thinking
    # earns its latency. Everything downstream is structured transformation, where it mostly does not.
    # Hence the per-agent override below.
    gemini_thinking_budget: int = -1

    # e.g. {"agent1_requirements": -1, "agent2_concept_note": 0, "agent4_requirement_docs": 0}
    agent_thinking: dict[str, int] = {}

    # How many generations Agent 4 may run at once. Default 1: on a free-tier key, six concurrent
    # calls is the surest way to earn a 429 or a 503, and a failed run costs far more than the
    # minute the concurrency saved. Raise it once you are on a paid quota.
    gemini_concurrency: int = 3

    # Ordered fallbacks, tried the instant the primary returns a transient error. NEVER WAIT IF
    # ANOTHER MODEL IS AVAILABLE — backoff is what you do when you have no alternative.
    # e.g. ["gemini-3.5-flash", "gemini-3.1-flash-lite", "anthropic:claude-sonnet-5"]
    # Failing over from Gemini to Gemini is not failing over: when Google is overloaded, every
    # Gemini model is on the same overloaded infrastructure. The chain must LEAVE the provider.
    # Anthropic candidates are skipped automatically when no ANTHROPIC_API_KEY is configured.
    fallback_chain: list[str] = [
        "gemini-3.5-flash",
        "anthropic:claude-haiku-4-5-20251001",
        "gemini-3.1-flash-lite",
    ]
    max_fallback_cycles: int = 3

    # Run Agent 3 (wireframes) and Agent 4 (documents) CONCURRENTLY. They are independent: both
    # derive from the approved concept note and requirements. The only coupling was that Agent 4's
    # prompt included the wireframe spec as context — which was never a real dependency. Documents
    # should derive from approved REQUIREMENTS, not from a picture. Set false to restore the old
    # sequential behaviour exactly.
    parallel_wireframes: bool = True
    # Must exceed the widest fan-out in the graph (currently 2) with headroom for the runner
    # thread and any concurrent run. Under-sizing this does not error — it silently serialises
    # the parallelism you paid for.
    checkpointer_pool_size: int = 8

    # Exact-hash response cache (NOT semantic — see llm/cache.py for why that would be dangerous).
    llm_cache_enabled: bool = True

    # Chunk-parallel extraction for large sources.
    ingest_chunk_chars: int = 12000
    ingest_max_parallel: int = 4

    use_vertex: bool = False
    vertex_project: str = ""
    vertex_location: str = "asia-south1"

    # Agent 3's wireframe provider: "stitch" | "figma" | "mock".
    # Stitch is the default: it generates a screen FROM TEXT — which is exactly what Agent 3 already
    # produces — returns HTML and a screenshot that can be embedded straight into the BRD, and needs
    # no paid seat. Figma's write-to-canvas wants geometry and a Full seat on a paid plan.
    wireframe_provider: str = "stitch"

    # Verified against google-labs-code/stitch-sdk. It is googleapis.com, not withgoogle.com.
    stitch_mcp_url: str = "https://stitch.googleapis.com/mcp"
    stitch_api_key: str = ""
    # The OAuth alternative. NEVER send both this and an API key — Google validates the
    # Authorization header first, fails, and 401s without looking at the key.
    stitch_access_token: str = ""
    google_cloud_project: str = ""
    stitch_mock: bool | None = None

    figma_mcp_url: str = "https://mcp.figma.com/mcp"
    figma_token: str = ""
    figma_team_id: str = ""

    google_sa_json: str = ""
    gmail_sender: str = "sdlc-bot@hdfcbank.com"
    # Real email delivery via plain SMTP — the low-friction path for a live inbox demo. When these
    # are set, approval emails are actually sent (to whatever address is in the run's approver list);
    # when they are not, the platform records the email to the Outbox and shows it in-app instead.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    gdrive_root_folder_id: str = ""

    jira_base_url: str = ""
    confluence_mock: bool | None = None
    confluence_base_url: str = "https://hdfcbank.atlassian.net/wiki"
    confluence_email: str = ""
    confluence_token: str = ""
    confluence_space: str = "SDLC"
    jira_email: str = ""
    jira_token: str = ""
    jira_project_key: str = "HDFC"
    # Issue-type names and the story-points field vary by Jira project template and by instance.
    # A business/finance project has no Story or Bug at all, so the adapter falls back to Task
    # rather than failing the run — see JiraAdapter._resolve_type.
    # Create a Jira project per platform project. Off by default: creating projects needs Jira
    # admin rights and is not trivially undoable, so it is an explicit choice.
    jira_auto_create_project: bool = False
    jira_epic_type: str = "Epic"
    jira_story_type: str = "Story"
    jira_bug_type: str = "Bug"
    jira_test_type: str = "Task"
    jira_story_points_field: str = ""      # blank = auto-detect, else e.g. customfield_10016

    jwt_secret: str = "change-me-in-prod"
    approval_token_ttl_hours: int = 72

    # Comma-separated list of allowed browser origins, e.g. the Vercel URL of the console.
    cors_origins: str = ""

    # Embedding dimension for text-embedding-004
    embed_dim: int = 768

    def is_mocked(self, service: str) -> bool:
        """Per-service resolution: explicit override wins, else the global MOCK_MODE."""
        override = getattr(self, f"{service}_mock", None)
        return self.mock_mode if override is None else override

    @property
    def db_url(self) -> str:
        """Managed Postgres providers (Render, Heroku, Railway) hand out `postgres://…`.
        SQLAlchemy 2 needs an explicit driver. Normalise rather than making deploys guess."""
        u = self.database_url
        if u.startswith("postgres://"):
            u = u.replace("postgres://", "postgresql+psycopg://", 1)
        elif u.startswith("postgresql://"):
            u = u.replace("postgresql://", "postgresql+psycopg://", 1)
        return u

    @property
    def allowed_origins(self) -> list[str]:
        if self.cors_origins:
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # No explicit allow-list: permissive in dev, closed in prod. Failing closed is the
        # only safe default — a misconfigured prod deploy should break, not silently open up.
        return ["*"] if self.app_env == "dev" else []

    @property
    def live_llm(self) -> bool:
        """True only when we have a real credential path AND the LLM is not mocked."""
        if self.is_mocked("llm"):
            return False
        return bool(self.google_api_key) or (self.use_vertex and bool(self.vertex_project))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
