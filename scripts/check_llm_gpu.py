#!/usr/bin/env python3
"""Fail unless each configured LLM is fully on the GPU and Ollama's runner isn't building a RAM cache."""
from __future__ import annotations

import json
import os
import subprocess
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


def gpu_share(model: str, options: dict, keep_alive: str = "-1m") -> float:
    """Return the fraction of the loaded model held in GPU memory."""
    body = {"model": model, "prompt": "ok", "stream": False, "options": options, "keep_alive": keep_alive}
    # Ollama holds one model at a time, so a request from the running app can swap this one out before it is read.
    for _attempt in range(3):
        post("/api/generate", body)
        with urllib.request.urlopen(OLLAMA_URL + "/api/ps") as response:
            running = json.load(response)["models"]
        entry = next((item for item in running if item["model"] == model), None)
        if entry:
            return entry["size_vram"] / entry["size"]
    raise RuntimeError(f"{model} kept being swapped out by other requests, so its GPU share couldn't be read")


def prompt_cache_disabled() -> bool | None:
    """Read the local runner's environment. None when Ollama runs elsewhere, so this can't be checked."""
    found = subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True, text=True).stdout.split()
    if not found:
        return None
    environment = Path(f"/proc/{found[0]}/environ").read_bytes().split(b"\0")
    return b"LLAMA_ARG_CACHE_RAM=0" in environment


def main() -> int:
    config = {**env_file_values(), **os.environ}
    options = {"num_predict": 1, "num_ctx": int(config.get("OLLAMA_NUM_CTX", 4096)), "use_mmap": False}
    if config.get("OLLAMA_NUM_GPU"):
        options["num_gpu"] = int(config["OLLAMA_NUM_GPU"])
    models = [config[key] for key in ("OLLAMA_MODEL", "OLLAMA_AUX_MODEL") if config.get(key)]
    failed = False
    # Without the app's keep-alive, this check would leave the model set to unload after Ollama's 5-minute default.
    keep_alive = config.get("OLLAMA_KEEP_ALIVE", "-1m")
    for model in models:
        share = gpu_share(model, options, keep_alive if model == models[0] else "5m")
        print(f"{model}: {share:.0%} on GPU")
        failed = failed or share < 1.0
    # Reload the main model: this is the state the app runs in, and the aux load must not have broken it.
    if len(models) > 1:
        share = gpu_share(models[0], options, keep_alive)
        print(f"{models[0]} after aux model: {share:.0%} on GPU")
        failed = failed or share < 1.0
    if failed:
        print("FAIL: part of the LLM is on the CPU. Free GPU memory or choose a smaller model.")
    cache_off = prompt_cache_disabled()
    if cache_off is None:
        print("Prompt cache not checked: no local llama-server process")
    elif not cache_off:
        print("FAIL: start Ollama with LLAMA_ARG_CACHE_RAM=0, or its prompt cache grows to 8 GB of RAM.")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
