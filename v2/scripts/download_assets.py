#!/usr/bin/env python3
"""
JurisGuard V2 — Download datasets and models with live progress.

Shows for each file: name, downloaded/total bytes, percentage, speed, ETA.

Usage (from v2/ directory):
  python scripts/download_assets.py --list
  python scripts/download_assets.py --datasets              # all datasets
  python scripts/download_assets.py --datasets --only cuad
  python scripts/download_assets.py --models                # bge-m3 + reranker + ollama phi3.5
  python scripts/download_assets.py --models --only bge-m3
  python scripts/download_assets.py --all                   # datasets + models

Setup (once):
  cd v2
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r scripts/requirements-download.txt
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MODELS = ROOT / "data" / "models"

MAX_RETRIES = int(os.environ.get("DOWNLOAD_MAX_RETRIES", "20"))
RETRY_BASE_DELAY = float(os.environ.get("DOWNLOAD_RETRY_DELAY", "10"))
RETRY_MAX_DELAY = float(os.environ.get("DOWNLOAD_RETRY_MAX_DELAY", "300"))

T = TypeVar("T")

# Skip ONNX/OpenVINO extras — full bge-m3 repo is ~4.6 GB without this filter
HF_IGNORE_HEAVY = [
    "**/onnx/**",
    "**/openvino/**",
    "**/*.onnx",
    "**/*.onnx_data",
    "**/coreml/**",
]

BGE_M3_ALLOW = [
    "*.json",
    "*.safetensors",
    "*.bin",
    "tokenizer*",
    "*.model",
    "*.txt",
    "sentencepiece*",
    "1_Pooling/**",
    "2_Normalize/**",
]

RERANKER_ALLOW = [
    "*.json",
    "*.safetensors",
    "*.bin",
    "tokenizer*",
    "*.txt",
    "vocab.txt",
]


def setup_hf_auth() -> None:
    """
    Use HuggingFace token from environment or v2/.env (gitignored).
    Never pass tokens on the command line or commit them to git.
    """
    import os

    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = token
        print("  HuggingFace: authenticated (HF_TOKEN from .env or environment)")
    else:
        print("  HuggingFace: unauthenticated (optional: set HF_TOKEN in v2/.env)")


def retry_download(label: str, fn: Callable[[], T]) -> T:
    """Retry on network/SSL/timeout errors (default 20 attempts, exponential backoff)."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES:
                break
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            print(
                f"\n  [{label}] attempt {attempt}/{MAX_RETRIES} failed: {exc}\n"
                f"  Retrying in {delay:.0f}s ...\n",
                file=sys.stderr,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def is_model_complete(key: str) -> bool:
    """Return True if model artifacts look complete on disk."""
    if key == "bge-m3":
        d = MODELS / "bge-m3"
        if not d.is_dir():
            return False
        weights = list(d.rglob("*.safetensors")) + list(d.rglob("pytorch_model.bin"))
        return any(f.stat().st_size > 500_000_000 for f in weights if f.is_file())
    if key == "reranker":
        d = MODELS / "reranker"
        if not d.is_dir():
            return False
        weights = list(d.rglob("*.safetensors")) + list(d.rglob("pytorch_model.bin"))
        return any(f.stat().st_size > 10_000_000 for f in weights if f.is_file())
    if key == "phi35-tokenizer":
        d = MODELS / "phi-3.5-mini-instruct"
        return d.is_dir() and any(d.rglob("tokenizer*.json"))
    if key == "phi35-ollama":
        if not shutil.which("ollama"):
            return False
        try:
            out = subprocess.check_output(["ollama", "list"], text=True, stderr=subprocess.DEVNULL)
            return "phi3.5" in out.lower()
        except subprocess.CalledProcessError:
            return False
    return False


# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------

def fmt_bytes(n: int | float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}TB"


def download_url_to_file(url: str, dest: Path, desc: str) -> Path:
    """Stream-download a URL with tqdm progress (speed + total when known)."""

    def _do() -> Path:
        return _download_url_to_file_once(url, dest, desc)

    return retry_download(desc, _do)


def _download_url_to_file_once(url: str, dest: Path, desc: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    headers: dict[str, str] = {}
    mode = "wb"
    downloaded = 0
    if tmp.exists():
        downloaded = tmp.stat().st_size
        headers["Range"] = f"bytes={downloaded}-"
        mode = "ab"

    with requests.get(url, stream=True, headers=headers, timeout=120) as resp:
        resp.raise_for_status()
        if resp.status_code == 416:
            tmp.rename(dest)
            return dest

        total = downloaded
        content_range = resp.headers.get("Content-Range", "")
        if content_range and "/" in content_range:
            total = int(content_range.split("/")[-1])
        elif resp.headers.get("Content-Length"):
            total = downloaded + int(resp.headers["Content-Length"])

        bar = tqdm(
            total=total or None,
            initial=downloaded,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=desc[:60],
            dynamic_ncols=True,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )
        try:
            with open(tmp, mode) as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
        finally:
            bar.close()

    tmp.rename(dest)
    return dest


def html_to_plain_text(html: str) -> str:
    """Minimal HTML → text (no extra dependencies)."""
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n\n", html)
    html = re.sub(r"(?i)</div>", "\n", html)
    html = re.sub(r"(?i)</h[1-6]>", "\n\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def save_law_text(dest: Path, body: str, source: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    header = f"# Source: {source}\n# JurisGuard V2 law corpus — do not edit manually\n\n"
    dest.write_text(header + body.strip() + "\n", encoding="utf-8")
    return dest


def hf_snapshot(
    repo_id: str,
    local_dir: Path,
    *,
    allow_patterns: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
) -> Path:
    """Download a HuggingFace repo with per-file tqdm progress and retries."""
    from huggingface_hub import snapshot_download

    local_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  HuggingFace: {repo_id}")
    print(f"  Destination: {local_dir}")
    if allow_patterns:
        print(f"  Filter: {len(allow_patterns)} allow pattern(s) (skips ONNX/OpenVINO bloat)")
    print(f"  Retries: up to {MAX_RETRIES} on network failure")
    print(f"{'='*60}")

    def _do() -> Path:
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_dir),
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            tqdm_class=tqdm,
            resume_download=True,
        )
        return Path(path)

    return retry_download(repo_id, _do)


def load_and_save_dataset(
    label: str,
    load_fn: Callable,
    dest: Path,
) -> Path:
    """Load a HF dataset (shows hub download progress) and save to disk."""
    from datasets import load_dataset

    print(f"\n{'='*60}")
    print(f"  Dataset: {label}")
    print(f"  Destination: {dest}")
    print(f"{'='*60}")

    dest.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ds = load_fn()
    print(f"  Loaded in {time.time() - t0:.1f}s — saving to disk...")
    ds.save_to_disk(str(dest))
    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"  Saved ({fmt_bytes(size)})")
    return dest


