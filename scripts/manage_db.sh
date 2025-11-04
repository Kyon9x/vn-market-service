#!/bin/bash

# VN Market Service Database Management Script
# This script helps manage the gold database seeding and backup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_PATH="$SCRIPT_DIR/db/assets.db"
BACKUP_DIR="$SCRIPT_DIR/db/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Function to check if service is running
is_service_running() {
    curl -s http://localhost:8765/health >/dev/null 2>&1
}

# Function to backup database
backup_database() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="$BACKUP_DIR/assets_backup_$timestamp.db"
    
    if [ -f "$DB_PATH" ]; then
        cp "$DB_PATH" "$backup_file"
        print_status "Database backed up to: $backup_file"
        
        # Compress old backups (keep last 5 uncompressed)
        ls -t "$BACKUP_DIR"/assets_backup_*.db | tail -n +6 | xargs -r gzip
        print_status "Old backups compressed"
    else
        print_warning "No database file found to backup"
    fi
}

# Function to restore database
restore_database() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        print_error "Please specify backup file to restore"
        echo "Usage: $0 restore <backup_file>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        # Try to find in backup directory
        backup_file="$BACKUP_DIR/$(basename "$backup_file")"
        if [ ! -f "$backup_file" ]; then
            print_error "Backup file not found: $backup_file"
            exit 1
        fi
    fi
    
    # Backup current database before restoring
    backup_database
    
    # Restore the backup
    cp "$backup_file" "$DB_PATH"
    print_status "Database restored from: $backup_file"
    
    # Restart service if running
    if is_service_running; then
        print_status "Restarting service..."
        docker-compose restart
        sleep 5
        if is_service_running; then
            print_status "Service restarted successfully"
        else
            print_error "Service failed to restart"
        fi
    fi
}

# Function to seed gold data
seed_gold_data() {
    print_header "Starting Gold Data Seeding"
    
    if ! is_service_running; then
        print_error "Service is not running. Please start it first:"
        echo "docker-compose up -d"
        exit 1
    fi
    
    # Backup current database before seeding
    backup_database
    
    print_status "Triggering gold data seeding..."
    print_warning "This may take 30 minutes to several hours depending on data range"
    print_status "You can monitor progress with: $0 progress"
    
    # Trigger seeding
    response=$(curl -s -X POST http://localhost:8765/gold/seed)
    
    if echo "$response" | grep -q '"status":"success"'; then
        print_status "Gold seeding completed successfully!"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        print_error "Gold seeding failed"
        echo "$response"
    fi
}

# Function to check seeding progress
check_progress() {
    print_header "Seeding Progress"
    
    if ! is_service_running; then
        print_error "Service is not running"
        exit 1
    fi
    
    response=$(curl -s http://localhost:8765/cache/seed/progress)
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    
    # Also check database size
    if [ -f "$DB_PATH" ]; then
        db_size=$(du -h "$DB_PATH" | cut -f1)
        record_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM historical_records WHERE asset_type = 'GOLD';" 2>/dev/null || echo "0")
        print_status "Database size: $db_size, Gold records: $record_count"
    fi
}

# Function to show database info
show_database_info() {
    print_header "Database Information"
    
    if [ ! -f "$DB_PATH" ]; then
        print_warning "No database file found"
        return
    fi
    
    db_size=$(du -h "$DB_PATH" | cut -f1)
    print_status "Database file: $DB_PATH"
    print_status "Database size: $db_size"
    
    # Check record counts
    if command -v sqlite3 >/dev/null 2>&1; then
        total_records=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM historical_records;" 2>/dev/null || echo "N/A")
        gold_records=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM historical_records WHERE asset_type = 'GOLD';" 2>/dev/null || echo "N/A")
        
        print_status "Total records: $total_records"
        print_status "Gold records: $gold_records"
        
        if [ "$gold_records" != "N/A" ] && [ "$gold_records" -gt 0 ]; then
            date_range=$(sqlite3 "$DB_PATH" "SELECT MIN(date), MAX(date) FROM historical_records WHERE asset_type = 'GOLD';" 2>/dev/null)
            if [ $? -eq 0 ]; then
                print_status "Gold date range: $date_range"
            fi
        fi
    else
        print_warning "sqlite3 not available - cannot show record counts"
    fi
    
    # Show available backups
    print_status "Available backups:"
    if [ -d "$BACKUP_DIR" ]; then
        ls -lah "$BACKUP_DIR"/assets_backup_*.db* 2>/dev/null || print_warning "No backups found"
    fi
}

# Function to prepare for deployment
prepare_deployment() {
    print_header "Preparing for Deployment"
    
    # Backup current database
    backup_database
    
    # Create deployment package
    local deploy_dir="$SCRIPT_DIR/deployment"
    mkdir -p "$deploy_dir"
    
    # Copy database for deployment
    if [ -f "$DB_PATH" ]; then
        cp "$DB_PATH" "$deploy_dir/assets.db"
        print_status "Database copied for deployment"
    else
        print_warning "No database found - deployment will use empty database"
    fi
    
    # Create deployment info
    cat > "$deploy_dir/deployment_info.txt" << EOF
VN Market Service Deployment Package
Generated: $(date)
Database records: $(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM historical_records WHERE asset_type = 'GOLD';" 2>/dev/null || echo "0")
Date range: $(sqlite3 "$DB_PATH" "SELECT MIN(date), MAX(date) FROM historical_records WHERE asset_type = 'GOLD';" 2>/dev/null || echo "No data")

To deploy:
1. Copy assets.db to the target server's db/ directory
2. Run: docker-compose up -d --build
3. The service will start with pre-seeded data
EOF
    
    print_status "Deployment package created in: $deploy_dir"
    print_status "Copy this directory to your target server"
}

# Main script logic
case "${1:-help}" in
    "seed")
        seed_gold_data
        ;;
    "progress")
        check_progress
        ;;
    "backup")
        backup_database
        ;;
    "restore")
        restore_database "$2"
        ;;
    "info")
        show_database_info
        ;;
    "prepare")
        prepare_deployment
        ;;
    "help"|*)
        echo "VN Market Service Database Management Script"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  seed      - Start gold data seeding (takes 30min - 3hours)"
        echo "  progress  - Check seeding progress"
        echo "  backup    - Backup current database"
        echo "  restore   - Restore from backup (requires backup file)"
        echo "  info      - Show database information"
        echo "  prepare   - Prepare deployment package with current data"
        echo "  help      - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 seed                    # Start seeding gold data"
        echo "  $0 progress                # Check seeding progress"
        echo "  $0 backup                  # Backup database"
        echo "  $0 restore backup_20241101.db  # Restore from backup"
        echo "  $0 info                    # Show database info"
        echo "  $0 prepare                 # Create deployment package"
        ;;
esac