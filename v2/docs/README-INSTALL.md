# JurisGuard V2 — Air-Gap Installation Guide

Install JurisGuard on an offline Ubuntu 22.04+ host with Docker Compose v2.

## Prerequisites

- Docker Engine 24+ and Compose v2
- 16 GB RAM minimum (8 GB for air-gap minimum)
- 20 GB free disk (40 GB+ with full bundle)
- Optional: NVIDIA GPU + `nvidia-container-toolkit` for GPU compose profile
- Optional: Native [Ollama](https://ollama.com) with `mistral:7b-instruct-q4_K_M` on the host

## Quick install (from bundle)

1. Transfer `juris-airgap-*.tar.zst` to the target host
2. Extract: `tar -I zstd -xf juris-airgap-*.tar.zst`
3. `cd juris-airgap-*`
4. Run `./scripts/verify_airgap_bundle.sh` (checksums)
5. Run `./scripts/setup.sh` and follow prompts
6. Open **http://localhost:8002/app**

## Manual install (from git)

```bash
cd v2
cp .env.airgap.example .env
# Edit AUTH_SECRET_KEY, OLLAMA_BASE_URL
make models
make download-law
make ingest-law
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
make migrate
python3 scripts/seed_admin.py --email admin@firm.local --password 'YourSecurePass123!' --org-name 'Your Firm'
```

## Ollama (recommended for latency)

On the host (not in Docker):

```bash
bash scripts/setup_ollama_gpu.sh
```

Set in `.env`:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
LLM_PROVIDER=ollama
```

## Verify

```bash
curl http://localhost:8002/health
make eval-offline          # no LLM required
make airgap-eval           # requires Ollama + strict ≥95% logical gate
make test-unit
make e2e
```

## Windows (PowerShell)

Use `scripts/setup.ps1` for Docker Desktop on Windows without WSL.

## Support

See `docs/PROJECT_MASTER_HANDOFF.md` and `docs/RUNBOOK.md`.