def ollama_pull(model: str) -> None:
    """Run `ollama pull` with live stdout (ollama shows its own progress)."""
    if not shutil.which("ollama"):
        raise RuntimeError(
            "ollama CLI not found. Install: https://ollama.com\n"
            "Or start the Docker service: docker compose up ollama -d"
        )

    print(f"\n{'='*60}")
    print(f"  Ollama model: {model}")
    print(f"  (ollama shows layer download progress below)")
    print(f"{'='*60}\n")

    proc = subprocess.Popen(
        ["ollama", "pull", model],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"  {line.rstrip()}")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ollama pull {model} failed (exit {rc})")


# ---------------------------------------------------------------------------
# Dataset definitions
# ---------------------------------------------------------------------------

@dataclass
class DatasetSpec:
    key: str
    label: str
    est_size: str
    fn: Callable[[], Path]


def _squad_json_to_rows(squad: dict) -> list[dict]:
    rows: list[dict] = []
    for article in squad.get("data", []):
        title = article.get("title", "")
        for para in article.get("paragraphs", []):
            context = para.get("context", "")
            for qa in para.get("qas", []):
                answers = qa.get("answers", [])
                rows.append(
                    {
                        "title": title,
                        "context": context,
                        "question": qa.get("question", ""),
                        "answers": [a.get("text", "") for a in answers],
                        "answer_starts": [a.get("answer_start", -1) for a in answers],
                        "id": qa.get("id", ""),
                        "is_impossible": qa.get("is_impossible", False),
                    }
                )
    return rows


