#!/usr/bin/env python3
"""Load each configured LLM with the app's settings and fail unless all of it is on the GPU."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
OLLAMA_URL = "http://localhost:11434"


def env_file_values() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    lines = (line.strip() for line in ENV_FILE.read_text().splitlines())
    pairs = (line.split("=", 1) for line in lines if line and not line.startswith("#") and "=" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def post(path: str, body: dict) -> dict:
    request = urllib.request.Request(
        OLLAMA_URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def gpu_share(model: str, options: dict) -> float:
    """Return the fraction of the loaded model held in GPU memory."""
    post("/api/generate", {"model": model, "prompt": "ok", "stream": False, "options": options})
    with urllib.request.urlopen(OLLAMA_URL + "/api/ps") as response:
        running = json.load(response)["models"]
    entry = next(item for item in running if item["model"] == model)
    return entry["size_vram"] / entry["size"]


def main() -> int:
    config = {**env_file_values(), **os.environ}
    options = {"num_predict": 1, "num_ctx": int(config.get("OLLAMA_NUM_CTX", 4096))}
    if config.get("OLLAMA_NUM_GPU"):
        options["num_gpu"] = int(config["OLLAMA_NUM_GPU"])
    models = [config[key] for key in ("OLLAMA_MODEL", "OLLAMA_AUX_MODEL") if config.get(key)]
    failed = False
    for model in models:
        share = gpu_share(model, options)
        print(f"{model}: {share:.0%} on GPU")
        failed = failed or share < 1.0
    # Reload the main model: this is the state the app runs in, and the aux load must not have broken it.
    if len(models) > 1:
        share = gpu_share(models[0], options)
        print(f"{models[0]} after aux model: {share:.0%} on GPU")
        failed = failed or share < 1.0
    if failed:
        print("FAIL: part of the LLM is on the CPU. Free GPU memory or choose a smaller model.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
