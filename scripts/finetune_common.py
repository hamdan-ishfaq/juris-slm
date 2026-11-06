"""Shared helpers for local smoke test and Colab fine-tuning."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

SYSTEM_PROMPT = "You are JurisGuard, an expert legal contract analyst."


def format_instruction_example(
    example: dict[str, Any],
    tokenizer: Any | None = None,
) -> str:
    """Turn one JSONL row into a Phi-3.5 chat string."""
    instruction = (example.get("instruction") or "").strip()
    user_input = (example.get("input") or "").strip()
    output = (example.get("output") or "").strip()

    user_content = f"{instruction}\n\n{user_input}".strip() if user_input else instruction

    if tokenizer is not None and getattr(tokenizer, "chat_template", None):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": output},
        ]
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )

    return (
        f"<|system|>\n{SYSTEM_PROMPT}<|end|>\n"
        f"<|user|>\n{user_content}<|end|>\n"
        f"<|assistant|>\n{output}<|end|>"
    )


def load_jsonl_rows(path: Path, max_examples: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if max_examples is not None and len(rows) >= max_examples:
                break
    return rows


def find_latest_checkpoint(output_dir: Path) -> Path | None:
    """Return the checkpoint-* folder with the highest global step."""
    if not output_dir.is_dir():
        return None

    best: Path | None = None
    best_step = -1
    for path in output_dir.iterdir():
        if not path.is_dir():
            continue
        match = re.fullmatch(r"checkpoint-(\d+)", path.name)
        if not match:
            continue
        state_file = path / "trainer_state.json"
        if not state_file.is_file():
            continue
        step = int(match.group(1))
        if step > best_step:
            best_step = step
            best = path
    return best


def read_trainer_step(checkpoint_dir: Path) -> int | None:
    state_file = checkpoint_dir / "trainer_state.json"
    if not state_file.is_file():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return int(data.get("global_step", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def write_run_manifest(
    manifest_path: Path,
    *,
    checkpoint_dir: Path | None,
    output_dir: Path,
    status: str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "checkpoint_dir": str(checkpoint_dir) if checkpoint_dir else None,
        "global_step": read_trainer_step(checkpoint_dir) if checkpoint_dir else 0,
    }
    if extra:
        payload.update(extra)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def sync_resume_checkpoint(source_checkpoint: Path, resume_dir: Path) -> Path:
    """
    Copy a full HF checkpoint to a fixed resume folder on Drive.
    Includes optimizer + scheduler + RNG state for true resume.
    """
    if resume_dir.exists():
        shutil.rmtree(resume_dir)
    shutil.copytree(source_checkpoint, resume_dir)

    marker = resume_dir / "RESUME_READY.txt"
    marker.write_text(
        f"Synced from {source_checkpoint}\n"
        f"step={read_trainer_step(source_checkpoint)}\n"
        f"at={datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )
    return resume_dir


def resolve_resume_checkpoint(output_dir: Path, resume_dir: Path | None = None) -> Path | None:
    """Prefer dedicated resume folder, then newest checkpoint-* in output_dir."""
    if resume_dir is not None and (resume_dir / "trainer_state.json").is_file():
        return resume_dir
    return find_latest_checkpoint(output_dir)