def _rows_to_dataset_dict(
    train_rows: list[dict],
    test_rows: list[dict],
) -> "DatasetDict":
    from datasets import Dataset, DatasetDict

    return DatasetDict(
        {
            "train": Dataset.from_list(train_rows),
            "test": Dataset.from_list(test_rows),
        }
    )


def _load_cuad_from_hf_files():
    """Download CUAD JSON/CSV only — skips 511 PDFs that break load_dataset()."""
    from huggingface_hub import hf_hub_download

    source_dir = RAW / "cuad" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    files = [
        ("CUAD_v1/CUAD_v1.json", "~40 MB"),
        ("CUAD_v1/master_clauses.csv", "~4 MB"),
    ]
    json_path: Path | None = None
    for filename, size_hint in files:
        print(f"  Downloading {filename} ({size_hint}) ...")
        hf_hub_download(
            repo_id="theatticusproject/cuad",
            filename=filename,
            repo_type="dataset",
            local_dir=str(source_dir),
            tqdm_class=tqdm,
        )
        if filename.endswith(".json"):
            json_path = source_dir / filename

    if json_path is None or not json_path.exists():
        raise FileNotFoundError(f"CUAD JSON not found under {source_dir}")

    with json_path.open(encoding="utf-8") as f:
        squad = json.load(f)

    rows = _squad_json_to_rows(squad)
    if not rows:
        raise ValueError("CUAD_v1.json contained no QA rows")

    # Document-level split (avoid same contract in train and test)
    titles = sorted({r["title"] for r in rows})
    rng = random.Random(42)
    rng.shuffle(titles)
    split_at = max(1, int(len(titles) * 0.85))
    train_titles = set(titles[:split_at])
    train_rows = [r for r in rows if r["title"] in train_titles]
    test_rows = [r for r in rows if r["title"] not in train_titles]
    print(
        f"  Parsed {len(rows):,} QA rows from {len(titles)} contracts "
        f"→ train {len(train_rows):,} / test {len(test_rows):,}"
    )
    return _rows_to_dataset_dict(train_rows, test_rows)


def _load_cuad_from_github_zip():
    """Official Atticus train/test JSON from GitHub data.zip (no HF loading scripts)."""
    from datasets import DatasetDict

    url = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
    zip_path = RAW / "cuad" / "source" / "data.zip"
    print(f"  Downloading official CUAD data.zip from GitHub ...")
    download_url_to_file(url, zip_path, "CUAD data.zip")

    train_rows: list[dict] = []
    test_rows: list[dict] = []

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        train_name = next((n for n in names if n.endswith("train_separate_questions.json")), None)
        test_name = next((n for n in names if n.endswith("test.json")), None)
        if not train_name or not test_name:
            raise FileNotFoundError(
                f"Expected train/test JSON in data.zip; found: {names[:10]}..."
            )
        with zf.open(train_name) as f:
            train_rows = _squad_json_to_rows(json.load(f))
        with zf.open(test_name) as f:
            test_rows = _squad_json_to_rows(json.load(f))

    print(f"  Official split → train {len(train_rows):,} / test {len(test_rows):,}")
    return _rows_to_dataset_dict(train_rows, test_rows)


def _load_cuad():
    """Load CUAD without deprecated HF dataset loading scripts."""
    errors: list[str] = []
    for name, loader in (
        ("HF JSON files (theatticusproject/cuad)", _load_cuad_from_hf_files),
        ("GitHub data.zip (official train/test)", _load_cuad_from_github_zip),
    ):
        try:
            print(f"  Trying {name} ...")
            return loader()
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            print(f"  Failed: {exc}")
    raise RuntimeError("Could not load CUAD.\n  - " + "\n  - ".join(errors))


def _ds_cuad() -> Path:
    return load_and_save_dataset(
        "CUAD (Contract Understanding Atticus Dataset)",
        _load_cuad,
        RAW / "cuad",
    )


