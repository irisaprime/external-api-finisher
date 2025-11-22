#!/bin/bash
# Quick migration apply script for all 3 databases

set -e  # Exit on error

echo "=========================================="
echo "Applying Clean Migration to All Databases"
echo "=========================================="
echo ""

# Database list
DATABASES=("external_api" "external_api_dev" "external_api_stage")

for DB_NAME in "${DATABASES[@]}"; do
    echo "-------------------------------------------"
    echo "Processing: $DB_NAME"
    echo "-------------------------------------------"

    # Set environment variable for this database
    export DB_NAME=$DB_NAME

    echo "Checking current migration status..."
    uv run alembic current || echo "No migrations applied yet (expected)"

    echo ""
    echo "Applying migration to $DB_NAME..."
    uv run alembic upgrade head

    echo ""
    echo "Verifying migration..."
    uv run alembic current

    echo ""
    echo "✅ $DB_NAME migration complete!"
    echo ""
done

echo "=========================================="
echo "All Databases Migrated Successfully!"
echo "=========================================="
echo ""
echo "Migration applied: 001_initial_schema"
echo ""
echo "Tables created:"
echo "  - channels (replaces teams)"
echo "  - api_keys"
echo "  - usage_logs"
echo "  - messages"
echo ""
echo "Next steps:"
echo "  1. Start your application"
echo "  2. Create test channels: python scripts/manage_api_keys.py channel create ..."
echo "  3. Test the API"
echo ""
