# Database Management for VN Market Service

This directory contains database files and management tools for the VN Market Service.

## Files

- `assets.db` - Main SQLite database containing all historical data
- `backups/` - Directory containing database backups
- `manage_db.sh` - Database management script

## Quick Start

### 1. Start Service with Persistent Database
```bash
docker-compose up -d --build
```

### 2. Seed Gold Data (One-time Operation)
```bash
./manage_db.sh seed
```

### 3. Monitor Seeding Progress
```bash
./manage_db.sh progress
```

## Database Management Script Usage

The `manage_db.sh` script provides easy database management:

### Commands

| Command | Description |
|---------|-------------|
| `./manage_db.sh seed` | Start gold data seeding (30min - 3hours) |
| `./manage_db.sh progress` | Check seeding progress |
| `./manage_db.sh backup` | Backup current database |
| `./manage_db.sh restore <file>` | Restore from backup |
| `./manage_db.sh info` | Show database information |
| `./manage_db.sh prepare` | Create deployment package |

### Examples

```bash
# Start seeding gold data
./manage_db.sh seed

# Check progress
./manage_db.sh progress

# Backup database
./manage_db.sh backup

# Show database info
./manage_db.sh info

# Prepare for deployment
./manage_db.sh prepare
```

## Database Persistence

The Docker setup now includes volume mounts to persist data:

```yaml
volumes:
  - ./db:/app/db        # Database persistence
  - ./logs:/app/logs    # Log persistence
```

This means:
- ✅ Database survives container restarts
- ✅ Seeded data is preserved
- ✅ Backups are stored on host machine
- ✅ Easy to migrate to new servers

## Deployment Scenarios

### New Deployment with Seeded Data

1. **Prepare package on development server:**
   ```bash
   ./manage_db.sh prepare
   ```

2. **Copy to production server:**
   ```bash
   scp -r deployment/ user@server:/path/to/vn-market-service/
   ```

3. **Deploy on production:**
   ```bash
   cd /path/to/vn-market-service/
   cp deployment/assets.db db/
   docker-compose up -d --build
   ```

### Backup and Recovery

```bash
# Regular backup
./manage_db.sh backup

# Restore if needed
./manage_db.sh restore assets_backup_20241102_120000.db
```

## Database Schema

The database stores data in the `historical_records` table:

```sql
CREATE TABLE historical_records (
    symbol TEXT NOT NULL,           -- VN.GOLD, SJC.GOLD, etc.
    asset_type TEXT NOT NULL,        -- 'GOLD', 'STOCK', 'FUND', 'INDEX'
    date TEXT NOT NULL,             -- YYYY-MM-DD format
    open/high/low/close REAL,       -- OHLC price data
    adjclose REAL,                  -- Adjusted close price
    volume REAL,                    -- Trading volume
    nav REAL,                       -- Net asset value
    buy_price REAL,                 -- Gold buy price
    sell_price REAL,                -- Gold sell price
    data_json TEXT,                  -- Additional JSON data
    created_at TIMESTAMP,            -- Record creation time
    updated_at TIMESTAMP,            -- Last update time
    PRIMARY KEY (symbol, asset_type, date)
);
```

## Performance Benefits

Once seeded:
- **Historical queries**: ~1ms (database) vs ~1000ms (API)
- **Zero rate limits**: No more "quá nhiều request" errors
- **Offline capability**: Service works without external dependencies
- **Consistent data**: Same data across all deployments

## Monitoring

Check database health:
```bash
# Database size and record count
./manage_db.sh info

# Service health
curl http://localhost:8765/health

# Gold endpoint test
curl "http://localhost:8765/history/VN.GOLD?start_date=2024-01-01&end_date=2024-01-31"
```

## Troubleshooting

### Database Not Found
```bash
# Check if database exists
ls -la db/assets.db

# Rebuild with volume mount
docker-compose down
docker-compose up -d --build
```

### Seeding Issues
```bash
# Check logs
docker-compose logs -f

# Restart seeding
./manage_db.sh seed
```

### Performance Issues
```bash
# Check database size
./manage_db.sh info

# Create indexes if needed (automatically handled by migrations)
```