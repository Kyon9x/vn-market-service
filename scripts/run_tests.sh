#!/bin/bash

# Run Behave tests with pretty output saved to file + HTML report
# Usage: ./run_tests.sh [@tag]
# Examples:
#   ./run_tests.sh @regression      # Run regression tests
#   ./run_tests.sh @smoke            # Run smoke tests
#   ./run_tests.sh "" behave-html    # Run all tests

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Parameters
TAG="${1:-@regression}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$PROJECT_ROOT/tests/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create reports directory
mkdir -p "$REPORT_DIR"

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}Running BDD Tests${NC}"
echo -e "${BLUE}=====================================${NC}\n"

echo -e "${YELLOW}Tag:${NC} $TAG"
echo -e "${YELLOW}Report Dir:${NC} $REPORT_DIR\n"

# Run tests with pretty output saved to file + HTML
PRETTY_OUTPUT="$REPORT_DIR/pretty_output_${TIMESTAMP}.txt"
HTML_REPORT="$REPORT_DIR/test_report_${TIMESTAMP}.html"

echo -e "${YELLOW}Running tests and saving to:${NC}"
echo -e "  - Pretty Output: $PRETTY_OUTPUT"
echo -e "  - HTML Report: $HTML_REPORT\n"

cd "$PROJECT_ROOT"

# Run with pretty formatter (console output) AND save to file
.venv/bin/python3 -m behave \
    --tags="$TAG" \
    tests/features \
    | tee "$PRETTY_OUTPUT"

echo -e "\n${YELLOW}Generating HTML report...${NC}\n"

# Also generate HTML report
.venv/bin/python3 -m behave \
    --tags="$TAG" \
    --format=behave_html_formatter:HTMLFormatter \
    --outfile="$HTML_REPORT" \
    tests/features > /dev/null 2>&1 || true

echo -e "${GREEN}✓ Tests completed!${NC}\n"

# Create summary
echo -e "${BLUE}Generated Reports:${NC}"
echo -e "  1. Pretty Output: $PRETTY_OUTPUT"
echo -e "  2. HTML Report:   $HTML_REPORT\n"

# Show file sizes
echo -e "${YELLOW}File Sizes:${NC}"
ls -lh "$PRETTY_OUTPUT" "$HTML_REPORT" 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'

echo -e "\n${YELLOW}Quick Links:${NC}"
echo -e "  View pretty output: cat $PRETTY_OUTPUT"
echo -e "  View HTML report:   open $HTML_REPORT"
echo -e "  Latest report:      open \$(ls -t $REPORT_DIR/test_report_*.html 2>/dev/null | head -1)\n"

# Optionally open HTML report
if [ "$OPEN_REPORT" != "false" ]; then
    echo -e "${YELLOW}Opening HTML report in browser...${NC}\n"
    open "$HTML_REPORT" 2>/dev/null || echo "Please open: $HTML_REPORT"
fi

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Done!${NC}"
echo -e "${GREEN}=====================================${NC}\n"
