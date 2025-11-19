#!/bin/bash
# Simple migration script to upgrade from PostgreSQL 15 to PostgreSQL 17

set -e

echo "=== PostgreSQL 15 to 17 Migration ==="
echo ""

# Backup directory
BACKUP_FILE="./database_backup_$(date +%Y%m%d_%H%M%S).dump"

# Step 1: Export data from PG15
echo "Step 1: Exporting data from PostgreSQL 15..."
if docker ps | grep -q trading_postgres; then
    docker-compose stop postgres
fi

# Start PG15 temporarily (if docker-compose still has pg15, otherwise we need to handle this)
# For now, let's assume we need to manually start with pg15 first
echo "Starting PostgreSQL 15 to export data..."
# Temporarily change to pg15 for export
sed -i.bak 's/latest-pg17/latest-pg15/' docker-compose.yml
docker-compose up -d postgres

# Wait for postgres
echo "Waiting for PostgreSQL to be ready..."
sleep 5
for i in {1..30}; do
    if docker exec trading_postgres pg_isready -U trading_user -d trading_db > /dev/null 2>&1; then
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Export
echo "Exporting database..."
docker exec trading_postgres pg_dump -U trading_user -d trading_db -F c -f /tmp/backup.dump
docker cp trading_postgres:/tmp/backup.dump "$BACKUP_FILE"
echo "✓ Backup saved to: $BACKUP_FILE"

# Step 2: Stop and remove old volume
echo ""
echo "Step 2: Removing old PostgreSQL 15 volume..."
docker-compose down postgres
docker volume rm trading_support_dashboard_postgres_data 2>/dev/null || true

# Step 3: Restore to PG17
echo ""
echo "Step 3: Starting PostgreSQL 17 and restoring data..."
# Restore pg17 in docker-compose
sed -i.bak2 's/latest-pg15/latest-pg17/' docker-compose.yml
docker-compose up -d postgres

# Wait for postgres 17
echo "Waiting for PostgreSQL 17 to be ready..."
sleep 5
for i in {1..30}; do
    if docker exec trading_postgres pg_isready -U trading_user -d trading_db > /dev/null 2>&1; then
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Restore
echo "Restoring database..."
docker cp "$BACKUP_FILE" trading_postgres:/tmp/backup.dump
docker exec trading_postgres pg_restore -U trading_user -d trading_db -c --if-exists /tmp/backup.dump 2>/dev/null || \
docker exec trading_postgres pg_restore -U trading_user -d trading_db /tmp/backup.dump

# Cleanup
docker exec trading_postgres rm /tmp/backup.dump
rm -f docker-compose.yml.bak docker-compose.yml.bak2

echo ""
echo "=== Migration Complete! ==="
echo "Database migrated to PostgreSQL 17"
echo "Backup: $BACKUP_FILE"