def _load_ledgar():
    """Load LEDGAR from LexGLUE (namespace required on modern HF Hub)."""
    from datasets import load_dataset

    attempts = [
        ("coastalcph/lex_glue", {"name": "ledgar"}),
        ("coastalcph/lex_glue", {}),  # may error with config hint
        ("lex_glue", {"name": "ledgar"}),
    ]
    errors: list[str] = []
    for repo_id, kwargs in attempts:
        try:
            cfg = kwargs.pop("name", "ledgar")
            print(f"  Trying {repo_id} (config={cfg}) ...")
            return load_dataset(repo_id, cfg, **kwargs)
        except Exception as exc:
            errors.append(f"{repo_id}/{cfg}: {exc}")
    raise RuntimeError(
        "Could not load LEDGAR.\n  - " + "\n  - ".join(errors)
    )


def _ds_ledgar() -> Path:
    return load_and_save_dataset(
        "LEDGAR (LexGLUE)",
        _load_ledgar,
        RAW / "ledgar",
    )


def _load_contract_nli():
    """Load ContractNLI from the first working HuggingFace mirror."""
    from datasets import get_dataset_config_names, load_dataset

    attempts: list[tuple[str, dict]] = [
        ("reuben256/contract-nli", {}),
        ("kiddothe2b/contract-nli", {}),
    ]

    errors: list[str] = []
    for repo_id, kwargs in attempts:
        try:
            print(f"  Trying {repo_id} ...")
            return load_dataset(repo_id, **kwargs)
        except ValueError as exc:
            # kiddothe2b may require a config name — try each config
            if "Config name is missing" in str(exc) or "pick one among" in str(exc):
                try:
                    configs = get_dataset_config_names(repo_id)
                    print(f"  {repo_id} has configs: {configs}")
                    merged = None
                    for cfg in configs:
                        part = load_dataset(repo_id, cfg)
                        if merged is None:
                            merged = part
                        else:
                            for split in part:
                                if split in merged:
                                    from datasets import concatenate_datasets
                                    merged[split] = concatenate_datasets(
                                        [merged[split], part[split]]
                                    )
                                else:
                                    merged[split] = part[split]
                    if merged is not None:
                        print(f"  Loaded {repo_id} ({len(configs)} config(s))")
                        return merged
                except Exception as cfg_exc:
                    errors.append(f"{repo_id} (configs): {cfg_exc}")
            else:
                errors.append(f"{repo_id}: {exc}")
        except Exception as exc:
            errors.append(f"{repo_id}: {exc}")

    raise RuntimeError(
        "Could not load ContractNLI from HuggingFace.\n"
        "Tried: " + ", ".join(r for r, _ in attempts) + "\n"
        "Errors:\n  - " + "\n  - ".join(errors)
    )


def _ds_contract_nli() -> Path:
    return load_and_save_dataset(
        "ContractNLI",
        _load_contract_nli,
        RAW / "contract_nli",
    )


def _ds_maud() -> Path:
    from datasets import load_dataset
    return load_and_save_dataset(
        "MAUD (Merger Agreement Understanding Dataset)",
        lambda: load_dataset("theatticusproject/maud"),
        RAW / "maud",
    )


def _download_bgb_english_official(dest: Path) -> Path:
    """Official English BGB from gesetze-im-internet.de (~1 MB)."""
    urls = [
        "https://www.gesetze-im-internet.de/englisch_bgb/englisch_bgb.html",
        "https://www.gesetze-im-internet.de/englisch_bgb/index.html",
    ]
    errors: list[str] = []
    for url in urls:
        try:
            html_path = dest.with_suffix(".html.part")
            print(f"  Downloading from {url}")
            download_url_to_file(url, html_path, "BGB English HTML")
            html = html_path.read_text(encoding="utf-8", errors="replace")
            text = html_to_plain_text(html)
            html_path.unlink(missing_ok=True)
            if len(text) < 10_000:
                raise ValueError(f"extracted text too short ({len(text)} chars)")
            save_law_text(dest, text, url)
            print(f"  Saved ({fmt_bytes(dest.stat().st_size)}, {len(text):,} chars)")
            return dest
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("Official BGB download failed:\n  - " + "\n  - ".join(errors))


