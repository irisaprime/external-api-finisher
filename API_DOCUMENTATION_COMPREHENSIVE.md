# Arash External API - Comprehensive Documentation

**Version:** 1.0.0
**Base URL:** `https://your-domain.com`
**Authentication:** Bearer Token (API Key)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Public Endpoints](#public-endpoints)
3. [Admin Endpoints](#admin-endpoints)
4. [Error Codes](#error-codes)
5. [Rate Limiting](#rate-limiting)
6. [Data Models](#data-models)
7. [Complete Examples](#complete-examples)

---

## Authentication

### Two-Tier Authentication System

#### 1. Channel API Keys (External Clients)
- **Purpose:** For external applications using the chat service
- **Storage:** Database (`api_keys` table)
- **Access:** `/v1/chat` and `/v1/commands` endpoints only
- **Format:** `ark_` prefix + 40 characters (SHA256 hash)

**Example:**
```http
Authorization: Bearer ark_1234567890abcdef1234567890abcdef12345678
```

#### 2. Super Admin API Keys (Infrastructure)
- **Purpose:** For platform administrators
- **Storage:** Environment variable `SUPER_ADMIN_API_KEYS`
- **Access:** All `/v1/admin/*` endpoints
- **Format:** Any string (comma-separated in env var)

**Example:**
```http
Authorization: Bearer your_super_admin_key_here
```

---

## Public Endpoints

### POST /v1/chat

Send a message and receive AI response.

#### Request

**Headers:**
```http
Content-Type: application/json
Authorization: Bearer <channel-api-key>
```

**Body Schema:**
```json
{
  "user_id": "string (required)",
  "text": "string (required)"
}
```

**Field Descriptions:**
- `user_id`: Unique user identifier (client-provided, e.g., telegram ID, customer ID)
- `text`: Message text or command (e.g., "/clear", "Hello")

#### All Request Variations

**1. First Message (New User):**
```json
{
  "user_id": "user_12345",
  "text": "سلام، چطوری؟"
}
```

**2. Continuing Conversation:**
```json
{
  "user_id": "user_12345",
  "text": "Tell me more about your services"
}
```

**3. Command Request:**
```json
{
  "user_id": "user_12345",
  "text": "/clear"
}
```

**4. Model Switch Command:**
```json
{
  "user_id": "user_12345",
  "text": "/model GPT-4o Mini"
}
```

**5. Long Text:**
```json
{
  "user_id": "user_12345",
  "text": "Very long message with lots of text that exceeds normal conversation length..."
}
```

**6. Special Characters:**
```json
{
  "user_id": "user_12345",
  "text": "Text with émojis 🎉 and spëcial çhars!"
}
```

**7. Persian/Arabic Text:**
```json
{
  "user_id": "telegram_987654",
  "text": "سلام! چطور می‌تونم کمکتون کنم؟"
}
```

**8. Code Block:**
```json
{
  "user_id": "dev_001",
  "text": "```python\nprint('Hello World')\n```"
}
```

#### All Response Scenarios

**1. Successful First Message (200):**
```json
{
  "success": true,
  "response": "سلام! چطور می‌تونم کمکتون کنم؟",
  "model": "Gemini 2.0 Flash",
  "total_message_count": 2
}
```

**2. Successful Continuing Conversation (200):**
```json
{
  "success": true,
  "response": "البته! خدمات ما شامل...",
  "model": "DeepSeek Chat V3",
  "total_message_count": 12
}
```

**3. After /clear Command (200):**
```json
{
  "success": true,
  "response": "✅ تاریخچه گفتگو پاک شد. می‌توانید مکالمه جدیدی شروع کنید.",
  "model": "GPT-4o Mini",
  "total_message_count": 26
}
```
*Note: total_message_count persists through /clear*

**4. After /model Switch (200):**
```json
{
  "success": true,
  "response": "✅ مدل به GPT-4o Mini تغییر کرد.",
  "model": "GPT-4o Mini",
  "total_message_count": 8
}
```

**5. Rate Limit Exceeded (200 with error):**
```json
{
  "success": false,
  "error": "rate_limit_exceeded",
  "response": "⚠️ محدودیت سرعت. لطفاً قبل از ارسال پیام بعدی کمی صبر کنید.\n\nمحدودیت: 60 پیام در دقیقه"
}
```

**6. AI Service Unavailable (200 with error):**
```json
{
  "success": false,
  "error": "ai_service_unavailable",
  "response": "متأسفم، سرویس هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً چند لحظه دیگر دوباره تلاش کنید."
}
```

**7. Access Denied (200 with error):**
```json
{
  "success": false,
  "error": "access_denied",
  "response": "❌ دسترسی رد شد. این مکالمه متعلق به API key دیگری است."
}
```
*When API key tries to access another key's user conversation*

**8. Quota Exceeded (200 with error):**
```json
{
  "success": false,
  "error": "quota_exceeded",
  "response": "⚠️ سهمیه استفاده به پایان رسیده است.\n\nسهمیه روزانه: 5000 (استفاده شده: 5000)\nسهمیه ماهانه: 100000 (استفاده شده: 95000)"
}
```

#### Error Responses

**1. Empty Text (400):**
```json
{
  "detail": "Message text cannot be empty"
}
```

**2. Empty User ID (400):**
```json
{
  "detail": "User ID cannot be empty"
}
```

**3. Missing Authorization (401):**
```json
{
  "detail": "Authentication required. Please provide an API key in the Authorization header."
}
```

**4. Invalid API Key (403):**
```json
{
  "detail": "Invalid API key. Please check your credentials."
}
```

**5. Inactive API Key (403):**
```json
{
  "detail": "API key is inactive or revoked"
}
```

**6. Expired API Key (403):**
```json
{
  "detail": "API key has expired"
}
```

**7. Validation Error (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "user_id"],
      "msg": "field required",
      "type": "value_error.missing"
    },
    {
      "loc": ["body", "text"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**8. Server Error (500):**
```json
{
  "detail": "An unexpected error occurred. Please try again later."
}
```

#### Complete cURL Examples

**1. Basic Chat Request:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ark_1234567890abcdef1234567890abcdef12345678" \
  -d '{
    "user_id": "user_12345",
    "text": "Hello, how can you help me?"
  }'
```

**2. Persian Text:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ark_1234567890abcdef1234567890abcdef12345678" \
  -d '{
    "user_id": "telegram_987654",
    "text": "سلام! چطور می‌تونم کمکتون کنم؟"
  }'
```

**3. Clear History Command:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ark_1234567890abcdef1234567890abcdef12345678" \
  -d '{
    "user_id": "user_12345",
    "text": "/clear"
  }'
```

**4. Model Switch:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ark_1234567890abcdef1234567890abcdef12345678" \
  -d '{
    "user_id": "user_12345",
    "text": "/model GPT-4o Mini"
  }'
```

---

### GET /v1/commands

Get list of available commands for current platform.

#### Request

**Headers:**
```http
Authorization: Bearer <channel-api-key>
```

**No Body Required**

#### All Response Scenarios

**1. Telegram Platform (Public) (200):**
```json
{
  "success": true,
  "platform": "telegram",
  "commands": [
    {
      "command": "/start",
      "description": "شروع مکالمه و نمایش پیام خوش‌آمدگویی"
    },
    {
      "command": "/help",
      "description": "نمایش راهنمای استفاده و دستورات موجود"
    },
    {
      "command": "/status",
      "description": "نمایش وضعیت نشست شما"
    },
    {
      "command": "/clear",
      "description": "پاک کردن تاریخچه گفتگو"
    },
    {
      "command": "/model",
      "description": "تغییر مدل هوش مصنوعی فعلی"
    },
    {
      "command": "/models",
      "description": "نمایش لیست مدل‌های موجود"
    }
  ]
}
```

**2. Internal Platform (Private) (200):**
```json
{
  "success": true,
  "platform": "Internal-BI",
  "commands": [
    {
      "command": "/start",
      "description": "شروع مکالمه"
    },
    {
      "command": "/help",
      "description": "نمایش راهنما"
    },
    {
      "command": "/model",
      "description": "تغییر مدل"
    },
    {
      "command": "/models",
      "description": "لیست مدل‌ها"
    },
    {
      "command": "/clear",
      "description": "پاک کردن تاریخچه"
    },
    {
      "command": "/status",
      "description": "نمایش وضعیت"
    }
  ]
}
```

#### Error Responses

**1. Missing Authorization (401):**
```json
{
  "detail": "Authentication required"
}
```

**2. Invalid API Key (403):**
```json
{
  "detail": "Invalid API key"
}
```

---

## Admin Endpoints

### POST /v1/admin/channels

Create a new channel with auto-generated API key.

⚠️ **SUPER ADMIN ONLY**

#### Request

**Headers:**
```http
Content-Type: application/json
Authorization: Bearer <super-admin-key>
```

**Body Schema:**
```json
{
  "channel_id": "string (required)",
  "title": "string (optional)",
  "access_type": "string (default: 'private')",
  "monthly_quota": "integer (optional)",
  "daily_quota": "integer (optional)",
  "rate_limit": "integer (optional)",
  "max_history": "integer (optional)",
  "default_model": "string (optional)",
  "available_models": ["string"] "(optional)",
  "allow_model_switch": "boolean (optional)"
}
```

#### All Request Variations

**1. Minimal Request (Required Fields Only):**
```json
{
  "channel_id": "Marketing-Platform"
}
```
*Creates channel with defaults*

**2. With Title (Persian):**
```json
{
  "channel_id": "Internal-BI",
  "title": "تیم هوش مصنوعی داخلی"
}
```

**3. With Quotas:**
```json
{
  "channel_id": "External-Marketing",
  "title": "Marketing Platform",
  "monthly_quota": 100000,
  "daily_quota": 5000
}
```

**4. Unlimited Quotas:**
```json
{
  "channel_id": "VIP-Customer",
  "monthly_quota": null,
  "daily_quota": null
}
```

**5. With Platform Overrides:**
```json
{
  "channel_id": "HOSCO-Popak",
  "title": "پلتفرم پوپک",
  "access_type": "private",
  "rate_limit": 80,
  "max_history": 25,
  "default_model": "openai/gpt-5-chat",
  "available_models": ["openai/gpt-5-chat", "google/gemini-2.0-flash-001"],
  "allow_model_switch": true
}
```

**6. Public Platform (Telegram-like):**
```json
{
  "channel_id": "Discord-Bot",
  "title": "Discord Integration",
  "access_type": "public",
  "monthly_quota": 500000,
  "daily_quota": 20000,
  "rate_limit": 20,
  "max_history": 10
}
```

**7. Complete Configuration:**
```json
{
  "channel_id": "Enterprise-Client-A",
  "title": "شرکت بزرگ الف",
  "access_type": "private",
  "monthly_quota": 1000000,
  "daily_quota": 50000,
  "rate_limit": 120,
  "max_history": 50,
  "default_model": "openai/gpt-5-chat",
  "available_models": [
    "openai/gpt-5-chat",
    "anthropic/claude-opus-4",
    "google/gemini-2.0-flash-001",
    "deepseek/deepseek-chat-v3-0324"
  ],
  "allow_model_switch": true
}
```

#### All Response Scenarios

**1. Successful Creation (200):**
```json
{
  "id": 1,
  "channel_id": "Internal-BI",
  "title": "تیم هوش مصنوعی داخلی",
  "access_type": "private",
  "monthly_quota": 100000,
  "daily_quota": 5000,
  "is_active": true,
  "rate_limit": 60,
  "max_history": 30,
  "default_model": "openai/gpt-5-chat",
  "available_models": ["openai/gpt-5-chat", "google/gemini-2.0-flash-001"],
  "allow_model_switch": true,
  "created_at": "2025-01-15T10:00:00",
  "api_key": "ark_1234567890abcdef1234567890abcdef12345678",
  "warning": "⚠️ IMPORTANT: Save this API key securely. It will NOT be shown again!"
}
```

**2. Channel with Defaults:**
```json
{
  "id": 2,
  "channel_id": "Marketing-Platform",
  "title": "Marketing-Platform",
  "access_type": "private",
  "monthly_quota": null,
  "daily_quota": null,
  "is_active": true,
  "rate_limit": 60,
  "max_history": 30,
  "default_model": "openai/gpt-5-chat",
  "available_models": null,
  "allow_model_switch": true,
  "created_at": "2025-01-15T10:05:00",
  "api_key": "ark_abcdefghijklmnopqrstuvwxyz1234567890abcd"
}
```

#### Error Responses

**1. Channel ID Already Exists (400):**
```json
{
  "detail": "Channel with ID 'Internal-BI' already exists"
}
```

**2. Invalid channel_id Format (400):**
```json
{
  "detail": "channel_id must be ASCII characters without spaces"
}
```

**3. Invalid Quota (400):**
```json
{
  "detail": "Quota values must be positive integers"
}
```

**4. Missing Authorization (401):**
```json
{
  "detail": "Authentication required"
}
```

**5. Super Admin Not Configured (401):**
```json
{
  "detail": "Super admin authentication not configured"
}
```

**6. Invalid Super Admin Key (403):**
```json
{
  "detail": "Invalid super admin API key"
}
```

**7. Validation Error (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "channel_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**8. Database Error (500):**
```json
{
  "detail": "Failed to create channel due to database error"
}
```

**9. API Key Generation Error (500):**
```json
{
  "detail": "Channel created but failed to generate API key"
}
```

#### Complete cURL Examples

**1. Minimal Channel:**
```bash
curl -X POST https://your-domain.com/v1/admin/channels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_super_admin_key" \
  -d '{
    "channel_id": "Marketing-Platform"
  }'
```

**2. With Quotas:**
```bash
curl -X POST https://your-domain.com/v1/admin/channels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_super_admin_key" \
  -d '{
    "channel_id": "Internal-BI",
    "title": "تیم هوش مصنوعی داخلی",
    "monthly_quota": 100000,
    "daily_quota": 5000
  }'
```

**3. Complete Configuration:**
```bash
curl -X POST https://your-domain.com/v1/admin/channels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_super_admin_key" \
  -d '{
    "channel_id": "Enterprise-Client",
    "title": "Enterprise Client A",
    "access_type": "private",
    "monthly_quota": 1000000,
    "daily_quota": 50000,
    "rate_limit": 120,
    "max_history": 50,
    "default_model": "openai/gpt-5-chat",
    "available_models": ["openai/gpt-5-chat", "anthropic/claude-opus-4"],
    "allow_model_switch": true
  }'
```

---

### GET /v1/admin/channels

Get list of channels with usage statistics.

⚠️ **SUPER ADMIN ONLY**

#### Request

**Headers:**
```http
Authorization: Bearer <super-admin-key>
```

**Query Parameters:**
- `channel_id` (integer, optional): Get specific channel by ID
- `active_only` (boolean, default: true): Filter active channels only
- `days` (integer, default: 30): Days for usage statistics
- `totally` (boolean, default: false): Include total aggregated report

#### All Request Variations

**1. List All Active Channels:**
```http
GET /v1/admin/channels
```

**2. List All Channels (Including Inactive):**
```http
GET /v1/admin/channels?active_only=false
```

**3. Get Specific Channel:**
```http
GET /v1/admin/channels?channel_id=1
```

**4. Last 7 Days Usage:**
```http
GET /v1/admin/channels?days=7
```

**5. With Total Report:**
```http
GET /v1/admin/channels?totally=true
```

**6. Complete Filter:**
```http
GET /v1/admin/channels?active_only=false&days=90&totally=true
```

**7. Specific Channel with 30-Day Usage:**
```http
GET /v1/admin/channels?channel_id=1&days=30
```

#### All Response Scenarios

**1. List of Channels (200):**
```json
{
  "channels": [
    {
      "id": 1,
      "channel_id": "Internal-BI",
      "title": "تیم هوش مصنوعی داخلی",
      "access_type": "private",
      "monthly_quota": 100000,
      "daily_quota": 5000,
      "is_active": true,
      "rate_limit": 60,
      "max_history": 30,
      "default_model": "openai/gpt-5-chat",
      "available_models": ["openai/gpt-5-chat", "google/gemini-2.0-flash-001"],
      "allow_model_switch": true,
      "api_key_prefix": "ark_1234",
      "api_key_last_used": "2025-01-15T14:30:00",
      "created_at": "2025-01-01T10:00:00",
      "updated_at": "2025-01-15T14:30:00",
      "usage": {
        "period": {
          "start": "2024-12-16",
          "end": "2025-01-15"
        },
        "requests": {
          "total": 15000,
          "successful": 14850,
          "failed": 150,
          "success_rate": 99.0
        },
        "performance": {
          "avg_response_time_ms": 850.5
        },
        "models": [
          {
            "model": "openai/gpt-5-chat",
            "requests": 12000
          },
          {
            "model": "google/gemini-2.0-flash-001",
            "requests": 3000
          }
        ],
        "cost": {
          "total": 125.50,
          "currency": "USD"
        }
      }
    },
    {
      "id": 2,
      "channel_id": "Marketing-Platform",
      "title": "Marketing Platform",
      "access_type": "private",
      "monthly_quota": null,
      "daily_quota": null,
      "is_active": true,
      "api_key_prefix": "ark_5678",
      "api_key_last_used": null,
      "created_at": "2025-01-10T15:00:00",
      "updated_at": "2025-01-10T15:00:00",
      "usage": {
        "requests": {
          "total": 0,
          "successful": 0,
          "failed": 0
        }
      }
    }
  ],
  "total_report": null
}
```

**2. With Total Report (200):**
```json
{
  "channels": [...],
  "total_report": {
    "total_channels": 5,
    "active_channels": 4,
    "total_requests": 75000,
    "total_successful": 74250,
    "total_failed": 750,
    "success_rate": 99.0,
    "total_cost": 375.50
  }
}
```

**3. Specific Channel (200):**
```json
{
  "channels": [
    {
      "id": 1,
      "channel_id": "Internal-BI",
      "title": "تیم هوش مصنوعی داخلی",
      ...
    }
  ],
  "total_report": null
}
```

**4. Empty List (No Channels) (200):**
```json
{
  "channels": [],
  "total_report": null
}
```

**5. Inactive Channels Included (200):**
```json
{
  "channels": [
    {
      "id": 3,
      "channel_id": "Old-Platform",
      "is_active": false,
      ...
    }
  ]
}
```

#### Error Responses

**1. Channel Not Found (404):**
```json
{
  "detail": "Channel not found"
}
```

**2. Missing Authorization (401):**
```json
{
  "detail": "Authentication required"
}
```

**3. Invalid Super Admin Key (403):**
```json
{
  "detail": "Invalid super admin API key"
}
```

**4. Server Error (500):**
```json
{
  "detail": "An unexpected error occurred"
}
```

#### Complete cURL Examples

**1. List All Channels:**
```bash
curl -X GET https://your-domain.com/v1/admin/channels \
  -H "Authorization: Bearer your_super_admin_key"
```

**2. Get Specific Channel:**
```bash
curl -X GET "https://your-domain.com/v1/admin/channels?channel_id=1" \
  -H "Authorization: Bearer your_super_admin_key"
```

**3. Last 7 Days with Total:**
```bash
curl -X GET "https://your-domain.com/v1/admin/channels?days=7&totally=true" \
  -H "Authorization: Bearer your_super_admin_key"
```

**4. All Channels (Including Inactive):**
```bash
curl -X GET "https://your-domain.com/v1/admin/channels?active_only=false" \
  -H "Authorization: Bearer your_super_admin_key"
```

---

### PATCH /v1/admin/channels/{channel_id}

Update an existing channel.

⚠️ **SUPER ADMIN ONLY**

#### Request

**Headers:**
```http
Content-Type: application/json
Authorization: Bearer <super-admin-key>
```

**Path Parameters:**
- `channel_id` (integer, required): Channel ID to update

**Body Schema:**
```json
{
  "title": "string (optional)",
  "channel_id": "string (optional)",
  "access_type": "string (optional)",
  "monthly_quota": "integer (optional)",
  "daily_quota": "integer (optional)",
  "is_active": "boolean (optional)",
  "rate_limit": "integer (optional)",
  "max_history": "integer (optional)",
  "default_model": "string (optional)",
  "available_models": ["string"] "(optional)",
  "allow_model_switch": "boolean (optional)"
}
```

#### All Request Variations

**1. Update Title Only:**
```json
{
  "title": "Updated Channel Name"
}
```

**2. Change Channel ID:**
```json
{
  "channel_id": "Internal-BI-Updated"
}
```

**3. Deactivate Channel:**
```json
{
  "is_active": false
}
```

**4. Reactivate Channel:**
```json
{
  "is_active": true
}
```

**5. Update Quotas:**
```json
{
  "monthly_quota": 150000,
  "daily_quota": 7000
}
```

**6. Remove Quotas (Set Unlimited):**
```json
{
  "monthly_quota": null,
  "daily_quota": null
}
```

**7. Update Platform Config:**
```json
{
  "rate_limit": 80,
  "max_history": 25,
  "default_model": "anthropic/claude-opus-4",
  "available_models": ["anthropic/claude-opus-4", "openai/gpt-5-chat"],
  "allow_model_switch": false
}
```

**8. Reset to Defaults (Set NULL):**
```json
{
  "rate_limit": null,
  "max_history": null,
  "default_model": null,
  "available_models": null,
  "allow_model_switch": null
}
```

**9. Complete Update:**
```json
{
  "title": "Updated Name",
  "channel_id": "New-Channel-ID",
  "access_type": "public",
  "monthly_quota": 200000,
  "daily_quota": 10000,
  "is_active": true,
  "rate_limit": 100,
  "max_history": 40,
  "default_model": "google/gemini-2.0-flash-001",
  "available_models": ["google/gemini-2.0-flash-001", "deepseek/deepseek-chat-v3-0324"],
  "allow_model_switch": true
}
```

#### All Response Scenarios

**1. Successful Update (200):**
```json
{
  "id": 1,
  "channel_id": "Internal-BI-Updated",
  "title": "Updated Channel Name",
  "access_type": "private",
  "monthly_quota": 150000,
  "daily_quota": 7000,
  "is_active": true,
  "rate_limit": 80,
  "max_history": 25,
  "default_model": "anthropic/claude-opus-4",
  "available_models": ["anthropic/claude-opus-4", "openai/gpt-5-chat"],
  "allow_model_switch": false,
  "api_key_prefix": "ark_1234",
  "api_key_last_used": "2025-01-15T14:30:00",
  "created_at": "2025-01-01T10:00:00",
  "updated_at": "2025-01-16T09:15:00"
}
```

**2. Deactivated Channel (200):**
```json
{
  "id": 1,
  "is_active": false,
  ...
}
```

**3. Reset to Defaults (200):**
```json
{
  "id": 1,
  "rate_limit": null,
  "max_history": null,
  "default_model": null,
  ...
}
```

#### Error Responses

**1. Channel Not Found (404):**
```json
{
  "detail": "Channel not found"
}
```

**2. Channel ID Already Exists (400):**
```json
{
  "detail": "Channel ID 'Internal-BI-v2' is already in use by another channel"
}
```

**3. Invalid Quota (400):**
```json
{
  "detail": "Quota values must be positive integers or null"
}
```

**4. No Fields Provided (400):**
```json
{
  "detail": "At least one field must be provided for update"
}
```

**5. Missing Authorization (401):**
```json
{
  "detail": "Authentication required"
}
```

**6. Invalid Super Admin Key (403):**
```json
{
  "detail": "Invalid super admin API key"
}
```

**7. Server Error (500):**
```json
{
  "detail": "Failed to update channel"
}
```

#### Complete cURL Examples

**1. Update Title:**
```bash
curl -X PATCH https://your-domain.com/v1/admin/channels/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_super_admin_key" \
  -d '{
    "title": "Updated Channel Name"
  }'
```

**2. Deactivate Channel:**
```bash
curl -X PATCH https://your-domain.com/v1/admin/channels/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_super_admin_key" \
  -d '{
    "is_active": false
  }'
```

**3. Update Quotas:**
```bash
curl -X PATCH https://your-domain.com/v1/admin/channels/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_super_admin_key" \
  -d '{
    "monthly_quota": 200000,
    "daily_quota": 10000
  }'
```

---

### GET /v1/admin/

Admin dashboard with platform statistics.

⚠️ **SUPER ADMIN ONLY**

#### Request

**Headers:**
```http
Authorization: Bearer <super-admin-key>
```

**No Query Parameters or Body**

#### Response (200)

```json
{
  "service": "Arash External API Service",
  "version": "1.0.0",
  "status": "healthy",
  "timestamp": "2025-01-15T14:30:00",
  "platforms": {
    "telegram": {
      "type": "public",
      "model": "Gemini 2.0 Flash",
      "rate_limit": 20,
      "commands": ["start", "help", "clear", "model", "models", "status"]
    },
    "internal": {
      "type": "private",
      "default_model": "GPT-5 Chat",
      "available_models": ["GPT-5 Chat", "Gemini 2.0 Flash", "DeepSeek Chat V3"],
      "rate_limit": 60
    }
  },
  "statistics": {
    "total_sessions": 150,
    "active_sessions": 25,
    "total_channels": 5,
    "active_channels": 4
  }
}
```

#### Error Responses

**Same as other admin endpoints (401, 403, 500)**

---

## Error Codes

### HTTP Status Codes

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid input data |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Valid auth but insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Server-side error |

### Application Error Codes

| Error Code | Meaning | HTTP Status |
|------------|---------|-------------|
| `rate_limit_exceeded` | Too many requests | 200 (with error) |
| `quota_exceeded` | Usage quota exceeded | 200 (with error) |
| `ai_service_unavailable` | AI service is down | 200 (with error) |
| `access_denied` | Cannot access resource | 200 (with error) |
| `authentication_failed` | Invalid credentials | 403 |
| `validation_error` | Invalid request data | 422 |

---

## Rate Limiting

### Per-Channel Rate Limits

**Default Limits:**
- **Public platforms:** 20 requests/minute
- **Private platforms:** 60 requests/minute

**Custom Limits:**
Can be configured per-channel during creation or update.

### Rate Limit Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705329600
```

### Rate Limit Exceeded Response

```json
{
  "success": false,
  "error": "rate_limit_exceeded",
  "response": "⚠️ محدودیت سرعت. لطفاً قبل از ارسال پیام بعدی کمی صبر کنید.\n\nمحدودیت: 60 پیام در دقیقه",
  "retry_after": 30
}
```

---

## Data Models

### Channel Object

```json
{
  "id": "integer",
  "channel_id": "string (unique identifier)",
  "title": "string (human-friendly name)",
  "access_type": "string (public|private)",
  "monthly_quota": "integer|null (null = unlimited)",
  "daily_quota": "integer|null (null = unlimited)",
  "is_active": "boolean",
  "rate_limit": "integer|null (requests/min, null = use default)",
  "max_history": "integer|null (messages in context, null = use default)",
  "default_model": "string|null (AI model, null = use default)",
  "available_models": "array|null (model list, null = use default)",
  "allow_model_switch": "boolean|null (null = use default)",
  "api_key_prefix": "string (first 8 chars of API key)",
  "api_key_last_used": "datetime|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Usage Statistics Object

```json
{
  "period": {
    "start": "date",
    "end": "date"
  },
  "requests": {
    "total": "integer",
    "successful": "integer",
    "failed": "integer",
    "success_rate": "float (percentage)"
  },
  "performance": {
    "avg_response_time_ms": "float"
  },
  "models": [
    {
      "model": "string",
      "requests": "integer"
    }
  ],
  "cost": {
    "total": "float",
    "currency": "string (USD)"
  }
}
```

---

## Complete Examples

### Example 1: Create Channel and Use It

**Step 1: Create Channel (Admin)**
```bash
curl -X POST https://your-domain.com/v1/admin/channels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin_super_key_123" \
  -d '{
    "channel_id": "my-app",
    "title": "My Application",
    "monthly_quota": 100000,
    "daily_quota": 5000
  }'
```

**Response:**
```json
{
  "id": 5,
  "channel_id": "my-app",
  "title": "My Application",
  "api_key": "ark_abcd1234efgh5678ijkl9012mnop3456qrst7890",
  "warning": "⚠️ Save this API key!"
}
```

**Step 2: Use API Key for Chat**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ark_abcd1234efgh5678ijkl9012mnop3456qrst7890" \
  -d '{
    "user_id": "customer_001",
    "text": "Hello!"
  }'
```

**Response:**
```json
{
  "success": true,
  "response": "Hello! How can I help you today?",
  "model": "GPT-5 Chat",
  "total_message_count": 2
}
```

### Example 2: Complete Conversation Flow

**Message 1:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Authorization: Bearer ark_..." \
  -d '{"user_id": "user_123", "text": "What is AI?"}'
```
Response: Explanation of AI, `total_message_count: 2`

**Message 2:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Authorization: Bearer ark_..." \
  -d '{"user_id": "user_123", "text": "Tell me more"}'
```
Response: More details, `total_message_count: 4`

**Clear History:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Authorization: Bearer ark_..." \
  -d '{"user_id": "user_123", "text": "/clear"}'
```
Response: History cleared, `total_message_count: 4` (persists!)

**New Message After Clear:**
```bash
curl -X POST https://your-domain.com/v1/chat \
  -H "Authorization: Bearer ark_..." \
  -d '{"user_id": "user_123", "text": "New topic"}'
```
Response: Fresh conversation, `total_message_count: 6`

### Example 3: Monitor Usage (Admin)

**Get Channel Statistics:**
```bash
curl -X GET "https://your-domain.com/v1/admin/channels?channel_id=5&days=7" \
  -H "Authorization: Bearer admin_super_key_123"
```

**Response:**
```json
{
  "channels": [
    {
      "id": 5,
      "channel_id": "my-app",
      "usage": {
        "requests": {
          "total": 1250,
          "successful": 1248,
          "failed": 2
        },
        "cost": {
          "total": 12.50
        }
      }
    }
  ]
}
```

---

## API Best Practices

### 1. Error Handling
```python
import requests

response = requests.post(
    "https://your-domain.com/v1/chat",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"user_id": user_id, "text": text}
)

if response.status_code == 200:
    data = response.json()
    if data["success"]:
        print(data["response"])
    else:
        # Handle application errors
        if data["error"] == "rate_limit_exceeded":
            print("Please wait before sending next message")
        elif data["error"] == "quota_exceeded":
            print("Usage quota exceeded")
elif response.status_code == 401:
    print("Invalid API key")
elif response.status_code == 403:
    print("Access denied")
```

### 2. Retry Logic
```python
import time

def send_message_with_retry(api_key, user_id, text, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(...)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:  # Rate limit
            time.sleep(2 ** attempt)  # Exponential backoff
        else:
            raise Exception(f"Error: {response.status_code}")

    raise Exception("Max retries exceeded")
```

### 3. Session Management
```python
# Reuse the same user_id for conversation continuity
user_id = "customer_12345"

# First message
chat(user_id, "Hello")

# Continue conversation (history is maintained)
chat(user_id, "Tell me more")

# Clear when needed
chat(user_id, "/clear")

# Start fresh topic
chat(user_id, "New question")
```

---

## Changelog

### Version 1.0.0 (2025-01-22)
- Initial release
- Channel-based architecture
- Two-tier authentication
- Multi-model AI support
- Usage tracking and quotas
- Persian/Farsi support

---

## Support

For API support, contact: support@your-domain.com

For technical documentation updates, visit: https://docs.your-domain.com

---

**© 2025 Arash External API Service. All rights reserved.**
