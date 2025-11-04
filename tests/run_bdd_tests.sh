#!/bin/bash

# BDD Testing Script for VN Market Service

echo "🧪 BDD Testing for VN Market Service"
echo "=================================="

# Check if service is running
echo "📡 Checking if service is running on port 8765..."
if curl -s http://localhost:8765/health > /dev/null; then
    echo "✅ Service is running"
else
    echo "❌ Service is not running. Please start the service first:"
    echo "   ./start.sh"
    echo "   or"
    echo "   python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765"
    exit 1
fi

# Install dependencies if needed
echo "📦 Checking BDD dependencies..."
if ! python3 -c "import behave" 2>/dev/null; then
    echo "📥 Installing BDD dependencies..."
    python3 -m pip install behave httpx pytest
fi

# Run smoke tests
echo "🚀 Running smoke tests..."
echo ""
cd "$(dirname "$0")" && python3 -m behave --tags=@smoke --format=pretty features

echo ""
echo "📊 Test Summary:"
echo "   - Smoke tests verify core functionality"
echo "   - All 4 asset types tested (Stocks, Funds, Indices, Gold)"
echo "   - Each test covers: Search → Quote → History flow"
echo ""
echo "🔧 Additional test commands:"
echo "   Run all tests:     python3 -m behave test/features"
echo "   Run error tests:    python3 -m behave --tags=@error-handling test/features"
echo "   Run regression:     python3 -m behave --tags=@regression test/features"
echo "   Generate reports:    python3 -m behave --format=html5 --outfile=reports/test_report.html test/features"