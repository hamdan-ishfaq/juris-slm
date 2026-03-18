# models.py
# src/models.py - Model loading and management
import logging
from pathlib import Path
from typing import Optional
import torch
from sentence_transformers import SentenceTransformer, CrossEncoder

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, config):
        self.config = config
        self.embedding_model: Optional[SentenceTransformer] = None
        self.reranker_model: Optional[CrossEncoder] = None
        self.llm_tokenizer = None
        self.llm_model = None

    def load_embedding_model(self):
        if self.embedding_model is None:
            logger.info(f"Loading embedding model: {self.config.models.embedding_model}")
            model_name = self.config.models.embedding_model
            
            # Ensure we have the full sentence-transformers path
            if "/" not in model_name:
                model_name = f"sentence-transformers/{model_name}"
            elif not model_name.startswith("sentence-transformers/"):
                # If user provided partial path, prepend sentence-transformers
                model_name = f"sentence-transformers/{model_name.split('/')[-1]}"
            
            try:
                logger.info(f"Downloading/loading model from HuggingFace: {model_name}")
                self.embedding_model = SentenceTransformer(model_name, device="cpu", trust_remote_code=True)
                logger.info(f"✅ Embedding model loaded successfully: {model_name}")
                return
            except Exception as e:
                logger.error(f"❌ Failed to load embedding model: {e}")
                # Try a lightweight alternative
                logger.warning(f"⚠️ Attempting fallback model...")
                try:
                    fallback = "sentence-transformers/paraphrase-MiniLM-L6-v2"
                    logger.info(f"Loading fallback: {fallback}")
                    self.embedding_model = SentenceTransformer(fallback, device="cpu", trust_remote_code=True)
                    logger.info(f"✅ Fallback embedding model loaded: {fallback}")
                    return
                except Exception as e2:
                    error_msg = f"Failed to load both primary and fallback embedding models.\nPrimary error: {str(e)[:100]}\nFallback error: {str(e2)[:100]}"
                    logger.error(f"❌ {error_msg}")
                    raise RuntimeError(error_msg)

    def load_llm(self):
        if not HF_AVAILABLE:
            raise ImportError("Hugging Face transformers not available")
        if self.llm_model is None or self.llm_tokenizer is None:
            print(f"[LLM_LOAD] Starting LLM load: {self.config.models.llm_model}", flush=True)
            
            # Set environment for better debugging
            import os
            os.environ["TRANSFORMERS_VERBOSITY"] = "info"
            
            try:
                # Tokenizer
                print(f"[LLM_LOAD] Loading tokenizer...", flush=True)
                tok_source = str(Path(self.config.paths.model_adapters) / "tokenizer.json") if (Path(self.config.paths.model_adapters) / "tokenizer.json").exists() else self.config.models.llm_model
                self.llm_tokenizer = AutoTokenizer.from_pretrained(tok_source, trust_remote_code=True)
                print(f"[LLM_LOAD] Tokenizer loaded", flush=True)
                if self.llm_tokenizer.pad_token is None:
                    self.llm_tokenizer.pad_token = self.llm_tokenizer.eos_token

                # Model
                print(f"[LLM_LOAD] Checking CUDA availability...", flush=True)
                use_cuda = torch.cuda.is_available()
                print(f"[LLM_LOAD] CUDA available: {use_cuda}", flush=True)
                
                if use_cuda and self.config.models.load_in_4bit:
                    print(f"[LLM_LOAD] Creating BitsAndBytesConfig for 4-bit loading...", flush=True)
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16
                    )
                    print(f"[LLM_LOAD] Loading model with 4-bit quantization (this may take 2-3 minutes)...", flush=True)
                    import sys
                    sys.stdout.flush()
                    
                    self.llm_model = AutoModelForCausalLM.from_pretrained(
                    self.config.models.llm_model,
                    quantization_config=bnb_config,
                    device_map={"": 0},
                    trust_remote_code=True,
                )   
                else:
                    print(f"[LLM_LOAD] Loading model without quantization (CUDA={use_cuda})...", flush=True)
                    device_map = "auto" if use_cuda else None
                    dtype = torch.float16 if use_cuda else torch.float32
                    import sys
                    sys.stdout.flush()
                    self.llm_model = AutoModelForCausalLM.from_pretrained(
                        self.config.models.llm_model,
                        device_map=device_map,
                        torch_dtype=dtype,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True
                    )
                print(f"[LLM_LOAD] Model loaded successfully", flush=True)

                # Attach adapters if present
                print(f"[LLM_LOAD] Checking for PEFT adapters...", flush=True)
                adapter_path = Path(self.config.paths.model_adapters)
                if adapter_path.exists() and (adapter_path / "adapter_config.json").exists():
                    print(f"[LLM_LOAD] Attaching PEFT adapters from {adapter_path}", flush=True)
                    self.llm_model = PeftModel.from_pretrained(self.llm_model, str(adapter_path), is_trainable=False)

                self.llm_model.eval()
                print(f"[LLM_LOAD] LLM fully loaded and in eval mode", flush=True)
            except Exception as e:
                print(f"[LLM_LOAD] ERROR: Failed to load LLM: {e}", flush=True)
                raise

    def _choose_reranker_device(self) -> str:
        """Prefer CPU for reranker unless there is ample VRAM available."""
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            try:
                total_mem_bytes = torch.cuda.get_device_properties(0).total_memory
                # Prefer GPU only if >8GB to leave headroom for the LLM
                if total_mem_bytes > 8 * 1024 ** 3:
                    return "cuda"
                logger.info("GPU detected but VRAM is tight; loading reranker on CPU to conserve memory")
            except Exception as exc:  # pragma: no cover - safety fallback
                logger.warning(f"Could not inspect GPU memory, using CPU for reranker: {exc}")
        return "cpu"

    def load_reranker(self):
        if self.reranker_model is None:
            device = self._choose_reranker_device()
            logger.info(
                f"Loading reranker model: {self.config.models.reranker_model} on {device}"
            )
            try:
                self.reranker_model = CrossEncoder(self.config.models.reranker_model, device=device)
            except Exception as e:
                logger.error(f"Failed to load reranker model: {e}")
                raise

    def unload_models(self):
        # Optional: clear GPU memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()