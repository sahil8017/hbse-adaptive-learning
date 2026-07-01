from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List
import json
import os
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = ""                      # Supabase postgresql+asyncpg://...
    REPLICA_DATABASE_URL: str = ""              # Optional read replica; falls back to primary

    # ── Security / JWT ──────────────────────────────────────────────────────
    SECRET_KEY: str                              # REQUIRED — must be ≥ 32 chars in .env
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30                   # Long-lived — students stay logged in
    JWT_REFRESH_EXPIRE_DAYS: int = 90           # Refresh token window

    # ── AI / LLM ────────────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct"
    GEMINI_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""         # YouTube Data API v3 key for video search & thumbnails
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_WEB_API_KEY: str = ""

    # ── Local paths ─────────────────────────────────────────────────────────
    EMBEDDING_MODEL_DIR: str = ""
    CHROMA_DIR: str = ""
    CURRICULUM_PATH: str = ""
    TUTOR_CONFIG_PATH: str = ""
    ENGLISH_CONFIG_PATH: str = ""
    HINDI_CONFIG_PATH: str = ""
    SUBJECT_CATALOG_PATH: str = ""
    RAG_INGEST_ON_STARTUP: bool = False

    # ── CORS ────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    FRONTEND_PUBLIC_URL: str = ""
    FRONTEND_URL: str = "http://localhost:3000"   # Used for share link generation
    ADMIN_SECRET: str = ""                         # Optional secret for admin API guard
    METRICS_BEARER_TOKEN: str = ""                # Optional bearer token for /metrics
    INIT_DB_SCHEMA_ON_STARTUP: bool = True        # Disable in production when migrations own schema changes
    ENABLE_PGVECTOR_SETUP: bool = True            # Disable if pgvector is managed externally

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_be_set(cls, v: str) -> str:
        if not v:
            logger.warning(
                "DATABASE_URL is not set. The application will fail on any database operation. "
                "Add your Supabase connection string to .env."
            )
        return v

    @field_validator("FIREBASE_PROJECT_ID")
    @classmethod
    def firebase_project_id_should_be_set(cls, v: str) -> str:
        if not v:
            logger.warning(
                "FIREBASE_PROJECT_ID is not set. Firebase ID token verification will fail."
            )
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return v

# ── Resolve default paths relative to project root ──────────────────────────
def _resolve_defaults(s: Settings) -> Settings:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if not s.EMBEDDING_MODEL_DIR:
        object.__setattr__(s, "EMBEDDING_MODEL_DIR", os.path.join(base, "backend", "app", "model", "paraphrase-multilingual-MiniLM-L12-v2"))
    if not s.CHROMA_DIR:
        object.__setattr__(s, "CHROMA_DIR", os.path.join(base, "db", "chroma"))
    if not s.CURRICULUM_PATH:
        object.__setattr__(s, "CURRICULUM_PATH", os.path.join(base, "data", "curriculum.json"))
    if not s.TUTOR_CONFIG_PATH:
        object.__setattr__(s, "TUTOR_CONFIG_PATH", os.path.join(base, "data", "tutor_config.json"))
    if not s.ENGLISH_CONFIG_PATH:
        object.__setattr__(s, "ENGLISH_CONFIG_PATH", os.path.join(base, "data", "subject_english_config.json"))
    if not s.HINDI_CONFIG_PATH:
        object.__setattr__(s, "HINDI_CONFIG_PATH", os.path.join(base, "data", "subject_hindi_config.json"))
    if not s.SUBJECT_CATALOG_PATH:
        object.__setattr__(s, "SUBJECT_CATALOG_PATH", os.path.join(base, "data", "subject_catalog.json"))
    return s

def validate_production_config(s: "Settings") -> List[str]:
    """Emit warnings for risky/missing production settings. Returns the warnings
    (also logged) so callers/tests can assert on them. Never raises."""
    warnings: List[str] = []
    if not s.ADMIN_SECRET:
        warnings.append("ADMIN_SECRET is unset — admin access relies solely on the students.is_admin flag.")
    if not s.METRICS_BEARER_TOKEN:
        warnings.append("METRICS_BEARER_TOKEN is unset — the /metrics endpoint is unauthenticated.")
    if not s.DATABASE_URL:
        warnings.append("DATABASE_URL is unset — all database operations will fail.")
    if not s.FIREBASE_PROJECT_ID:
        warnings.append("FIREBASE_PROJECT_ID is unset — Firebase ID token verification will fail.")
    if any("localhost" in o or "127.0.0.1" in o for o in s.ALLOWED_ORIGINS):
        warnings.append("ALLOWED_ORIGINS includes localhost — ensure this is not a production deployment.")
    for w in warnings:
        logger.warning("CONFIG WARNING: %s", w)
    return warnings


settings = _resolve_defaults(Settings())

# ── Curriculum (lazy loaded on first access) ────────────────────────────────
def load_curriculum() -> dict:
    try:
        with open(settings.CURRICULUM_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load curriculum from {settings.CURRICULUM_PATH}: {e}")
        return {}

class _LazyChaptersData(dict):
    """Lazy curriculum loader: reads JSON only on first dict access, not at import time."""
    _loaded: bool = False

    def _load(self):
        if not self._loaded:
            self._loaded = True
            try:
                with open(settings.CURRICULUM_PATH, "r", encoding="utf-8") as f:
                    self.update(json.load(f))
                logger.info("Curriculum loaded (%d subjects)", len(self))
            except Exception as exc:
                logger.error("Failed to load curriculum: %s", exc)

    def __getitem__(self, k):
        self._load()
        return super().__getitem__(k)

    def __contains__(self, k):
        self._load()
        return super().__contains__(k)

    def __iter__(self):
        self._load()
        return super().__iter__()

    def __len__(self):
        self._load()
        return super().__len__()

    def get(self, k, d=None):
        self._load()
        return super().get(k, d)

    def items(self):
        self._load()
        return super().items()

    def values(self):
        self._load()
        return super().values()

    def keys(self):
        self._load()
        return super().keys()

CHAPTERS_DATA: dict = _LazyChaptersData()
