#!/bin/bash
# Migration script to upgrade from PostgreSQL 15 to PostgreSQL 17

set -e

echo "=== PostgreSQL 15 to 17 Migration Script ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if postgres container is running
if docker ps | grep -q trading_postgres; then
    echo -e "${YELLOW}Stopping PostgreSQL container...${NC}"
    docker-compose stop postgres
fi

# Create backup directory
BACKUP_DIR="./database_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Step 1: Starting PostgreSQL 15 to export data...${NC}"
# Start with pg15 to export
docker-compose up -d postgres

# Wait for postgres to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 5
until docker exec trading_postgres pg_isready -U trading_user -d trading_db > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

echo -e "${YELLOW}Step 2: Exporting database...${NC}"
# Export database
docker exec trading_postgres pg_dump -U trading_user -d trading_db -F c -f /tmp/backup.dump
docker cp trading_postgres:/tmp/backup.dump "$BACKUP_DIR/backup.dump"

echo -e "${GREEN}Database exported to $BACKUP_DIR/backup.dump${NC}"

echo -e "${YELLOW}Step 3: Stopping PostgreSQL and removing old volume...${NC}"
# Stop and remove container
docker-compose down postgres

# Remove the old volume
echo -e "${YELLOW}Removing old PostgreSQL 15 volume...${NC}"
docker volume rm trading_support_dashboard_postgres_data 2>/dev/null || echo "Volume already removed or doesn't exist"

echo -e "${YELLOW}Step 4: Updating docker-compose.yml to PostgreSQL 17...${NC}"
# docker-compose.yml should already be updated to pg17

echo -e "${YELLOW}Step 5: Starting PostgreSQL 17...${NC}"
# Start with pg17
docker-compose up -d postgres

# Wait for postgres to be ready
echo "Waiting for PostgreSQL 17 to be ready..."
sleep 5
until docker exec trading_postgres pg_isready -U trading_user -d trading_db > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

echo -e "${YELLOW}Step 6: Restoring database...${NC}"
# Copy backup to container
docker cp "$BACKUP_DIR/backup.dump" trading_postgres:/tmp/backup.dump

# Restore database
docker exec trading_postgres pg_restore -U trading_user -d trading_db -c --if-exists /tmp/backup.dump || \
docker exec trading_postgres pg_restore -U trading_user -d trading_db /tmp/backup.dump

# Clean up
docker exec trading_postgres rm /tmp/backup.dump

echo -e "${GREEN}=== Migration Complete! ==="
echo -e "${GREEN}Database has been migrated from PostgreSQL 15 to PostgreSQL 17${NC}"
echo -e "${YELLOW}Backup saved in: $BACKUP_DIR${NC}"

