"""Central configuration. Every tunable lives here and comes from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM ---------------------------------------------------------------
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 60.0
    groq_max_tokens: int = 1200
    groq_temperature: float = 0.4

    # --- Database ----------------------------------------------------------
    db_backend: str = "sqlite"
    sqlite_path: str = "data/demopilot.db"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""

    # --- Auth --------------------------------------------------------------
    auth_backend: str = "local"
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expire_minutes: int = 60 * 24 * 7

    # --- RAG ---------------------------------------------------------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    rag_chunk_size: int = 900
    rag_chunk_overlap: int = 150
    rag_top_k: int = 6
    rag_min_score: float = 0.18

    # --- Storage -----------------------------------------------------------
    data_dir: str = "data"
    upload_dir: str = "data/uploads"
    faiss_dir: str = "data/faiss"

    # --- Uploads -----------------------------------------------------------
    max_upload_mb: int = 10
    allowed_upload_extensions: str = ".pdf,.docx,.txt,.md,.csv"

    # --- Server ------------------------------------------------------------
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_app_url: str = "http://localhost:5173"

    # --- Rate limiting -----------------------------------------------------
    rate_limit_enabled: bool = True
    public_rate_limit_per_minute: int = 30
    upload_rate_limit_per_minute: int = 10

    # --- Derived helpers ---------------------------------------------------

    @field_validator("db_backend", "auth_backend", mode="before")
    @classmethod
    def _lower(cls, v: str) -> str:
        return str(v).strip().lower()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extensions(self) -> set[str]:
        return {
            e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
            for e in self.allowed_upload_extensions.split(",")
            if e.strip()
        }

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def abs_path(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else (BACKEND_ROOT / p)

    @property
    def data_path(self) -> Path:
        return self.abs_path(self.data_dir)

    @property
    def upload_path(self) -> Path:
        return self.abs_path(self.upload_dir)

    @property
    def faiss_path(self) -> Path:
        return self.abs_path(self.faiss_dir)

    @property
    def sqlite_file(self) -> Path:
        return self.abs_path(self.sqlite_path)

    @property
    def use_supabase(self) -> bool:
        return self.db_backend == "supabase"

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())

    def ensure_dirs(self) -> None:
        for p in (self.data_path, self.upload_path, self.faiss_path):
            p.mkdir(parents=True, exist_ok=True)
        self.sqlite_file.parent.mkdir(parents=True, exist_ok=True)

    def validate_runtime(self) -> list[str]:
        """Non-fatal configuration warnings surfaced at startup and on /api/health."""
        warnings: list[str] = []
        if not self.llm_configured:
            warnings.append(
                "GROQ_API_KEY is not set — the AI Sales Engineer cannot generate replies."
            )
        if self.use_supabase and not (self.supabase_url and self.supabase_service_role_key):
            warnings.append(
                "DB_BACKEND=supabase but SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are missing."
            )
        if self.app_env != "development" and self.jwt_secret.startswith("change-me"):
            warnings.append("JWT_SECRET is still the default value — set a strong secret.")
        return warnings


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
