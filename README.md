# Arash External API

**Multi-platform AI chatbot service with team-based access control, supporting Telegram and REST API integrations.**

Powered by multiple AI models (GPT, Claude, Gemini, Grok, DeepSeek) with intelligent session management, rate limiting, and usage tracking.

---

## Architecture

```mermaid
graph TB
    subgraph "Entry Point"
        ENTRY[Unified Entry Point<br/>app/main.py<br/>RUN_TELEGRAM_BOT env]
    end

    subgraph "Core Services"
        APP[FastAPI App]
        BOT[Integrated Telegram Bot<br/>Optional]
        MSG[Message Processor]
        SESS[Session Manager]
        PLAT[Platform Manager]
    end

    subgraph "External Services"
        AI[AI Service<br/>Multi-Model Router]
        DB[(PostgreSQL<br/>Teams & Usage)]
    end

    ENTRY --> APP
    APP --> BOT
    APP --> MSG
    BOT --> MSG
    MSG --> SESS
    MSG --> PLAT
    SESS --> AI
    PLAT --> DB
    MSG --> AI

    style ENTRY fill:#9C27B0
    style APP fill:#4CAF50
    style BOT fill:#00BCD4
    style AI fill:#2196F3
    style DB fill:#FF9800
```

## API Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Auth
    participant Session Manager
    participant AI Service
    participant Database

    Client->>FastAPI: POST /v1/chat<br/>{user_id, text, conversation_id?}
    FastAPI->>Auth: Validate API Key
    Auth->>Database: Check team & quotas
    Database-->>Auth: Team config
    Auth-->>FastAPI: Authorized (team_id, platform)

    FastAPI->>Session Manager: Get/Create session
    Session Manager-->>FastAPI: Session context

    FastAPI->>AI Service: Process message<br/>(history + new message)
    AI Service-->>FastAPI: AI response

    FastAPI->>Database: Log usage
    FastAPI->>Session Manager: Update session

    FastAPI-->>Client: {success, response, conversation_id}
```

---

## Quick Start

```bash
# 1. Install dependencies
uv sync --all-extras

# 2. Configure environment
cp .env.example .env  # Edit: DB, AI_SERVICE_URL, tokens

# 3. Apply database migrations
make migrate-up

# 4. Run service (API + integrated Telegram bot)
make run-dev
# IMPORTANT: THE DOCS IS DISABLED IN `make run` like the prod and stage.

```

---

## Configuration

Essential environment variables (`.env`):

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=arash
DB_PASSWORD=***
DB_NAME=arash_db

# AI Service (external multi-model router)
AI_SERVICE_URL=https://our-ai-service.com

# Authentication
SUPER_ADMIN_API_KEYS=admin_key_1,admin_key_2  # Comma-separated
TELEGRAM_BOT_TOKEN=***
TELEGRAM_SERVICE_KEY=***  # For Telegram platform auth

# Runtime
RUN_TELEGRAM_BOT=true  # Run bot integrated with API service
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

## Key Architecture Behaviors

### Message Counting

The `total_message_count` field returned in API responses tracks the total number of **conversation messages** (user messages + AI responses) stored in the database.

**Important Notes:**

- ✅ **Counted:** User chat messages and AI assistant responses
- ❌ **NOT Counted:** Commands (e.g., `/model`, `/help`, `/clear`, `/status`)
- **Persistence:** `total_message_count` persists through `/clear` command
- **Purpose:** Used for analytics and tracking conversation depth

**Example:**

```json
{
  "success": true,
  "response": "مدل شما به GPT-4 تغییر کرد.",
  "model": "GPT-4",
  "total_message_count": 10  // Only counts actual messages, not this /model command
}
```

---

**Version:** 1.0.0 | **API Docs:** [Apidog](https://app.apidog.com/project/1110139) | **Development:** See [CLAUDE.md](CLAUDE.md)
