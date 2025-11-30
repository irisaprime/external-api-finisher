# Arash External API

Multi-platform AI chatbot service with channel-based access control.

**Stack:** FastAPI + PostgreSQL + Telegram Bot | **Models:** GPT, Claude, Gemini, Grok, DeepSeek

---

## System Overview

### Architecture Diagram

```mermaid
graph TB
    subgraph "External Clients"
        TG[Telegram Users]
        CH[Custom Channels]
        ADMIN[Super Admins]
    end

    subgraph "FastAPI Application"
        API[API Router]
        AUTH[Authentication]
        SESS[Session Manager]
        PROC[Message Processor]
        USAGE[Usage Tracker]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL)]
        MEM[In-Memory Sessions]
    end

    subgraph "External Services"
        AI[AI Service<br/>Multi-Model Router]
    end

    TG -->|Telegram Service Key| API
    CH -->|Channel API Keys| API
    ADMIN -->|Super Admin Keys| API

    API --> AUTH
    AUTH --> SESS
    SESS --> MEM
    SESS --> PROC
    PROC --> AI
    PROC --> USAGE
    USAGE --> PG
    MEM -.periodic sync.-> PG

    style TG fill:#e1f5ff
    style CH fill:#e1f5ff
    style ADMIN fill:#ffe1e1
    style API fill:#fff4e1
    style AI fill:#e8f5e9
    style PG fill:#f3e5f5
```

### Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Router
    participant Auth as Authentication
    participant Session as Session Manager
    participant Processor as Message Processor
    participant AI as AI Service
    participant DB as PostgreSQL

    Client->>API: POST /v1/chat<br/>{user_id, text}<br/>Authorization: Bearer key

    API->>Auth: Validate API Key
    Auth->>DB: Check api_keys table
    DB-->>Auth: Channel + Key Info
    Auth-->>API: APIKey object

    API->>Session: Get/Create Session<br/>channel:id:user_id
    Session->>DB: Load message history
    DB-->>Session: Previous messages
    Session-->>API: Session object

    API->>Processor: Process message

    alt Command (e.g., /clear, /model)
        Processor-->>Client: Command response
    else Chat Message
        Processor->>AI: Send with context
        AI-->>Processor: AI response
        Processor->>DB: Log usage + message
        Processor->>Session: Update session
        Processor-->>Client: BotResponse
    end

    Note over Client,DB: Rate limiting, quota checks,<br/>and error handling at each step
```

---

## Architecture

```
app/main.py (Entry Point)
│
├── FastAPI Application
│   ├── /v1/chat (Public - All API keys)
│   ├── /v1/commands (Public)
│   └── /v1/admin/* (Super admin only)
│
├── Telegram Bot (Optional - RUN_TELEGRAM_BOT=true)
│
└── Core Services
    ├── ChannelManager (channel_identifier → config)
    ├── SessionManager (In-memory sessions)
    ├── MessageProcessor (Commands + AI routing)
    └── UsageTracker (PostgreSQL logging)

External: AI Service (Multi-model router), PostgreSQL
```

**Database Tables:**
- `channels` - Integration endpoints (Telegram, customer channels)
- `api_keys` - Authentication keys per channel
- `usage_logs` - Request tracking
- `messages` - Conversation history

---

## Quick Start

```bash
# 1. Install
uv sync --all-extras

# 2. Configure
cp .env.example .env
# Edit: DB_*, AI_SERVICE_URL, TELEGRAM_BOT_TOKEN, INTERNAL_API_KEY, SUPER_ADMIN_API_KEYS

# 3. Database setup
psql -U postgres -c "DROP DATABASE IF EXISTS arash_db;"
psql -U postgres -c "CREATE DATABASE arash_db OWNER arash_user;"
make migrate-up

# 4. Run
make run-dev  # API at :3000, docs at :3000/docs (dev only)
```

---

## API Endpoints

**Public** (All API keys):
- `POST /v1/chat` - Send message, get AI response
- `GET /v1/commands` - List available commands

**Admin** (Super admin keys only):
- `GET /v1/admin/channels` - List all channels
- `POST /v1/admin/channels` - Create channel
- `GET /v1/admin/stats` - Usage statistics
- `GET /v1/admin/sessions` - Active sessions

---

## Configuration

Essential `.env` variables:

```bash
# Database (PostgreSQL only)
DB_HOST=localhost
DB_PORT=5432
DB_USER=arash_user
DB_PASSWORD=***
DB_NAME=arash_db

# AI Service
AI_SERVICE_URL=https://your-ai-service.com

# Authentication (all required)
TELEGRAM_BOT_TOKEN=***                    # Telegram bot token
TELEGRAM_SERVICE_KEY=***                  # For bot API auth (min 32 chars)
INTERNAL_API_KEY=***                      # Private channels (min 32 chars)
INTERNAL_MODELS=["openai/gpt-5-chat","google/gemini-2.0-flash-001"]
SUPER_ADMIN_API_KEYS=key1,key2            # Comma-separated admin keys

# Runtime
RUN_TELEGRAM_BOT=true                     # Enable Telegram bot
ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_API_DOCS=false                     # true in dev only
```

---

## Commands

**Development:**
```bash
make install        # Install dependencies (uv)
make run            # Start service
make run-dev        # Start with auto-reload
make test           # Run tests (345 tests)
make lint           # Code quality check
make format         # Format code
make clean          # Remove cache
```

**Database:**
```bash
make migrate-up                      # Apply migrations
make migrate-down                    # Rollback
make migrate-status                  # Show status
make migrate-create MSG="desc"       # Create migration
```

**Channel Management:**
```bash
make db-channels                           # List channels
make db-keys                               # List API keys
make db-channel-create NAME="Ch" DAILY=100 MONTHLY=3000
make db-key-create CHANNEL=<id> NAME="Key"
```

---

## Key Behaviors

**Message Counting:**
- `total_message_count` tracks chat messages only (user + assistant)
- Commands (`/model`, `/help`, `/clear`) are NOT counted
- Persists through `/clear` command

**Session Management:**
- One conversation per user per channel
- Session ID: `channel_identifier:channel_id:user_id`
- Messages persist in DB; `/clear` removes from AI context only

**Channel Types:**
- **Public** (telegram): Public messaging, basic rate limiting
- **Private** (customer channels): Authenticated, custom quotas, full isolation

---

**Version:** 1.0.0 | **Package Manager:** uv | **Python:** 3.11+ | **Database:** PostgreSQL
