# Training checkpoints (local copy from Drive)

## Your download location

**Windows:**
```
C:\Users\mhamd\Desktop\PROJECT\juris\training
```

**WSL (same folder):**
```
/mnt/c/Users/mhamd/Desktop/PROJECT/juris/training
```

## Important folders inside `training/`

| Folder / file | Purpose |
|---------------|---------|
| `checkpoint_RESUME/` | **Resume Colab from here** (step ~3800+) |
| `checkpoints/checkpoint-*` | Rolling HF saves |
| `tokenized_cache/` | Skip re-tokenizing on resume |
| `RUN_MANIFEST.json` | Last step, status, loss history |
| `train_final.jsonl` / `eval_set.jsonl` | Training data (if copied) |
| `gguf/` | Final Ollama export (after Cell 8 — not yet) |

**Do not delete `checkpoint_RESUME/` until training reaches ~11,800 steps and Cell 8 completes.**

---

## Resume fine-tuning on Colab (when GPU limit resets)

1. Re-upload is **not** required if files are still on Drive at `My Drive/JurisGuard/training/`.
2. If Drive was cleared, re-upload `training/` (or at least `checkpoint_RESUME/`, `tokenized_cache/`, JSONL files).
3. Open `v2/notebooks/phi35_legal_finetune.ipynb` → T4 GPU → run cells 1–7.
4. Expect: `↻ RESUMING from: .../checkpoint_RESUME`

Local copy on Desktop is a **backup**; Colab reads from Drive, not your PC.

---

## Using partial weights while building the app (now)

Until full training finishes:

1. **Develop with base Ollama model:**
   ```bash
   ollama pull phi3.5
   ```
   Set in `v2/.env`: `OLLAMA_MODEL=phi3.5`

2. **After Cell 8 (GGUF export):** download `training/gguf/*.gguf`, create Ollama model:
   ```bash
   ollama create jurisguard-dev -f Modelfile
   ```
   Set `OLLAMA_MODEL=jurisguard-dev`

3. **After full training completes:** swap to `OLLAMA_MODEL=jurisguard-v1` (same Modelfile flow, new GGUF).

Only the env var + `ollama create` changes — backend/RAG/frontend stay the same.

---

## Point Docker at your training folder (optional)

In `v2/.env`:
```env
TRAINING_DIR=/mnt/c/Users/mhamd/Desktop/PROJECT/juris/training
```

The API `/api/v1/status` endpoint reads `RUN_MANIFEST.json` from this path for progress display.
