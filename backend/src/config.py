from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "JurisGuard V2"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    database_url: str = "postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db"
    redis_url: str = "redis://localhost:6380/0"
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="phi3.5", validation_alias="OLLAMA_MODEL")
    ollama_aux_model: str = Field(default="qwen2.5:0.5b", validation_alias="OLLAMA_AUX_MODEL")
    llm_aux_provider: str = Field(default="ollama", validation_alias="LLM_AUX_PROVIDER")
    llm_provider: str = Field(default="openrouter", validation_alias="LLM_PROVIDER")
    graph_extraction_enabled: bool = Field(default=True, validation_alias="GRAPH_EXTRACTION_ENABLED")
    query_cache_enabled: bool = Field(default=True, validation_alias="QUERY_CACHE_ENABLED")
    query_cache_ttl_seconds: int = Field(default=3600, validation_alias="QUERY_CACHE_TTL_SECONDS")
    tracing_enabled: bool = Field(default=False, validation_alias="TRACING_ENABLED")
    oidc_enabled: bool = Field(default=False, validation_alias="OIDC_ENABLED")
    oidc_issuer_url: str = Field(default="", validation_alias="OIDC_ISSUER_URL")
    oidc_client_id: str = Field(default="", validation_alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", validation_alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field(default="http://localhost:5173/auth/callback", validation_alias="OIDC_REDIRECT_URI")
    langfuse_public_key: str = Field(default="", validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", validation_alias="LANGFUSE_HOST")
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
    adaptive_hyde_enabled: bool = Field(default=True, validation_alias="ADAPTIVE_HYDE_ENABLED")
    crag_retry_enabled: bool = Field(default=True, validation_alias="CRAG_RETRY_ENABLED")
    airgap_latency_profile: bool | None = Field(default=None, validation_alias="AIRGAP_LATENCY_PROFILE")
    embedding_device: str = Field(default="auto", validation_alias="EMBEDDING_DEVICE")
    reranker_device: str = Field(default="auto", validation_alias="RERANKER_DEVICE")
    auth_refresh_expire_days: int = Field(default=7, validation_alias="AUTH_REFRESH_EXPIRE_DAYS")
    auth_access_expire_minutes: int = Field(default=15, validation_alias="AUTH_ACCESS_EXPIRE_MINUTES")
    brand_name: str = Field(default="JurisGuard", validation_alias="BRAND_NAME")
    brand_tagline: str = Field(default="V2 · On-Premise", validation_alias="BRAND_TAGLINE")
    brand_logo_url: str = Field(default="", validation_alias="BRAND_LOGO_URL")
    brand_primary_color: str = Field(default="#5eead4", validation_alias="BRAND_PRIMARY_COLOR")
    ocr_enabled: bool = Field(default=True, validation_alias="OCR_ENABLED")
    ocr_min_chars_per_page: int = Field(default=50, validation_alias="OCR_MIN_CHARS_PER_PAGE")
    citation_verify_enabled: bool = Field(default=True, validation_alias="CITATION_VERIFY_ENABLED")
    semantic_context_min_cosine: float = Field(default=0.55, validation_alias="SEMANTIC_CONTEXT_MIN_COSINE")
    legal_hold_allow_export: bool = Field(default=True, validation_alias="LEGAL_HOLD_ALLOW_EXPORT")
    rls_enabled: bool = Field(default=True, validation_alias="RLS_ENABLED")
    worm_backend: str = Field(default="none", validation_alias="WORM_BACKEND")
    worm_filesystem_path: Path = Field(default=Path("/app/data/worm"), validation_alias="WORM_FILESYSTEM_PATH")
    saml_enabled: bool = Field(default=False, validation_alias="SAML_ENABLED")
    saml_entity_id: str = Field(default="jurisguard-sp", validation_alias="SAML_ENTITY_ID")
    saml_acs_url: str = Field(default="http://localhost:8002/api/v1/auth/saml/acs", validation_alias="SAML_ACS_URL")
    saml_idp_sso_url: str = Field(default="", validation_alias="SAML_IDP_SSO_URL")
    saml_idp_x509_cert: str = Field(default="", validation_alias="SAML_IDP_X509_CERT")
    saml_skip_signature_verify: bool = Field(default=False, validation_alias="SAML_SKIP_SIGNATURE_VERIFY")
    scim_enabled: bool = Field(default=False, validation_alias="SCIM_ENABLED")
    rag_min_query_words: int = Field(default=3, validation_alias="RAG_MIN_QUERY_WORDS")
    audit_log_answers: bool = Field(default=False, validation_alias="AUDIT_LOG_ANSWERS")
    chat_history_turns: int = Field(default=3, validation_alias="CHAT_HISTORY_TURNS")
    serve_ui_from_api: bool = Field(default=True, validation_alias="SERVE_UI_FROM_API")
    ui_dist_path: Path = Field(default=Path("/app/frontend/dist"), validation_alias="UI_DIST_PATH")

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
    def is_airgap_latency_profile(self) -> bool:
        """Low-latency retrieval settings for on-prem Ollama deployments."""
        if self.airgap_latency_profile is not None:
            return self.airgap_latency_profile
        return self.llm_provider.strip().lower() == "ollama"

    @property
    def effective_access_token_minutes(self) -> int:
        return self.auth_access_expire_minutes if self.auth_access_expire_minutes > 0 else self.auth_token_expire_minutes

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
