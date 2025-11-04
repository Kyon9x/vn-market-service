# AGENTS.md

## Build/Lint/Test Commands

Always use .venv virtual environment.

### Running Tests
```bash
# Run BDD tests (service must be running)
./tests/run_bdd_tests.sh

# Run smoke tests only
cd tests && python3 -m behave --tags=@smoke --format=pretty features

# Run all regression tests
cd tests && python3 -m behave --tags=@regression features

# Run specific test file
cd tests && python3 -m behave features/market_data_api.feature

# Generate HTML test report
cd tests && python3 -m behave --format=html5 --outfile=reports/test_report.html features
```

### Development Commands
```bash
# Start service
./start.sh

# Start with debug logging
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level debug

# Database management
./manage_db.sh
```
### Docker Commands
```bash
# Build Docker image
docker build -t vn-market-service:latest .
# Run Docker container
docker run -d -p 8765:8765 vn-market-service:latest
# Docker compose up
docker-compose up -d
# Docker compose down
docker-compose down
```


## Code Style Guidelines

### Python & Imports
- Python 3.12+ required (vnstock 3.x compatibility)
- Use absolute imports: `from app.clients.fund_client import FundClient`
- Standard library imports first, then third-party, then local app imports
- Configure vnstock timeout before importing clients (see `app/vnstock_config.py`)

### Naming Conventions
- Classes: PascalCase (`FundClient`, `CacheManager`)
- Functions/variables: snake_case (`get_fund_data`, `cache_manager`)
- Constants: UPPER_SNAKE_CASE (`QUOTE_TTL_CONFIG`, `ASSET_TYPE_FUND`)
- Private members: prefix with underscore (`_funds_cache`, `_cache_timestamp`)

### Error Handling
- Use structured logging with provider call decorator: `@log_provider_call`
- Vietnamese error detection for rate limiting: "quá nhiều request", "thử lại sau"
- Global exception handling in FastAPI with proper HTTP status codes
- Database-first architecture: check cache/database before API calls

### Type Safety & Models
- Use Pydantic models for all API responses (see `app/models.py`)
- Type hints required: `def fetch_data(self, symbol: str) -> Optional[Dict]:`
- Validate asset types: STOCK/FUND/INDEX/GOLD constants from `app/constants.py`

### Caching Patterns
- Multi-layer: SQLite persistent + in-memory LRU + historical cache
- TTL varies by asset type (24h funds, 1h stocks/indices/gold)
- Background tasks for cleanup and refresh
- Always check cache before external API calls

### Testing
- BDD tests with Behave framework in `tests/features/`
- Service must run on localhost:8765 before testing
- Tag tests: @smoke, @regression, @error-handling
- Test all asset types: Search → Quote → History flow
- use `./tests/run_bdd_tests.sh` for convenience