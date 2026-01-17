# settings.py
# config/settings.py - Loads and validates configuration from config.yaml
import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from pydantic import BaseModel, Field, validator

class HardPattern(BaseModel):
    name: str
    pattern: str
    flags: str = ""
    tag: str

class SecurityConfig(BaseModel):
    hard_patterns: List[HardPattern] = Field(default_factory=list)
    sensitive_keywords: List[str] = Field(default_factory=list)
    public_keywords: List[str] = Field(default_factory=list)
    similarity_threshold: float = 0.55
    sentinel_threshold: float = 0.85

class IngestionConfig(BaseModel):
    chunk_size: int = 500
    chunk_overlap: int = 50

class QueryConfig(BaseModel):
    top_k: int = 3
    max_new_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.9

class APIConfig(BaseModel):
    origins: List[str] = Field(default_factory=list)
    port: int = 8000

class TestItem(BaseModel):
    category: str
    question: str
    ground_truth: str

class EvaluationConfig(BaseModel):
    test_data: List[TestItem] = Field(default_factory=list)

class TrainingConfig(BaseModel):
    dataset: str = "yahma/alpaca-cleaned"
    max_steps: int = 1500
    batch_size: int = 1
    gradient_accumulation_steps: int = 8
    learning_rate: float = 0.0002
    lora_r: int = 16
    lora_alpha: int = 32
    target_modules: List[str] = Field(default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])

class ModelsConfig(BaseModel):
    embedding_model: str = "all-MiniLM-L6-v2"
    llm_model: str = "microsoft/Phi-3-mini-4k-instruct"
    classifier_model: str = "facebook/bart-large-mnli"
    load_in_4bit: bool = False
    max_seq_length: int = 2048

class PathsConfig(BaseModel):
    faiss_db: str = "data/juris_faiss_db"
    model_adapters: str = "data/juris_local_proof"
    config_file: str = "config/config.yaml"

class Config(BaseModel):
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)

def load_config(config_path: str = None) -> Config:
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Config(**data)

# Global config instance
config = load_config()