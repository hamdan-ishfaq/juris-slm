#!/usr/bin/env bash
# Phase 0.1 — GPU & Docker verification for JurisGuard V2
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass=0
fail=0
warn=0

echo "========================================"
echo " JurisGuard V2 — Environment Verification"
echo "========================================"
echo

# 1. NVIDIA driver in WSL
echo "[1/5] WSL GPU (nvidia-smi)"
if nvidia-smi >/dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
    echo -e "  ${GREEN}PASS${NC} — $GPU_NAME ($GPU_MEM)"
    pass=$((pass + 1))
else
    echo -e "  ${RED}FAIL${NC} — nvidia-smi not available"
    echo "  Fix: Install NVIDIA driver on Windows + WSL2 CUDA support"
    fail=$((fail + 1))
fi

# 2. Minimum VRAM
echo
echo "[2/5] VRAM capacity (>= 6144 MiB)"
VRAM_MIB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
if [[ -n "${VRAM_MIB:-}" ]] && [[ "$VRAM_MIB" -ge 6144 ]]; then
    echo -e "  ${GREEN}PASS${NC} — ${VRAM_MIB} MiB"
    pass=$((pass + 1))
elif [[ -n "${VRAM_MIB:-}" ]] && [[ "$VRAM_MIB" -ge 5800 ]]; then
    echo -e "  ${GREEN}PASS${NC} — ${VRAM_MIB} MiB (RTX 4050 reports ~6141 MiB — OK)"
    pass=$((pass + 1))
else
    echo -e "  ${RED}FAIL${NC} — insufficient VRAM (${VRAM_MIB:-unknown} MiB)"
    fail=$((fail + 1))
fi

# 3. Docker available
echo
echo "[3/5] Docker daemon"
if docker info >/dev/null 2>&1; then
    echo -e "  ${GREEN}PASS${NC}"
    pass=$((pass + 1))
else
    echo -e "  ${RED}FAIL${NC} — Docker not running"
    fail=$((fail + 1))
fi

# 4. Docker GPU passthrough
echo
echo "[4/5] Docker GPU passthrough (--gpus all)"
CUDA_IMAGE="nvidia/cuda:12.9.2-base-ubuntu22.04"
GPU_OK=0
if docker run --rm --gpus all "$CUDA_IMAGE" nvidia-smi >/dev/null 2>&1; then
    GPU_OK=1
elif docker run --rm --gpus all ollama/ollama nvidia-smi >/dev/null 2>&1; then
    GPU_OK=1
    echo "  (verified via ollama/ollama image)"
fi

if [[ "$GPU_OK" -eq 1 ]]; then
    echo -e "  ${GREEN}PASS${NC}"
    pass=$((pass + 1))
else
    echo -e "  ${RED}FAIL${NC}"
    echo "  Fix: Install NVIDIA Container Toolkit in WSL:"
    echo "    sudo apt-get install -y nvidia-container-toolkit"
    echo "    sudo nvidia-ctk runtime configure --runtime=docker"
    echo "    sudo systemctl restart docker"
    fail=$((fail + 1))
fi

# 5. System RAM (warn only — does not block Phase 0 downloads / Colab training)
echo
echo "[5/5] WSL RAM (>= 12 GB recommended for full Docker stack)"
RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
if [[ "${RAM_GB:-0}" -ge 12 ]]; then
    echo -e "  ${GREEN}PASS${NC} — ${RAM_GB} GB"
    pass=$((pass + 1))
elif [[ "${RAM_GB:-0}" -ge 7 ]]; then
    echo -e "  ${YELLOW}WARN${NC} — ${RAM_GB} GB visible (OK for downloads; fix before Phase 2 Docker stack)"
    echo "  Fix: C:\\Users\\<you>\\.wslconfig → memory=12GB, then wsl --shutdown + reboot Windows"
    warn=$((warn + 1))
    pass=$((pass + 1))
else
    echo -e "  ${RED}FAIL${NC} — only ${RAM_GB} GB visible to WSL"
    fail=$((fail + 1))
fi

echo
echo "========================================"
echo -e " Results: ${GREEN}${pass} passed${NC}, ${RED}${fail} failed${NC}, ${YELLOW}${warn} warnings${NC}"
echo "========================================"

if [[ "$fail" -eq 0 ]]; then
    echo -e "${GREEN}Phase 0.1 COMPLETE — environment ready for V2 build${NC}"
    exit 0
else
    echo -e "${RED}Phase 0.1 INCOMPLETE — fix failures above before continuing${NC}"
    exit 1
fi
