#!/bin/bash
# 🚀 JurisGuardRAG Auto-Setup Script
# Runs on any new PC to set up the entire project with one command

set -e  # Exit on any error

echo "🎯 JurisGuardRAG Setup Script"
echo "=================================="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first:"
    echo "   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
    exit 1
fi

echo "✅ Docker found"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Installing..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

echo "✅ Docker Compose found"

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+:"
    echo "   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -"
    echo "   sudo apt-get install -y nodejs"
    exit 1
fi

echo "✅ Node.js found ($(node --version))"

# Start backend
echo ""
echo "🐳 Starting backend (Docker)..."
docker-compose up -d
sleep 5

# Check backend health
BACKEND_READY=0
for i in {1..30}; do
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        BACKEND_READY=1
        break
    fi
    echo "⏳ Waiting for backend... ($i/30)"
    sleep 1
done

if [ $BACKEND_READY -eq 0 ]; then
    echo "❌ Backend failed to start. Check logs:"
    docker-compose logs backend
    exit 1
fi

echo "✅ Backend running on http://localhost:8000"

# Install frontend
echo ""
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps > /dev/null 2>&1
cd ..
echo "✅ Frontend dependencies installed"

# Print next steps
echo ""
echo "✨ Setup Complete!"
echo "=================================="
echo ""
echo "🚀 To start the frontend:"
echo "   cd frontend && npm run dev"
echo ""
echo "📍 Open your browser:"
echo "   http://localhost:5173"
echo ""
echo "📤 Upload a PDF and click 'Run Evaluation'"
echo ""
echo "✅ Verify everything:"
echo "   Backend: curl http://localhost:8000/"
echo "   Tests:   curl -X POST http://localhost:8000/evaluate"
echo ""
echo "🛑 To stop everything:"
echo "   docker-compose down"
echo ""
