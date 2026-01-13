# Juris — Full Project (backend + frontend)

## Quickstart (recommended)
1. Clone repo.
2. Create conda env:
   - `conda env create -f juris_env_full.yml`
   - `conda activate <envname from yml>`
3. Download model/adapters & tokenizer:
   - `bash scripts/download_models.sh`
     - uses Kaggle (if `kaggle` CLI configured) or HF_TOKEN for HuggingFace
4. Start server:
   - `cd backend`
   - `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`

## Notes
- **Large weights**: base model weights (many GB) should *not* be committed to git. Use the download script to pull them.
- The engine expects the adapter/tokenizer in `./juris_local_proof` relative to the backend folder.
- If you host adapters in Hugging Face or Kaggle, update `scripts/download_models.sh` accordingly.

