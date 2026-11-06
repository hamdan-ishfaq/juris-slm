#!/usr/bin/env python3
"""
Phase 1.3 — Local smoke test for Phi-3.5 QLoRA fine-tuning.

Verifies GPU, data formatting, checkpoint save, and resume on a tiny subset
before you run the full job on Colab.

Usage (from v2/):
  pip install -r scripts/requirements-finetune.txt
  python scripts/05_smoke_test_finetune.py
  python scripts/05_smoke_test_finetune.py --use-unsloth   # faster training (optional)
  python scripts/05_smoke_test_finetune.py --resume --max-steps 50

Default model is pre-quantized 4-bit (~2.3 GB), NOT full FP16 (~7.6 GB).
Expect ~5–15 min on RTX 4050 after model download.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainerCallback,
)
from trl import SFTConfig, SFTTrainer
from tqdm import tqdm

from finetune_common import (
    PROCESSED,
    format_instruction_example,
    find_latest_checkpoint,
    load_jsonl_rows,
    resolve_resume_checkpoint,
    sync_resume_checkpoint,
    write_run_manifest,
)

# Pre-quantized 4-bit on HF (~2.3 GB download). Avoid microsoft/* FP16 (~7.6 GB).
DEFAULT_MODEL_ID = "unsloth/Phi-3.5-mini-instruct-bnb-4bit"
FULL_MODEL_ID = "microsoft/Phi-3.5-mini-instruct"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "smoke_checkpoints"
RESUME_DIR_NAME = "checkpoint_RESUME"


def _load_hf_token() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("HF_TOKEN=") and not os.environ.get("HF_TOKEN"):
            os.environ["HF_TOKEN"] = line.split("=", 1)[1].strip().strip('"').strip("'")


def _is_prequantized(model_id: str) -> bool:
    lower = model_id.lower()
    return "bnb-4bit" in lower or "-4bit" in lower or "gguf" in lower


class SyncResumeCallback(TrainerCallback):
    """Mirror each saved checkpoint to a fixed resume folder (same as Colab notebook)."""

    def __init__(self, resume_dir: Path, manifest_path: Path) -> None:
        self.resume_dir = resume_dir
        self.manifest_path = manifest_path

    def on_save(self, args, state, control, **kwargs):
        ckpt = find_latest_checkpoint(Path(args.output_dir))
        if ckpt is None:
            return
        sync_resume_checkpoint(ckpt, self.resume_dir)
        write_run_manifest(
            self.manifest_path,
            checkpoint_dir=ckpt,
            output_dir=Path(args.output_dir),
            status="training",
            extra={"global_step": state.global_step, "epoch": state.epoch},
        )


def build_dataset(tokenizer, train_path: Path, max_examples: int) -> Dataset:
    rows = load_jsonl_rows(train_path, max_examples=max_examples)
    texts = [
        format_instruction_example(row, tokenizer)
        for row in tqdm(rows, desc="Formatting examples", unit="ex")
    ]
    return Dataset.from_dict({"text": texts})


def load_with_unsloth(model_id: str, max_seq_length: int):
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_id,
        max_seq_length=max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.print_trainable_parameters()
    return model, tokenizer


def load_with_transformers(model_id: str):
    print(f"Loading tokenizer: {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if _is_prequantized(model_id):
        print("Loading pre-quantized 4-bit weights (~2–3 GB download)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            dtype=torch.float16,
            trust_remote_code=True,
            attn_implementation="eager",
        )
    else:
        print(
            "WARNING: Full FP16 model (~7.6 GB download). "
            f"Prefer: --model-id {DEFAULT_MODEL_ID}"
        )
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb_config,
            device_map="auto",
            dtype=torch.float16,
            trust_remote_code=True,
            attn_implementation="eager",
        )

    model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model, tokenizer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-file", type=Path, default=PROCESSED / "train_final.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-examples", type=int, default=400)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--save-steps", type=int, default=10)
    parser.add_argument("--max-seq-length", type=int, default=512)
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--model-id", type=str, default=DEFAULT_MODEL_ID)
    parser.add_argument(
        "--use-unsloth",
        action="store_true",
        help="Use Unsloth loader (faster training; pip install unsloth first)",
    )
    parser.add_argument(
        "--no-amp",
        action="store_true",
        help="Disable fp16/bf16 mixed precision (default for smoke test)",
    )
    parser.add_argument(
        "--fp16",
        action="store_true",
        help="Enable fp16 mixed precision (faster; may fail on WSL+torch 2.12)",
    )
    args = parser.parse_args()

    _load_hf_token()

    if not args.train_file.is_file():
        print(f"Missing train file: {args.train_file}", file=sys.stderr)
        return 1

    if not torch.cuda.is_available():
        print("CUDA not available — smoke test requires GPU.", file=sys.stderr)
        return 1

    device_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"GPU: {device_name} ({vram_gb:.1f} GB VRAM)")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    resume_dir = args.output_dir / RESUME_DIR_NAME
    manifest_path = args.output_dir / "RUN_MANIFEST.json"

    if args.use_unsloth:
        print("\nLoading via Unsloth (4-bit QLoRA)...")
        model, tokenizer = load_with_unsloth(args.model_id, args.max_seq_length)
    else:
        print("\nLoading via transformers + bitsandbytes (4-bit QLoRA)...")
        model, tokenizer = load_with_transformers(args.model_id)

    print(f"\nBuilding dataset ({args.max_examples} examples)...")
    dataset = build_dataset(tokenizer, args.train_file, args.max_examples)

    # Default: no AMP for smoke test (30 steps). WSL+torch 2.12 breaks fp16 GradScaler with bf16 grads.
    use_fp16 = args.fp16 and not args.no_amp
    use_bf16 = False
    if not use_fp16:
        print("Mixed precision: off (use --fp16 to enable; fine for 30-step smoke test)")

    training_args = SFTConfig(
        output_dir=str(args.output_dir),
        max_steps=args.max_steps,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=use_fp16,
        bf16=use_bf16,
        logging_steps=1,
        save_steps=args.save_steps,
        save_total_limit=3,
        report_to="none",
        optim="paged_adamw_8bit",
        warmup_steps=2,
        lr_scheduler_type="cosine",
        gradient_checkpointing=not args.use_unsloth,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_length=args.max_seq_length,
        dataset_text_field="text",
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset,
        args=training_args,
        callbacks=[SyncResumeCallback(resume_dir, manifest_path)],
    )

    resume_ckpt = None
    if args.resume:
        resume_ckpt = resolve_resume_checkpoint(args.output_dir, resume_dir)
        if resume_ckpt:
            step = resume_ckpt.name.replace("checkpoint-", "")
            print(f"\n↻ Resuming full training state from: {resume_ckpt} (step {step})")
        else:
            print("\n--resume set but no checkpoint found; starting fresh.")

    print(f"\nTraining for {args.max_steps} steps (save every {args.save_steps})...")
    trainer.train(resume_from_checkpoint=str(resume_ckpt) if resume_ckpt else None)

    final_ckpt = find_latest_checkpoint(args.output_dir)
    if final_ckpt:
        sync_resume_checkpoint(final_ckpt, resume_dir)

    adapter_dir = args.output_dir / "final_adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    write_run_manifest(
        manifest_path,
        checkpoint_dir=final_ckpt,
        output_dir=args.output_dir,
        status="smoke_test_complete",
        extra={
            "max_steps": args.max_steps,
            "max_examples": args.max_examples,
            "model_id": args.model_id,
            "use_unsloth": args.use_unsloth,
        },
    )

    print("\n✓ Smoke test complete.")
    print(f"  Adapter: {adapter_dir}")
    print(f"  Resume folder: {resume_dir}")
    print(f"  Manifest: {manifest_path}")
    print("\nNext: upload train/eval JSONL to Drive and open notebooks/phi35_legal_finetune.ipynb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
