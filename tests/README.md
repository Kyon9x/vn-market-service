# BDD Testing for VN Market Service

This directory contains Behavior-Driven Development (BDD) tests for the VN Market Service API.

## 📋 Overview

The BDD framework tests the core functionality of the Vietnamese market data service using natural language scenarios that are readable by both technical and non-technical stakeholders.

## 🏗️ Architecture

```
tests/
├── features/
│   ├── market_data_api.feature    # Main API endpoint tests
│   ├── error_handling.feature      # Error scenario tests
│   ├── environment.py            # Test setup/teardown hooks
│   ├── steps/
│   │   ├── given_steps.py        # Setup step definitions
│   │   ├── when_steps.py         # Action step definitions
│   │   └── then_steps.py        # Verification step definitions
│   └── support/
│       ├── api_client.py         # HTTP client wrapper
│       ├── data_utils.py         # Test data generators
│       └── assertions.py         # Custom assertions
├── behave.ini                 # Behave configuration
├── docker-compose.bdd.yml      # Docker testing setup
├── Dockerfile.bdd              # BDD Docker image
└── run_bdd_tests.sh           # Test runner script
```

## 🎯 Test Coverage

### Core Workflows (4 Asset Types)

Each asset type follows the same test pattern:
1. **Search** → Find assets by query
2. **Quote** → Get latest price/NAV data  
3. **History** → Get historical data (365 days)

| Asset Type | Search Query | Quote Endpoint | History Endpoint |
|------------|--------------|----------------|------------------|
| **Stocks** | VNM, FPT, ACB | `/quote/{symbol}` | `/history/{symbol}` |
| **Funds** | VFMVF1, VFMVN30 | `/quote/{symbol}` | `/history/{symbol}` |
| **Indices** | VNINDEX, HNXINDEX | `/quote/{symbol}` | `/history/{symbol}` |
| **Gold** | SJC, BTMC | `/quote/{symbol}` | `/history/{symbol}` |

### Test Scenarios

#### Smoke Tests (`@smoke`)
- ✅ Stock data retrieval workflow
- ✅ Fund data retrieval workflow  
- ✅ Index data retrieval workflow
- ✅ Gold price retrieval workflow

#### Error Handling (`@error-handling`)
- ❌ Invalid symbol handling
- ❌ Empty search query handling
- ❌ Invalid date range handling
- ❌ Service unavailable simulation

#### Regression Tests (`@regression`)
- 🔄 Asset type data retrieval (parameterized)

## 🚀 Running Tests

### Prerequisites
```bash
# Install BDD dependencies
python3 -m pip install behave httpx pytest

# Start the service
./start.sh
# or
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

### Quick Start
```bash
# Run smoke tests (recommended for daily validation)
./run_bdd_tests.sh

# Or manually:
python3 -m behave --tags=@smoke tests/features
```

### Test Commands

```bash
# Run all tests
python3 -m behave test/features

# Run specific test categories
python3 -m behave --tags=@smoke test/features
python3 -m behave --tags=@error-handling test/features  
python3 -m behave --tags=@regression tests/features

# Run specific feature
python3 -m behave test/features/market_data_api.feature

# Generate HTML report
python3 -m behave --tags=@regression --format=html5 --outfile=tests/reports/test_report.html tests/features

# Generate JSON report for CI/CD
python3 -m behave --format=json5 --outfile=tests/reports/test_report.json5 tests/features

# Run with verbose output
python3 -m behave -v test/features

# Dry run (syntax check)
python3 -m behave --dry-run test/features
```

## 🐳 Docker Testing

### Local Docker Testing
```bash
# Build and run BDD tests
docker-compose -f test/docker-compose.bdd.yml up --abort-on-container-exit

# View logs
docker-compose -f test/docker-compose.bdd.yml logs -f bdd-tests
```

### Service Health Check
The BDD framework automatically:
- Waits for service to be healthy (max 60 seconds)
- Validates health endpoint response
- Cleans up resources between tests

## 📊 Reports

### Console Output
```
1 feature passed, 0 failed, 0 skipped
4 scenarios passed, 0 failed, 0 skipped  
12 steps passed, 0 failed, 0 skipped
Took 0m45.123s
```

### HTML Reports
Generate interactive HTML reports:
```bash
python3 -m behave --format=html5 --outfile=reports/test_report.html
open reports/test_report.html
```

### JSON Reports (CI/CD)
```bash
python3 -m behave --format=json5 --outfile=reports/test_report.json5
```

## 🔧 Configuration

### Environment Variables
- `TEST_BASE_URL`: Service URL (default: `http://localhost:8765`)

### behave.ini Configuration
```ini
[behave]
format = pretty
stdout_capture = False
stderr_capture = False
show_skipped = True
show_timings = True
paths = features
tags = ~@wip
```

## 📝 Writing New Scenarios

### 1. Add to Feature File
```gherkin
@new-feature
Scenario: Custom test scenario
  Given I search for stocks with a common symbol
    When I request the latest quote for that symbol
    Then I should receive valid quote data
```

### 2. Implement Steps
Add step definitions to appropriate files:
- `given_steps.py` for setup steps
- `when_steps.py` for action steps  
- `then_steps.py` for verification steps

### 3. Run Tests
```bash
python3 -m behave --tags=@new-feature
```

## 🎯 Success Criteria

A successful BDD test run means:
- ✅ All smoke tests pass (core workflows)
- ✅ Error handling tests pass (graceful failures)
- ✅ No HTTP 5xx errors in normal flows
- ✅ All responses contain valid data
- ✅ Tests complete within 2 minutes

## 🐛 Troubleshooting

### Service Not Starting
```bash
# Check port availability
lsof -i :8765

# Check Python version
python3 --version  # Need 3.9+

# Check dependencies
python3 -m pip list | grep behave
```

### Test Failures
```bash
# Run with verbose output
python3 -m behave -v --tags=@smoke

# Check step definitions
python3 -m behave --format=steps.catalog --dry-run

# Run single scenario
python3 -m behave features/market_data_api.feature:10
```

### Import Errors
```bash
# Ensure you're in project root
cd /path/to/vn-market-service

# Install dependencies
python3 -m pip install -r requirements.txt

# Check Python path
python3 -c "import sys; print(sys.path)"
```

## 📚 References

- [Behave Documentation](https://behave.readthedocs.io/)
- [Gherkin Syntax](https://cucumber.io/docs/gherkin/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Project README](../README.md)