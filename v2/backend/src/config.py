from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "JurisGuard V2"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    database_url: str = "postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db"
    redis_url: str = "redis://localhost:6380/0"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3.5"
    llm_provider: str = Field(default="openrouter", validation_alias="LLM_PROVIDER")
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="microsoft/phi-4-mini-instruct",
        validation_alias="OPENROUTER_MODEL",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
    )
    training_mount_path: Path = Field(default=Path("/training"), validation_alias="TRAINING_MOUNT_PATH")

    auth_secret_key: str = Field(default="change-me-in-production", validation_alias="AUTH_SECRET_KEY")
    auth_token_expire_minutes: int = 60
    registration_open: bool = Field(default=True, validation_alias="REGISTRATION_OPEN")

    allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://localhost:8002",
        validation_alias="ALLOWED_ORIGINS",
    )
    expose_openapi: bool = Field(default=True, validation_alias="EXPOSE_OPENAPI")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, validation_alias="MAX_UPLOAD_BYTES")

    embedding_dim: int = 1024
    embedding_model_path: Path = Field(
        default=Path("/app/data/models/bge-m3"), validation_alias="EMBEDDING_MODEL_PATH"
    )
    reranker_model_path: Path = Field(
        default=Path("/app/data/models/reranker"), validation_alias="RERANKER_MODEL_PATH"
    )
    law_corpus_path: Path = Field(
        default=Path("/app/data/raw/law_corpus"), validation_alias="LAW_CORPUS_PATH"
    )

    rag_top_k: int = 20
    rag_rerank_k: int = 5
    rag_max_context_chars: int = 6000

    hybrid_search_enabled: bool = Field(default=True, validation_alias="HYBRID_SEARCH_ENABLED")
    rag_rrf_k: int = Field(default=60, validation_alias="RAG_RRF_K")
    hyde_enabled: bool = Field(default=False, validation_alias="HYDE_ENABLED")
    contextual_retrieval_enabled: bool = Field(default=True, validation_alias="CONTEXTUAL_RETRIEVAL_ENABLED")
    rag_min_rerank_score: float = Field(default=-2.0, validation_alias="RAG_MIN_RERANK_SCORE")
    citation_verify_enabled: bool = Field(default=True, validation_alias="CITATION_VERIFY_ENABLED")
    rag_min_query_words: int = Field(default=3, validation_alias="RAG_MIN_QUERY_WORDS")

    # Dev master — local eval/E2E only; disabled by default (enable in .env for dev)
    dev_master_enabled: bool = Field(default=False, validation_alias="DEV_MASTER_ENABLED")
    dev_master_email: str = Field(
        default="devmaster@example.com",
        validation_alias="DEV_MASTER_EMAIL",
    )
    dev_master_password: str = Field(
        default="DevMasterPass123!",
        validation_alias="DEV_MASTER_PASSWORD",
    )

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, v: str) -> str:
        return (v or "development").strip().lower()


settings = Settings()
