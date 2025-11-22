# Database Migration Guide

After dropping all tables and databases, follow these steps to apply the new clean schema:

## Step 1: Verify All Tables Are Dropped

Run this in PostgreSQL to confirm cleanup:

```sql
-- For each database (external_api, external_api_dev, external_api_stage)
\c external_api
\dt
-- Should show: "Did not find any relations" or empty list

\c external_api_dev
\dt

\c external_api_stage
\dt
```

## Step 2: Apply Migrations

The migration will create 4 tables:
- `channels` (replaces old `teams` table)
- `api_keys`
- `usage_logs`
- `messages`

### Option A: Using Docker Compose

```bash
# Apply migration in the running container
docker-compose exec app make migrate-up

# Or if you need to restart the app
docker-compose restart app
```

### Option B: Using Make (if running locally)

```bash
# For production database
export DB_NAME=external_api
make migrate-up

# For development database
export DB_NAME=external_api_dev
make migrate-up

# For staging database
export DB_NAME=external_api_stage
make migrate-up
```

### Option C: Direct Alembic Command

```bash
# Using uv (from project root)
uv run alembic upgrade head

# Or if alembic is in PATH
alembic upgrade head
```

## Step 3: Verify Migration

Check that tables were created:

```sql
\c external_api

-- List all tables
\dt

-- Should show:
-- public | alembic_version | table
-- public | api_keys        | table
-- public | channels        | table
-- public | messages        | table
-- public | usage_logs      | table

-- Check alembic version
SELECT * FROM alembic_version;
-- Should show: 001_initial_schema

-- Verify channels table structure
\d channels
```

## Step 4: Start Application

After successful migration:

```bash
# Using docker-compose
docker-compose up -d

# Or make command
make run-dev
```

## Troubleshooting

### Error: "alembic: command not found"

Solution:
```bash
uv run alembic upgrade head
```

### Error: "Multiple head revisions"

This should NOT happen with the new migration. If it does:
```bash
# Check current state
uv run alembic current
uv run alembic heads

# Should show only one head: 001_initial_schema
```

### Error: "Target database is not up to date"

```bash
# Check migration status
uv run alembic current

# Force stamp to current version (only if needed)
uv run alembic stamp head
```

## What Was Changed

The new migration creates a **channel-based architecture**:

### Old Schema (teams):
```
teams → api_keys → usage_logs
     ↘ messages
```

### New Schema (channels):
```
channels → api_keys → usage_logs
        ↘ messages
```

All foreign keys now point to `channels.id` instead of `teams.id`.

## Next Steps After Migration

1. **Create test channel:**
   ```bash
   python scripts/manage_api_keys.py channel create --title "Test Channel" --channel-id "test"
   ```

2. **List channels:**
   ```bash
   python scripts/manage_api_keys.py channel list
   ```

3. **Check API health:**
   ```bash
   curl http://localhost:8000/health
   ```
