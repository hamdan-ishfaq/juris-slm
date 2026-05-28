from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "JurisGuard V2"
    database_url: str = "postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db"
    redis_url: str = "redis://localhost:6380/0"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3.5"
    training_mount_path: Path = Field(default=Path("/training"), validation_alias="TRAINING_MOUNT_PATH")

    auth_secret_key: str = Field(default="change-me-in-production", validation_alias="AUTH_SECRET_KEY")
    auth_token_expire_minutes: int = 60

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


settings = Settings()