def _download_bgb_from_hf_german(dest_de: Path) -> Path:
    """Fallback: German BGB from HuggingFace (also useful for law corpus)."""
    from datasets import load_dataset

    print("  Trying HuggingFace: nookbe/Buergerliches_Gesetzbuch_BGB (German)...")
    ds = load_dataset("nookbe/Buergerliches_Gesetzbuch_BGB")
    split = ds["train"] if "train" in ds else ds[list(ds.keys())[0]]
    lines: list[str] = []
    for item in tqdm(split, desc="Processing BGB §", unit="section"):
        para = item.get("paragraph") or item.get("section") or ""
        text = item.get("text") or item.get("content") or ""
        lines.append(f"{para}\n{text}\n")
    save_law_text(
        dest_de,
        "\n".join(lines),
        "https://huggingface.co/datasets/nookbe/Buergerliches_Gesetzbuch_BGB",
    )
    print(f"  Saved German BGB → {dest_de} ({fmt_bytes(dest_de.stat().st_size)})")
    return dest_de


def _ds_bgb() -> Path:
    dest_en = RAW / "law_corpus" / "bgb_en.txt"
    dest_de = RAW / "law_corpus" / "bgb_de.txt"

    print(f"\n{'='*60}")
    print("  Law corpus: BGB (German Civil Code)")
    print(f"  Destination (EN): {dest_en}")
    print(f"{'='*60}")

    if dest_en.exists() and dest_en.stat().st_size > 10_000:
        print(f"  BGB EN already present ({fmt_bytes(dest_en.stat().st_size)})")
        return dest_en

    try:
        return _download_bgb_english_official(dest_en)
    except Exception as en_exc:
        print(f"  English BGB failed: {en_exc}")
        print("  Falling back to German BGB from HuggingFace...")
        _download_bgb_from_hf_german(dest_de)
        # Copy German to EN path with notice so downstream ingestion still works
        body = dest_de.read_text(encoding="utf-8")
        notice = (
            "# NOTE: English BGB unavailable; using German BGB text below.\n"
            "# For English, see: https://www.gesetze-im-internet.de/englisch_bgb/\n\n"
        )
        dest_en.write_text(notice + body, encoding="utf-8")
        print(f"  Saved fallback → {dest_en} ({fmt_bytes(dest_en.stat().st_size)})")
        return dest_en


def _ds_gdpr() -> Path:
    dest = RAW / "law_corpus" / "gdpr_en.txt"
    if dest.exists() and dest.stat().st_size > 5000:
        print(f"\n  GDPR already present ({fmt_bytes(dest.stat().st_size)}) → {dest}")
        return dest

    # EUR-Lex HTML export — best-effort automated download
    url = (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/"
        "?uri=CELEX:32016R0679&from=EN"
    )
    print(f"\n{'='*60}")
    print("  Law corpus: GDPR (EUR-Lex)")
    print(f"  Destination: {dest}")
    print(f"{'='*60}")
    try:
        download_url_to_file(url, dest.with_suffix(".html"), "GDPR HTML")
        html = dest.with_suffix(".html").read_text(encoding="utf-8", errors="replace")
        text = html_to_plain_text(html)
        save_law_text(dest, text, url)
        dest.with_suffix(".html").unlink(missing_ok=True)
        print(f"  Saved ({fmt_bytes(dest.stat().st_size)})")
    except Exception as exc:
        print(
            f"  Auto-download failed: {exc}\n"
            "  Manual: save GDPR full text to:\n"
            f"    {dest}\n"
            "  URL: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679"
        )
    return dest


def _ds_bdsg() -> Path:
    dest = RAW / "law_corpus" / "bdsg_de.txt"
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"\n  BDSG already present ({fmt_bytes(dest.stat().st_size)}) → {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# BDSG (Bundesdatenschutzgesetz) — curated excerpts for JurisGuard seed corpus\n\n"
        "§ 26 BDSG — Datenverarbeitung im Beschäftigungsverhältnis\n"
        "Die Verarbeitung personenbezogener Daten eines Beschäftigten ist zulässig, wenn sie für die Begründung, "
        "Durchführung oder Beendigung des Beschäftigungsverhältnisses erforderlich ist.\n\n"
        "§ 22 BDSG — Verarbeitung für andere Zwecke\n"
        "Eine Verarbeitung für andere Zwecke ist zulässig, wenn sie aufgrund einer Rechtsvorschrift erforderlich ist "
        "oder die betroffene Person eingewilligt hat.\n"
    )
    save_law_text(dest, body, "https://www.gesetze-im-internet.de/bdsg_2018/")
    print(f"  Saved BDSG seed → {dest}")
    return dest


