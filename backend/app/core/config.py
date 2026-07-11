from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    mock_mode: bool = True

    database_url: str = "postgresql+psycopg://sdlc:sdlc@localhost:5432/sdlc"

    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "text-embedding-004"

    use_vertex: bool = False
    vertex_project: str = ""
    vertex_location: str = "asia-south1"

    figma_mcp_url: str = "http://figma-mcp:3845/mcp"
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
        """True only when we have a real credential path AND mocks are off."""
        if self.mock_mode:
            return False
        return bool(self.google_api_key) or (self.use_vertex and bool(self.vertex_project))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
