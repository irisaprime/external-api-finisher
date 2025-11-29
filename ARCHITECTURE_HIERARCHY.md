# Arash External API - Complete Architecture Hierarchy

**Version:** 1.0.0
**Date:** 2025-11-22
**Architecture:** Channel-Based (Legacy "Teams" Removed)

---

## 🏗️ FINAL ARCHITECTURE HIERARCHY

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ARASH EXTERNAL API SERVICE                           │
│                         (FastAPI Application)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
         ┌──────────▼──────────┐         ┌─────────▼──────────┐
         │  PUBLIC ENDPOINTS   │         │  ADMIN ENDPOINTS   │
         │    /v1/chat         │         │   /v1/admin/*      │
         │    /v1/commands     │         │                    │
         └──────────┬──────────┘         └─────────┬──────────┘
                    │                               │
         ┌──────────▼──────────┐         ┌─────────▼──────────┐
         │   AUTHENTICATION    │         │   AUTHENTICATION   │
         │  Channel API Keys   │         │ Super Admin Keys   │
         │   (Database)        │         │  (Environment)     │
         └──────────┬──────────┘         └────────────────────┘
                    │
         ┌──────────▼──────────┐
         │     CHANNELS        │
         │  (Main Entity)      │
         └──────────┬──────────┘
                    │
    ┌───────────────┼───────────────┬────────────────┬──────────────┐
    │               │               │                │              │
┌───▼────┐   ┌─────▼──────┐  ┌────▼─────┐   ┌─────▼──────┐  ┌───▼────┐
│ API    │   │  USAGE     │  │ SESSIONS │   │  USERS     │  │CONFIG  │
│ Keys   │   │  Tracking  │  │          │   │            │  │        │
└────────┘   └────────────┘  └──────────┘   └────────────┘  └────────┘
```

---

## 📊 DETAILED ENTITY HIERARCHY

### Level 1: Service Layer
```
┌─────────────────────────────────────────────────────────────┐
│                  ARASH EXTERNAL API SERVICE                 │
│                                                             │
│  Purpose: Multi-platform AI chatbot service                │
│  Type: FastAPI + Telegram Bot (Optional)                   │
│  Version: 1.0.0                                             │
└─────────────────────────────────────────────────────────────┘
```

### Level 2: Access Control (Two-Tier Authentication)
```
┌──────────────────────────────┐  ┌──────────────────────────────┐
│    SUPER ADMIN ACCESS        │  │    CHANNEL ACCESS            │
│    (Infrastructure)          │  │    (Application)             │
│                              │  │                              │
│  • Environment-based         │  │  • Database-backed           │
│  • SUPER_ADMIN_API_KEYS      │  │  • api_keys table            │
│  • Access: ALL /v1/admin/*   │  │  • Access: /v1/chat only     │
│  • Purpose: Manage platform  │  │  • Purpose: Use chatbot      │
└──────────────────────────────┘  └──────────────────────────────┘
```

### Level 3: Channels (Core Entity)
```
┌─────────────────────────────────────────────────────────────────┐
│                          CHANNELS                               │
│                     (Replaces old "Teams")                      │
│                                                                 │
│  Definition: A communication endpoint / integration point       │
│  Database Table: channels                                       │
│  Primary Key: id (auto-increment integer)                       │
│  Unique Identifier: channel_id (string, e.g., "Internal-BI")   │
│                                                                 │
│  Each Channel Has:                                              │
│    • 1 auto-generated API key (for authentication)             │
│    • N users (many users can use one channel)                  │
│    • N sessions (one per user)                                 │
│    • 1 configuration (quotas, rate limits, models)             │
│    • 1 usage statistics (aggregated)                           │
└─────────────────────────────────────────────────────────────────┘
```

### Level 4: Channel Types (Access Type)
```
┌──────────────────────────┐          ┌──────────────────────────┐
│   PUBLIC CHANNELS        │          │   PRIVATE CHANNELS       │
│   (access_type=public)   │          │   (access_type=private)  │
│                          │          │                          │
│  Examples:               │          │  Examples:               │
│   • Telegram Bot         │          │   • Internal-BI          │
│   • Discord Bot          │          │   • HOSCO-Popak          │
│   • Public Website       │          │   • External-Marketing   │
│                          │          │   • Enterprise-Client-A  │
│  Config Defaults:        │          │                          │
│   • Rate: 20 req/min     │          │  Config Defaults:        │
│   • History: 10 msgs     │          │   • Rate: 60 req/min     │
│   • Model: Gemini Flash  │          │   • History: 30 msgs     │
│                          │          │   • Model: GPT-5 Chat    │
└──────────────────────────┘          └──────────────────────────┘
```

### Level 5: Channel Components
```
CHANNEL (e.g., "Internal-BI")
│
├─── API KEY (1:1 relationship)
│    │
│    ├─ Key Prefix: "ark_1234"
│    ├─ Key Hash: SHA256(full_key)
│    ├─ Is Active: true/false
│    ├─ Expires At: datetime or null
│    └─ Last Used: datetime or null
│
├─── CONFIGURATION (1:1 embedded)
│    │
│    ├─ Title: "تیم هوش مصنوعی داخلی"
│    ├─ Channel ID: "Internal-BI"
│    ├─ Access Type: "private"
│    ├─ Monthly Quota: 100000 or null
│    ├─ Daily Quota: 5000 or null
│    ├─ Rate Limit: 60 or null (null = use default)
│    ├─ Max History: 30 or null (null = use default)
│    ├─ Default Model: "openai/gpt-5-chat" or null
│    ├─ Available Models: [...] or null
│    └─ Allow Model Switch: true or null
│
├─── USERS (1:N relationship)
│    │
│    ├─ User 1 (user_id: "user_12345")
│    │   └─ Has 1 Session (user + channel = unique)
│    │
│    ├─ User 2 (user_id: "customer_001")
│    │   └─ Has 1 Session
│    │
│    └─ User N (user_id: "telegram_987654")
│        └─ Has 1 Session
│
├─── SESSIONS (1:N relationship, via users)
│    │
│    ├─ Session 1 (user_12345 on Internal-BI)
│    │   ├─ Conversation History (messages)
│    │   ├─ Current Model: "GPT-5 Chat"
│    │   ├─ Total Message Count: 24
│    │   └─ Last Activity: datetime
│    │
│    └─ Session N (...)
│
└─── USAGE LOGS (1:N relationship)
     │
     ├─ Log 1 (timestamp, model, cost, success)
     ├─ Log 2 (timestamp, model, cost, success)
     └─ Log N (...)
          │
          └─ Aggregated into Usage Statistics
```

---

## 🔄 COMPLETE DATA FLOW

### Request Flow
```
┌──────────┐
│  CLIENT  │
└────┬─────┘
     │ HTTP Request
     │ Authorization: Bearer ark_xxx
     │
     ▼
┌────────────────────┐
│  FastAPI Endpoint  │
│   /v1/chat         │
└────┬───────────────┘
     │
     ▼
┌────────────────────┐
│  Authentication    │
│  Dependency        │
└────┬───────────────┘
     │
     ├─ Validate API Key (ark_xxx)
     │  └─ Query: api_keys table
     │     └─ Match: SHA256(ark_xxx)
     │        └─ Check: is_active, expires_at
     │           └─ Return: APIKey object (includes channel_id)
     │
     ▼
┌────────────────────┐
│  Get/Create        │
│  Session           │
└────┬───────────────┘
     │
     ├─ Session Key: (user_id + channel_id)
     │  └─ Ensures: Each user has ONE conversation per channel
     │     └─ Creates: ChatSession object
     │
     ▼
┌────────────────────┐
│  Process Message   │
└────┬───────────────┘
     │
     ├─ Check Rate Limit (channel-specific)
     ├─ Check Quotas (daily, monthly)
     ├─ Add to History
     ├─ Send to AI Service
     └─ Log Usage
     │
     ▼
┌────────────────────┐
│  Return Response   │
└────────────────────┘
```

---

## 🗄️ DATABASE SCHEMA HIERARCHY

```
┌─────────────────────────────────────────────────────────────┐
│                       DATABASE                              │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┬─────────────────┐
        │                     │                     │                 │
┌───────▼────────┐  ┌─────────▼────────┐  ┌───────▼───────┐  ┌──────▼──────┐
│   CHANNELS     │  │    API_KEYS      │  │  USAGE_LOGS   │  │  MESSAGES   │
│   (Main)       │  │                  │  │               │  │             │
└───────┬────────┘  └─────────┬────────┘  └───────┬───────┘  └──────┬──────┘
        │                     │                   │                  │
        │ id ◄────────────────┤ channel_id        │                  │
        │ channel_id          │ key_prefix        │                  │
        │ title               │ key_hash          │                  │
        │ access_type         │ is_active         │                  │
        │ monthly_quota       │ expires_at        │                  │
        │ daily_quota         │ created_at        │                  │
        │ is_active           │ last_used_at      │                  │
        │ rate_limit          └───────────────────┤ api_key_id       │
        │ max_history                             │ channel_id       │
        │ default_model                           │ user_id          │
        │ available_models                        │ request_data     │
        │ allow_model_switch                      │ response_data    │
        │ created_at                              │ model_used       │
        │ updated_at                              │ success          │
        └─────────────────────────────────────────┤ created_at       │
                                                  └──────────────────┤ channel_id
                                                                     │ user_id
                                                                     │ role
                                                                     │ content
                                                                     │ created_at
                                                                     └──────────
```

### Relationships
```
channels (1) ←──→ (1) api_keys
    ↓
    │ channel_id
    ↓
channels (1) ←──→ (N) usage_logs
    ↓
    │ channel_id
    ↓
channels (1) ←──→ (N) messages
    ↓
    │ (channel_id + user_id = session)
    ↓
messages (N) ←──→ (1) session (virtual, in-memory)
```

---

## 📋 FIELD MAPPING: OLD vs NEW

### ❌ REMOVED (Old "Teams" Architecture)
```
OLD FIELD NAME          →  REMOVED
─────────────────────────────────────
team_id                 →  ❌ DELETED
team_name               →  ❌ DELETED
display_name            →  ❌ DELETED
platform_type           →  ❌ DELETED
platform_name (field)   →  ❌ DELETED
```

### ✅ CURRENT (New "Channels" Architecture)
```
NEW FIELD NAME          →  PURPOSE
──────────────────────────────────────────────────────────
id                      →  Primary key (auto-increment)
channel_id              →  System identifier (e.g., "Internal-BI")
title                   →  Human-friendly name (supports Persian)
access_type             →  "public" or "private"
monthly_quota           →  Monthly request limit (null = unlimited)
daily_quota             →  Daily request limit (null = unlimited)
is_active               →  Active/inactive status
rate_limit              →  Requests per minute (null = use default)
max_history             →  Messages in AI context (null = use default)
default_model           →  AI model to use (null = use default)
available_models        →  List of allowed models (null = use default)
allow_model_switch      →  Can users change model? (null = use default)
created_at              →  Creation timestamp
updated_at              →  Last update timestamp
```

---

## 🎯 CHANNEL EXAMPLES

### Example 1: Telegram Bot (Public)
```
┌─────────────────────────────────────────┐
│  Channel: Telegram Bot                  │
├─────────────────────────────────────────┤
│  channel_id: "telegram"                 │
│  title: "Telegram Public Bot"           │
│  access_type: "public"                  │
│  monthly_quota: 500000                  │
│  daily_quota: 20000                     │
│  rate_limit: 20                         │
│  max_history: 10                        │
│  default_model: "gemini-2.0-flash"      │
│  allow_model_switch: true               │
├─────────────────────────────────────────┤
│  API Key: ark_telegram123...            │
│  Users: 5000+                           │
│  Sessions: 5000+ (one per user)         │
└─────────────────────────────────────────┘
```

### Example 2: Internal BI Team (Private)
```
┌─────────────────────────────────────────┐
│  Channel: Internal BI                   │
├─────────────────────────────────────────┤
│  channel_id: "Internal-BI"              │
│  title: "تیم هوش مصنوعی داخلی"         │
│  access_type: "private"                 │
│  monthly_quota: 100000                  │
│  daily_quota: 5000                      │
│  rate_limit: 60                         │
│  max_history: 30                        │
│  default_model: "gpt-5-chat"            │
│  available_models: [gpt-5, claude-4]    │
│  allow_model_switch: true               │
├─────────────────────────────────────────┤
│  API Key: ark_internalbi456...          │
│  Users: 25 (team members)               │
│  Sessions: 25 (one per team member)     │
└─────────────────────────────────────────┘
```

### Example 3: Enterprise Client (Private)
```
┌─────────────────────────────────────────┐
│  Channel: HOSCO Popak                   │
├─────────────────────────────────────────┤
│  channel_id: "HOSCO-Popak"              │
│  title: "پلتفرم پوپک"                  │
│  access_type: "private"                 │
│  monthly_quota: null (unlimited)        │
│  daily_quota: null (unlimited)          │
│  rate_limit: 120                        │
│  max_history: 50                        │
│  default_model: "gpt-5-chat"            │
│  available_models: [gpt-5, opus-4]      │
│  allow_model_switch: true               │
├─────────────────────────────────────────┤
│  API Key: ark_hoscopopak789...          │
│  Users: 1000+ (app users)               │
│  Sessions: 1000+ (one per app user)     │
└─────────────────────────────────────────┘
```

---

## 🔐 AUTHENTICATION HIERARCHY

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION                           │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
        ┌───────▼────────┐         ┌────────▼────────┐
        │  SUPER ADMIN   │         │  CHANNEL KEY    │
        │     KEYS       │         │     (Client)    │
        └───────┬────────┘         └────────┬────────┘
                │                           │
    ┌───────────▼───────────┐   ┌──────────▼──────────┐
    │  Environment Variable │   │  Database Table     │
    │  SUPER_ADMIN_API_KEYS │   │    api_keys         │
    │  (Comma-separated)    │   │                     │
    └───────────┬───────────┘   └──────────┬──────────┘
                │                          │
    ┌───────────▼───────────┐   ┌──────────▼──────────┐
    │  Access Level         │   │  Access Level       │
    │  • ALL /v1/admin/*    │   │  • /v1/chat only    │
    │  • Create channels    │   │  • Cannot see admin │
    │  • Manage API keys    │   │  • Channel isolated │
    │  • View all usage     │   │                     │
    └───────────────────────┘   └─────────────────────┘
```

---

## 🌊 SESSION FLOW

```
USER makes request
    │
    ├─ user_id: "user_12345"
    ├─ channel: Internal-BI (from API key)
    │
    ▼
SESSION MANAGER
    │
    ├─ Session Key = (user_id + channel_id)
    ├─ Key = "user_12345:Internal-BI"
    │
    ├─ Check if session exists?
    │  │
    │  ├─ YES → Load existing session
    │  │         └─ Conversation history maintained
    │  │
    │  └─ NO  → Create new session
    │            └─ Fresh conversation
    │
    ▼
SESSION OBJECT
    │
    ├─ session_id: "uuid-1234-5678..."
    ├─ user_id: "user_12345"
    ├─ channel_id: 1 (Internal-BI)
    ├─ platform: "Internal-BI"
    ├─ current_model: "GPT-5 Chat"
    ├─ total_message_count: 24
    ├─ history: [msg1, msg2, ...]
    ├─ last_activity: datetime
    │
    └─ Isolation: User can only access their own session
                  within their channel
```

---

## 📊 USAGE TRACKING HIERARCHY

```
┌─────────────────────────────────────────┐
│         USAGE TRACKING                  │
└─────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │                         │
┌───▼──────┐          ┌───────▼────────┐
│ PER      │          │ AGGREGATED     │
│ REQUEST  │          │ STATISTICS     │
└───┬──────┘          └───────┬────────┘
    │                         │
    ▼                         ▼
usage_logs                UsageTracker
(Database)                (Service)
    │                         │
    ├─ api_key_id            ├─ get_channel_usage_stats()
    ├─ channel_id            ├─ get_api_key_usage_stats()
    ├─ user_id               └─ Returns:
    ├─ model_used                 │
    ├─ success                    ├─ Period (start, end)
    ├─ response_time              ├─ Requests (total, success, failed)
    ├─ cost                       ├─ Performance (avg response time)
    ├─ created_at                 ├─ Models (breakdown)
    └─ ...                        └─ Cost (total, currency)
```

---

## 🎯 FINAL SUMMARY

### What IS a "Channel"?
```
A CHANNEL is:
  ✅ A communication endpoint / integration point
  ✅ An external client using the chatbot service
  ✅ A platform connection (Telegram, Discord, Website, App)
  ✅ An organization/department using the service
  ✅ Each channel has its own API key, quotas, and config
  ✅ Complete isolation between channels

Examples:
  • Telegram Bot = 1 channel
  • Internal BI Dashboard = 1 channel
  • HOSCO Popak App = 1 channel
  • Marketing Platform = 1 channel
  • Customer Support Widget = 1 channel
```

### What is NOT a "Channel"?
```
A CHANNEL is NOT:
  ❌ A user (users belong to channels)
  ❌ A conversation (sessions belong to users in channels)
  ❌ A team of people (that's just the channel's title/name)
  ❌ A message (messages belong to sessions)
  ❌ An AI model (models are configured per channel)
```

### Architecture Benefits
```
✅ Clean separation of concerns
✅ Multi-tenant isolation (channels can't see each other)
✅ Flexible configuration (each channel customizable)
✅ Easy to add new integrations (just create new channel)
✅ Clear access control (channel key vs admin key)
✅ Accurate usage tracking (per channel, per user)
✅ Scalable (thousands of channels supported)
```

---

## 🔢 NUMERIC HIERARCHY

```
1 SERVICE
  │
  ├─ N SUPER ADMINS (environment keys)
  │
  └─ N CHANNELS
      │
      ├─ 1 API KEY per channel
      │
      ├─ N USERS per channel
      │   │
      │   └─ 1 SESSION per user (per channel)
      │       │
      │       └─ N MESSAGES per session
      │
      └─ N USAGE LOGS per channel
```

**Example:**
- 1 Service
  - 3 Super Admins
  - 10 Channels
    - 10 API Keys (one per channel)
    - 5,000 Users (across all channels)
      - 5,000 Sessions (one per user per channel)
        - 500,000 Messages (across all sessions)
    - 100,000 Usage Logs (across all channels)

---

**© 2025 Arash External API Service**
**Architecture: Channel-Based (v1.0.0)**
**Legacy "Teams" Removed: ✅ Complete**
