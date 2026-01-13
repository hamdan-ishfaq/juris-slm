#!/usr/bin/env bash
set -euo pipefail
echo "Creating conda env from juris_env_full.yml (name inside file used)."
if [ ! -f ./juris_env_full.yml ]; then
  echo "ERROR: ./juris_env_full.yml not found. Place it in repo root."
  exit 1
fi

# Create env (if you prefer a specific name use: -n juris_dev)
conda env create -f ./juris_env_full.yml || echo "Environment might already exist."

# Optional: create a pip requirements snapshot (run while env is active)
echo "To produce a pip requirements.txt, activate the env and run:"
echo "  conda activate <env_name_from_yml>"
echo "  python -m pip freeze > requirements.txt"