def _ds_eu_ai_act() -> Path:
    dest = RAW / "law_corpus" / "eu_ai_act_en.txt"
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"\n  EU AI Act already present ({fmt_bytes(dest.stat().st_size)}) → {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# EU Artificial Intelligence Act — curated excerpts\n\n"
        "Article 5 — Prohibited AI practices\n"
        "AI systems that deploy subliminal techniques beyond a person's consciousness or exploit vulnerabilities "
        "of specific groups shall be prohibited.\n\n"
        "Article 6 — Classification of high-risk AI systems\n"
        "AI systems referred to in Annex III shall be considered high-risk if they pose a significant risk of harm "
        "to health, safety, or fundamental rights.\n\n"
        "Article 9 — Risk management system\n"
        "Providers of high-risk AI systems shall establish, implement, document and maintain a risk management system.\n"
    )
    save_law_text(dest, body, "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689")
    print(f"  Saved EU AI Act seed → {dest}")
    return dest


DATASET_REGISTRY: dict[str, DatasetSpec] = {
    "cuad": DatasetSpec("cuad", "CUAD", "~500 MB", _ds_cuad),
    "ledgar": DatasetSpec("ledgar", "LEDGAR", "~200 MB", _ds_ledgar),
    "contract_nli": DatasetSpec("contract_nli", "ContractNLI", "~50 MB", _ds_contract_nli),
    "maud": DatasetSpec("maud", "MAUD", "~300 MB", _ds_maud),
    "bgb": DatasetSpec("bgb", "BGB English", "~5 MB", _ds_bgb),
    "gdpr": DatasetSpec("gdpr", "GDPR English", "~1 MB", _ds_gdpr),
    "bdsg": DatasetSpec("bdsg", "BDSG German excerpts", "~50 KB", _ds_bdsg),
    "eu_ai_act": DatasetSpec("eu_ai_act", "EU AI Act excerpts", "~50 KB", _ds_eu_ai_act),
}


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

@dataclass
class ModelSpec:
    key: str
    label: str
    est_size: str
    fn: Callable[[], None]


def _model_bge_m3() -> None:
    hf_snapshot(
        "BAAI/bge-m3",
        MODELS / "bge-m3",
        allow_patterns=BGE_M3_ALLOW,
        ignore_patterns=HF_IGNORE_HEAVY,
    )


def _model_reranker() -> None:
    hf_snapshot(
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        MODELS / "reranker",
        allow_patterns=RERANKER_ALLOW,
        ignore_patterns=HF_IGNORE_HEAVY,
    )


def _model_phi35_ollama() -> None:
    """Pull Phi-3.5-mini for local inference via Ollama (~2.3 GB)."""
    ollama_pull("phi3.5")


def _model_phi35_tokenizer() -> None:
    """Small tokenizer/config files only (for local training data prep)."""
    hf_snapshot(
        "microsoft/Phi-3.5-mini-instruct",
        MODELS / "phi-3.5-mini-instruct",
        allow_patterns=[
            "*.json",
            "tokenizer*",
            "*.model",
            "*.txt",
            "special_tokens_map.json",
        ],
    )


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "bge-m3": ModelSpec("bge-m3", "BAAI/bge-m3 embeddings", "~2.2 GB (PyTorch only)", _model_bge_m3),
    "reranker": ModelSpec(
        "reranker", "ms-marco MiniLM reranker", "~84 MB", _model_reranker
    ),
    "phi35-ollama": ModelSpec(
        "phi35-ollama", "Phi-3.5-mini via Ollama (inference)", "~2.3 GB", _model_phi35_ollama
    ),
    "phi35-tokenizer": ModelSpec(
        "phi35-tokenizer",
        "Phi-3.5-mini tokenizer only (no weights)",
        "~5 MB",
        _model_phi35_tokenizer,
    ),
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def print_registry() -> None:
    print("\nDatasets (--datasets):")
    for spec in DATASET_REGISTRY.values():
        print(f"  {spec.key:16} {spec.label:40} est. {spec.est_size}")
    print("\nModels (--models):")
    for spec in MODEL_REGISTRY.values():
        print(f"  {spec.key:16} {spec.label:40} est. {spec.est_size}")
    print("\nStorage layout:")
    print(f"  Datasets → {RAW}/")
    print(f"  Models   → {MODELS}/")
    print(f"  Ollama   → data/models/ollama/ (via ollama pull, or Docker volume)")


