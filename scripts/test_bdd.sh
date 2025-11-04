#!/bin/bash

# Simple BDD Test Runner
echo "🧪 Running BDD Tests for VN Market Service"
echo "=========================================="

# Check if service is running
if ! curl -s http://localhost:8765/health > /dev/null; then
    echo "❌ Service not running on port 8765"
    echo "Please start with: ./start.sh"
    exit 1
fi

echo "✅ Service is running"

# Run tests from test directory
cd ../tests && python3 -m behave --tags=@regression features

echo ""
echo "✨ BDD tests completed!"