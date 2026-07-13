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
    gemini_concurrency: int = 1

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
    stitch_mock: bool | None = None

    figma_mcp_url: str = "https://mcp.figma.com/mcp"
    figma_token: str = ""
    figma_team_id: str = ""

    google_sa_json: str = ""
    gmail_sender: str = "sdlc-bot@hdfcbank.com"
    gdrive_root_folder_id: str = ""

    jira_base_url: str = ""
    jira_email: str = ""
    jira_token: str = ""
    jira_project_key: str = "HDFC"

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
