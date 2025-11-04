#!/bin/bash

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🧪 Running BDD Tests for VN Market Service${NC}"
echo -e "${BLUE}==========================================${NC}"

# Check if service is running
if ! curl -s http://localhost:8765/health > /dev/null; then
    echo "❌ Service not running on port 8765"
    echo "Please start with: ./start.sh"
    exit 1
fi

echo "✅ Service is running"

# Set up paths
PROJECT_ROOT="$(cd "$(dirname "$0")/../" && pwd)"
TESTS_DIR="$PROJECT_ROOT/tests"
REPORT_DIR="$TESTS_DIR/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create reports directory
mkdir -p "$REPORT_DIR"

# Run tests from test directory
cd "$TESTS_DIR" && python3 -m behave --tags=@regression features

# Move pretty.output to reports folder if it exists
if [ -f "$TESTS_DIR/pretty.output" ]; then
    mv "$TESTS_DIR/pretty.output" "$REPORT_DIR/pretty_output_${TIMESTAMP}.txt"
    echo -e "${YELLOW}Moved pretty output to: $REPORT_DIR/pretty_output_${TIMESTAMP}.txt${NC}"
fi

echo ""
echo -e "${GREEN}✨ BDD tests completed!${NC}"
