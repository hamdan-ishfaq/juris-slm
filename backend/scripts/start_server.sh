#!/bin/bash
# Start backend server for rate limit testing

cd /home/mhamd/juris_full_project/backend
source /home/mhamd/miniconda3/bin/activate juris_dev

export AUTH_SECRET_KEY="test-secret-key-12345678901234567890"
export DATABASE_URL="postgresql+asyncpg://juris:juris_password@localhost:5432/juris_db"

echo "Starting backend server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
