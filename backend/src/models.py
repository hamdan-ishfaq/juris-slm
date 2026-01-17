# models.py
# src/models.py - Model loading and management
import logging
from pathlib import Path
from typing import Optional
import torch
from sentence_transformers import SentenceTransformer

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, config):
        self.config = config
        self.embedding_model: Optional[SentenceTransformer] = None
        self.llm_tokenizer = None
        self.llm_model = None

    def load_embedding_model(self):
        if self.embedding_model is None:
            logger.info(f"Loading embedding model: {self.config.models.embedding_model}")
            try:
                self.embedding_model = SentenceTransformer(self.config.models.embedding_model, device="cpu")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

    def load_llm(self):
        if not HF_AVAILABLE:
            raise ImportError("Hugging Face transformers not available")
        if self.llm_model is None or self.llm_tokenizer is None:
            logger.info(f"Loading LLM: {self.config.models.llm_model}")
            try:
                # Tokenizer
                tok_source = str(Path(self.config.paths.model_adapters) / "tokenizer.json") if (Path(self.config.paths.model_adapters) / "tokenizer.json").exists() else self.config.models.llm_model
                self.llm_tokenizer = AutoTokenizer.from_pretrained(tok_source, trust_remote_code=True)
                if self.llm_tokenizer.pad_token is None:
                    self.llm_tokenizer.pad_token = self.llm_tokenizer.eos_token

                # Model
                use_cuda = torch.cuda.is_available()
                device_map = "auto" if use_cuda else None
                dtype = torch.float16 if use_cuda else torch.float32
                self.llm_model = AutoModelForCausalLM.from_pretrained(
                    self.config.models.llm_model,
                    device_map=device_map,
                    torch_dtype=dtype,
                    load_in_4bit=self.config.models.load_in_4bit,
                    trust_remote_code=True
                )

                # Attach adapters if present
                adapter_path = Path(self.config.paths.model_adapters)
                if adapter_path.exists() and (adapter_path / "adapter_config.json").exists():
                    logger.info(f"Attaching PEFT adapters from {adapter_path}")
                    self.llm_model = PeftModel.from_pretrained(self.llm_model, str(adapter_path), is_trainable=False)

                self.llm_model.eval()
                logger.info("LLM loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load LLM: {e}")
                raise

    def unload_models(self):
        # Optional: clear GPU memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()