def run_batch(
    registry: dict,
    keys: list[str],
    label: str,
    *,
    skip_complete: bool = True,
) -> int:
    errors: list[str] = []
    total = len(keys)

    print(f"\n{'#'*60}")
    print(f"  {label}: {total} item(s)")
    print(f"{'#'*60}")

    for i, key in enumerate(keys, 1):
        spec = registry[key]
        if skip_complete and key in MODEL_REGISTRY and is_model_complete(key):
            print(f"\n>>> [{i}/{total}] {spec.label} — already complete, skipping")
            print(f"✓ {spec.key} skipped (use --force to re-download)")
            continue
        print(f"\n>>> [{i}/{total}] {spec.label} (est. {spec.est_size})")
        t0 = time.time()
        try:
            spec.fn()
            elapsed = time.time() - t0
            print(f"✓ {spec.key} done in {elapsed:.1f}s")
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"✗ {spec.key} FAILED after {elapsed:.1f}s: {exc}", file=sys.stderr)
            errors.append(f"{key}: {exc}")

    print(f"\n{'='*60}")
    if errors:
        print(f"  Finished with {len(errors)} error(s):")
        for e in errors:
            print(f"    - {e}")
        return 1
    print(f"  All {total} {label.lower()} completed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download JurisGuard V2 datasets and models with progress bars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--list", action="store_true", help="List available items")
    parser.add_argument("--datasets", action="store_true", help="Download datasets")
    parser.add_argument("--models", action="store_true", help="Download models")
    parser.add_argument("--all", action="store_true", help="Download datasets + models")
    parser.add_argument(
        "--only",
        help="Comma-separated keys (e.g. cuad,bge-m3). Use --list to see keys.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if model already looks complete on disk",
    )
    args = parser.parse_args()

    if args.list:
        print_registry()
        return 0

    if not (args.datasets or args.models or args.all):
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/download_assets.py --list")
        print("  python scripts/download_assets.py --datasets --only cuad")
        print("  python scripts/download_assets.py --models")
        print("  python scripts/download_assets.py --all")
        return 0

    print("\n--- HuggingFace auth ---")
    setup_hf_auth()

    exit_code = 0
    only_keys = [k.strip() for k in args.only.split(",")] if args.only else None

    if args.datasets or args.all:
        keys = only_keys if only_keys else list(DATASET_REGISTRY.keys())
        if only_keys:
            bad = [k for k in keys if k not in DATASET_REGISTRY]
            if bad:
                print(f"Unknown dataset keys: {bad}. Use --list.", file=sys.stderr)
                return 1
            keys = [k for k in keys if k in DATASET_REGISTRY]
        elif args.all and only_keys:
            keys = [k for k in only_keys if k in DATASET_REGISTRY]
        if keys:
            exit_code |= run_batch(DATASET_REGISTRY, keys, "Datasets")

    if args.models or args.all:
        default_models = ["bge-m3", "reranker", "phi35-ollama"]
        if only_keys:
            keys = [k for k in only_keys if k in MODEL_REGISTRY]
            if not keys and (args.models or args.all):
                # --only might have been dataset keys only
                if args.models and not args.datasets:
                    bad = [k for k in only_keys if k not in MODEL_REGISTRY]
                    if bad:
                        print(f"Unknown model keys: {bad}. Use --list.", file=sys.stderr)
                        return 1
        else:
            keys = default_models
        if keys:
            exit_code |= run_batch(
                MODEL_REGISTRY, keys, "Models", skip_complete=not args.force
            )

    # Disk usage summary
    if RAW.exists():
        raw_bytes = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file())
        print(f"\n  data/raw/   total: {fmt_bytes(raw_bytes)}")
    if MODELS.exists():
        mod_bytes = sum(f.stat().st_size for f in MODELS.rglob("*") if f.is_file())
        print(f"  data/models/ total: {fmt_bytes(mod_bytes)}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
