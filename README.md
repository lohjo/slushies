# AgnesClaw — agnes-hlm

A 24/7 voice-directed AI co-pilot for **Heartland Merchants** (neighbourhood
mini-marts, provision shops, kopitiams, hawker stalls). Built for the AgnesAI @
SMU Agnes Hackathon.

AgnesClaw runs in the storefront and autonomously: drafts replies to customer
reviews and messages, aggregates footfall & sales trends, suggests inventory
adjustments from local demand signals, coordinates a student-volunteer network
over Telegram/WhatsApp, and monitors customer sentiment across Google Reviews,
Facebook, Instagram, and Reddit — keeping persistent memory of the merchant's
preferences, product catalogue, and past interactions.

It is the **Heartland-Merchant adaptation of the SOAR surgical co-pilot**: the
clinical surface is stripped, but the full infrastructure is retained — CI/CD
pipeline, ADK multi-agent orchestration, grounding layer, WebSocket transport,
bidirectional native-audio streaming, and session management.

This repo contains two layers:

| Layer | Path | Purpose |
|---|---|---|
| **Live runtime** | `app/` | FastAPI + Gemini Live + ADK multi-agent voice console (focus of this guide) |
| **Memory/scheduler helpers** | `agnes_claw/` | Lightweight persistent-memory, drafting, scheduling and webhook utilities (`update_identity`, `update_soul`, scheduled-task templates) — see the Appendix |

---

## Architecture

```
Google Cloud Storage (assets)  ──►  Cloud Build (cloudbuild.yaml, auto-deploy on push to main)
                                          │  docker build + push → Artifact Registry
                                          ▼
                              Cloud Run — FastAPI (app/main.py)
   ┌──────────────────────────────────────────────────────────────────────┐
   │ WebSocket  /ws/{user_id}/{session_id}                                  │
   │   upstream_task()   browser → Vertex AI (3200-byte PCM, JPEG frames)   │
   │   downstream_task() Vertex AI → browser (audio, text, function calls)  │
   │ Webhooks   /webhook/whatsapp   /webhook/telegram                       │
   │ Vertex AI — Gemini Live (gemini-live-2.5-flash-native-audio)           │
   │   StreamingMode.BIDI · AUDIO out · barge-in · Charon voice · live ASR  │
   │ ADK multi-agent runtime (run_live, LiveRequestQueue)                   │
   │ Firestore-backed tenant persistence (hydrate on connect, flush on close)│
   └──────────────────────────────────────────────────────────────────────┘
```

### Domain mapping: SOAR clinical → AgnesClaw commerce

| SOAR | AgnesClaw |
|---|---|
| Surgeon / Patient data | Merchant / Merchant data (catalog, inventory, suppliers, revenue) |
| Surgical phase | Business operations phase (morning prep, peak hours, closing, off hours) |
| Complication protocol | Crisis protocol (viral review, supply disruption, health inspection, staff shortage, equipment breakdown) |
| WHO checklist / EBL tracker | Opening/closing checklists / inventory tracker |
| Operative report | Daily sales / weekly trend report |
| Visual Assistant (screen) | Visual Assistant (social feeds, Google reviews, dashboards) |

---

<root_agent>
**Root Orchestrator — `hlm_Orchestrator`** (`app/hlm_orchestrator/agent.py`)

Handles all voice input, applies wake-word filtering, and either calls direct
tools (single + parallel multi-action commands) or routes to a specialist
sub-agent via `transfer_to_agent()`. Built on Google ADK `LlmAgent` with:

- `model = os.environ.get('DEMO_AGENT_MODEL', 'gemini-live-2.5-flash-native-audio')`
- `before_tool_callback = grounding_before_tool` (argument whitelisting)
- `after_tool_callback = grounding_after_tool` (render_command schema validation)
- `runner.run_live()` with `StreamingMode.BIDI`, `response_modalities=['AUDIO']`
- Custom voice persona via `PrebuiltVoiceConfig(voice_name='Charon')`
- `AudioTranscriptionConfig` on both input and output for live transcription
</root_agent>

<subagents>
| Agent | Trigger phrases | Priority |
|---|---|---|
| **Message_Agent** | "draft a reply", "message my supplier", "any customer issues" | P0 |
| **Marketing_Agent** | "generate the image", "make a poster/video", "what should I promote" | P0 |
| **Trend_Engine** | "weekly report", "footfall patterns", "sales trends", "sentiment trend" | P0 |
| **Complication_Advisor** | "I don't know what to do", "health inspector came", "supplier didn't deliver", "chiller broke", "short-staffed" | P1 |
| **Visual_Assistant** | "monitor my screen", "scan my reviews", "watch my social feed", "what do you see" | P1 |
</subagents>

<feature_cards>
Eight vanilla-JS display panels (`app/static/js/`), each driven by
`render_command` objects over the WebSocket:

1. `merchant-panel.js` — merchant profile, fields, inventory vs reorder points
2. `sentiment-card.js` — aggregated sentiment, theme chips, mention navigator, footfall trend
3. `message-card.js` — WhatsApp/Telegram inbound + outbound chat bubbles
4. `checklist-panel.js` — operational-phase checklists + crisis protocols
5. `log-panel.js` — timestamped event log + shop-photo capture
6. `summary-panel.js` — formatted agent summaries (reports, drafts, protocols)
7. `marketing-card.js` — generated posters / images / video from the Agnes API
8. `hecs-card.js` — HECS micro-training module recommendations
</feature_cards>

<design-decisions>
1. **Progressive trust extraction** — `_MERCHANT_DATA` fields carry an
   `extracted_session`; the dynamic system prompt references only fields gathered
   up to the current session, and emits cold-start nudges otherwise
   (`build_dynamic_instruction`).
2. **Confidence-aware hedging** — inferred fields (e.g. `reorder_points`,
   `confidence: 0.6`) get a hedge suffix so Agnes asks to confirm
   (`hedge_for_confidence`).
3. **Structured suppliers, not flat lists** — nested supplier structs preserve
   frequency, lead time, and payment terms.
4. **No PII** — plausible but anonymous fixture; phone numbers are fake.
5. **Grounding layer** — every whitelisted tool argument is validated before
   execution; every success response must carry a `render_command`.
6. **Firestore-backed persistence** — tenant merchant data hydrates session state
   on connect and flushes on disconnect; degrades to the in-code fixture when
   Firestore/credentials are absent.
7. **Graceful channel degradation** — every external integration returns a
   `simulated`/empty result when credentials are missing, so the console runs offline.
</design-decisions>

---

## Project structure

```
agnes-hlm/
├── app/
│   ├── main.py                     # FastAPI: WebSocket + WhatsApp/Telegram webhooks
│   ├── .env.template
│   ├── hlm_orchestrator/
│   │   ├── __init__.py             # exports root_agent, log_ai_interaction
│   │   ├── agent.py                # hlm_Orchestrator + 5 sub-agents
│   │   ├── tools.py                # all tools (render_command contract)
│   │   ├── grounding.py            # whitelists + before/after callbacks
│   │   └── merchant_data.py        # _MERCHANT_DATA + progressive extraction
│   ├── integrations/
│   │   ├── whatsapp.py telegram.py facebook.py instagram.py
│   │   ├── reddit.py   google_maps.py agnes_api.py
│   │   └── firestore_session.py    # tenant load/save
│   └── static/
│       ├── landing.html index.html favicon.svg
│       ├── css/tokens.css
│       └── js/  app.js + 8 feature cards + audio worklets + screenshare
├── agnes_claw/                     # lightweight memory/scheduler helpers (+ tests)
├── tests/                          # test_tools, test_grounding, test_hlm_integrations, …
├── Dockerfile cloudbuild.yaml pyproject.toml
```

---

## Local setup

### Prerequisites
- Python 3.11+
- `gcloud` CLI authenticated (`gcloud auth application-default login`)
- A GCP project with Vertex AI enabled (for the voice console)
- (Optional) Firebase/Firestore for cross-restart persistence; channel API keys

### Install & run
```bash
cd agnes-hlm
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp app/.env.template app/.env       # set GOOGLE_CLOUD_PROJECT + DEMO_AGENT_MODEL
gcloud auth application-default login
gcloud config set project your-gcp-project-id

cd app
uvicorn main:app --reload --port 8080
```
> **Critical:** run `uvicorn` from inside `app/` — running from the project root
> causes `ModuleNotFoundError` for `hlm_orchestrator`. **Never commit `app/.env`.**

Open the console at <http://localhost:8080/console> (landing page at
<http://localhost:8080>), click the orb to connect, allow the microphone, then
say **"Agnes, check my customer reviews."**

<deployment>
Push to `main` triggers Cloud Build (`cloudbuild.yaml`): docker build → push to
Artifact Registry → deploy to Cloud Run (`agnes-hlm`, port 8080, 2Gi/2cpu,
`--timeout=3600` for long-lived WebSockets). Model id, GCS bucket, tenant id, and
all channel secrets are managed on the Cloud Run service and kept out of source
control (`--update-env-vars` preserves them across redeploys).
</deployment>

---

## Tests

```bash
pip install -e ".[dev]" && pytest          # unified runner — all 35 tests (app/ + agnes_claw)
python -m unittest discover -s tests -q      # legacy agnes_claw helpers (run from repo root)
```
> The `app/` runtime tests use pytest fixtures (`monkeypatch`), so `pytest` is the
> primary runner. The legacy `unittest discover` command still works — it imports
> the app test modules cleanly but collects only the `agnes_claw` `TestCase`s.

`tests/test_tools.py` asserts the `render_command` contract for every tool,
`tests/test_grounding.py` covers whitelist enforcement, and
`tests/test_hlm_integrations.py` covers channel parsing + graceful degradation.

---

# Appendix — Original scheduled-task & channel design guide

The sections below are the original AgnesClaw design notes for the always-on
scheduled-task layer (`agnes_claw/`): persistent memory (`update_identity`,
`update_soul`), cron task templates, the drafting pipeline, and the
Telegram/WhatsApp webhook reference. They complement the live runtime above.

## Architecture Overview

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    AgnesClaw Orchestrator                 │
│  (Scheduled Tasks → Worker Agents → Specialist Delegates) │
└──────┬──────────┬──────────┬──────────┬────────────────┘
       │          │          │          │
  ┌────▼───┐ ┌───▼────┐ ┌──▼────┐ ┌───▼─────┐
  │Monitor │ │Draft   │ │Trend  │ │Coordinate│
  │Worker  │ │Responses│ │Engine │ │Volunteers│
  └────┬───┘ └────┬───┘ └───┬───┘ └────┬────┘
       │          │          │           │
       ▼          ▼          ▼           ▼
  ┌──────────────────────────────────────────────┐
  │         Persistent Memory Layer               │
  │  Identity (merchant, catalog, roster)         │
  │  Soul (tone rules, language prefs)            │
  └──────────────────────────────────────────────┘
                            ▲
                            │
              ┌─────────────┴──────────────┐
              │     External Channels       │
              │ Telegram / WhatsApp Webhooks│
              └────────────────────────────┘
```

---

## Phase 1: Persistent Memory Setup

### 1a. Identity Configuration (`update_identity`)

Records WHO the merchant/volunteer network is — long-term facts the agent draws on.

```python
# Call once during initial setup
update_identity(
    content="""
    Merchant profile:
    - Name: "Kopi & Rempah" (fictional example; replace with actual)
    - Location: Kampong Glam, Singapore
    - Cuisine: Modern Southeast Asian cafe
    - Product catalog: Coffee blends (single-origin Ethiopian, house blend),
      food items (garlic pork ribs, spicy laksa, kaya toast), seasonal specials
    - Operating hours: Mon-Sun 08:00-22:00
    - Peak footfall days: Saturdays and Sundays
    
    Volunteer network:
    - Coordinator: "Wei Ming" (lead volunteer, handles shift scheduling)
    - Members: [list names, roles, availability windows]
    - Contact method: Telegram group @kopia_rremah_volunteers
    """
)
```

**Why this matters:** Every subsequent task execution inherits this context automatically. The agent knows who it's representing without being told each time.

### 1b. Soul Configuration (`update_soul`)

Defines HOW the agent behaves — response tone, language switching, brand constraints.

```python
# Call once during initial setup
update_soul(
    content="""
    Response behaviour:
    - Auto-draft customer replies must be warm, empathetic, and professional
    - Never promise refunds or compensation without explicit merchant approval
    - Always suggest an alternative before apologising
    - Switch to Mandarin when responding to Mandarin-language reviews/posts
    - Keep student coordinator messages concise and action-oriented
    - When aggregating trends, present data in bullet-point format with percentages
    """
)
```

---

## Phase 2: Scheduled Monitoring Tasks

### 2a. Daily Review & Mention Monitor

Uses `schedule_manager.create` with `cron` schedule type to run every weekday morning.

```json
{
  "action": "create",
  "params": {
    "name": "Daily Customer Sentiment Digest",
    "description": "Monitors reviews, social mentions, and community posts daily at 07:00 SGT",
    "schedule_type": "cron",
    "cron_expr": "0 7 * * 1-5",
    "timezone": "Asia/Singapore",
    "display_schedule": "Weekdays 07:00",
    "prompt": "Gather overnight customer reviews and social media mentions for 'Kopi & Rempah' in Singapore. Use web_search to find reviews from Google, food platforms, and local community groups. For any image-based reviews, use visual_recognition to analyse them. Compile a structured summary with: (1) sentiment breakdown by source, (2) top 3 positive mentions with quotes, (3) top 3 concerns/negative reviews with quotes, (4) trending dishes or topics mentioned. Flag any stock-out complaints for inventory follow-up. Produce output in English unless a review is in another language — then include the original text. Do not ask follow-up questions.",
    "agent_type": "research",
    "timeout_seconds": 600,
    "notify_config": {
      "channels": ["push", "webhook"],
      "webhook_url": "https://your-server.example.com/agnes/review-digest"
    }
  }
}
```

**Cited Reference — Scheduler Skill Cron Syntax:**
Standard 5-field cron expression: `minute hour day-of-month month day-of-week`. Set timezone to IANA zone `Asia/Singapore`. See scheduler skill documentation for full cron pattern reference. [[Source: scheduler skill]]

### 2b. Footfall Pattern Aggregation

Runs weekly, delegates to SheetAgent for structured analysis.

```json
{
  "action": "create",
  "params": {
    "name": "Weekly Footfall Trend Report",
    "description": "Aggregates footfall patterns and sales trends every Monday",
    "schedule_type": "cron",
    "cron_expr": "0 10 * * 1",
    "timezone": "Asia/Singapore",
    "display_schedule": "Mondays 10:00",
    "prompt": "Analyse uploaded POS data for footfall patterns over the past week. Look for peak hours, busiest days, average transaction values, and compare against the previous week. Identify any notable deviations (>10% change). Output findings as a structured report with percentage changes highlighted.",
    "agent_type": "super",
    "timeout_seconds": 300,
    "allowed_tools": [],
    "notify_config": {
      "channels": ["push"]
    }
  }
}
```

**Note:** The actual POS data ingestion happens via your existing workflow (CSV upload → SheetAgent processing). This scheduled task assumes the cleaned dataset is already available.

### 2c. Inventory Signal Detector

Monitors demand signals from community posts and adjusts suggestions.

```json
{
  "action": "create",
    "params": {
    "name": "Inventory Demand Signal Monitor",
    "description": "Scans community discussions for product demand spikes",
    "schedule_type": "interval",
    "interval_seconds": 28800,
    "timezone": "Asia/Singapore",
    "display_schedule": "Every 8 hours",
    "prompt": "Search recent community forum posts and social media mentions in Singapore for discussions about 'Kopi & Rempah' menu items. Track frequency of specific dish mentions compared to baseline. If any single item appears >50% more than its 7-day average mention count, flag it as a potential demand spike. Cross-reference against known inventory levels if available. Recommend whether to increase, maintain, or reduce orders for flagged items. Present findings in a prioritised list.",
    "agent_type": "search",
    "timeout_seconds": 240,
    "notify_config": {
      "channels": ["push", "webhook"],
      "webhook_url": "https://your-server.example.com/agnes/inventory-alerts"
    }
  }
}
```

---

## Phase 3: Automated Response Drafting Pipeline

This runs as a triggered workflow — either via webhook from Phase 2's digest, or as a manual trigger.

```python
def draft_customer_response(review_text, sentiment, channel):
    """
    Generates a brand-aligned response draft for a customer review.
    
    Args:
        review_text: Original review text
        sentiment: Positive/Negative/Neutral classification
        channel: Source platform ('google', 'facebook', 'instagram')
    
    Returns:
        Drafted response string ready for merchant approval
    """
    
    # This logic lives inside the agent's prompt, not external code
    # The agent uses update_soul-configured tone rules autonomously
    
    return agent.generate(
        prompt=f"""
        You are drafting a customer response for Kopi & Rempah, a modern 
        Southeast Asian cafe in Kampong Glam, Singapore.
        
        ORIGINAL REVIEW ({sentiment}):
        "{review_text}"
        
        CHANNEL: {channel}
        
        Guidelines:
        - For positive reviews: thank sincerely, reference a specific dish/point
        - For negative reviews: acknowledge concern, apologise briefly, suggest 
          a solution or alternative visit opportunity
        - NEVER promise refunds or free items
        - Keep responses under 80 words
        - Tone: warm, professional, genuine
        
        Output ONLY the drafted response text. No preamble, no explanation.
        """,
        temperature=0.7
    )
```

**Example outputs generated by the agent:**

*Negative review:*
> "Hi there — we're truly sorry to hear your garlic pork ribs weren't up to our usual standard. We've escalated this to our kitchen team immediately. Please give us another chance next visit; we'd love to make it right. Thank you for the feedback."

*Positive review:*
> "Thank you so much! Our Ethiopian single-origin pour-over is indeed one of our favourites too — glad you noticed the floral notes. Hope to see you again soon!"

---

## Phase 4: Telegram/WhatsApp Integration

### 4a. Telegram Bot Setup

**Documentation References:**
- Telegram Bot API: https://core.telegram.org/bots/api
- BotFather (bot creation): https://core.telegram.org/bots#botfather
- setWebhook method: https://core.telegram.org/bots/api#setwebhook

**Step 1: Create the bot via BotFather**
```
@BotFather → /newbot
→ Name: Kopi & Rempah Assistant
→ Username: kopiremash_assistant_bot
→ Receives API_TOKEN from BotFather
```

**Step 2: Deploy the webhook server**

```python
# webhook_server.py — Minimal Flask/FastAPI webhook handler
import os
import hashlib
import hmac
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

APP_ID = os.environ["TELEGRAM_APP_ID"]       # From BotFather
API_TOKEN = os.environ["TELEGRAM_API_TOKEN"]  # From BotFather
SECRET_TOKEN = os.environ["TELEGRAM_SECRET"]  # Your own secret for verification
AGNES_WEBHOOK_URL = os.environ["AGNES_WEBHOOK"]  # e.g., https://your-server.example.com/agnes/inbound

app = ApplicationBuilder().token(API_TOKEN).build()

async def handle_message(update: Update, context):
    """Route incoming Telegram messages to AgnesClaw."""
    user_msg = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Forward to Agnes orchestrator
    agnes_response = await call_agnes_orchestrator(
        source="telegram",
        chat_id=chat_id,
        user_id=user_id,
        message=user_msg
    )
    
    await update.message.reply_text(agnes_response)

async def call_agnes_orchestrator(source, chat_id, user_id, message):
    """
    Send message to AgnesClaw backend for autonomous processing.
    The orchestrator applies memory, generates response/action.
    """
    # Implementation depends on your backend architecture
    # Options: REST API call, message queue, gRPC
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            AGNES_WEBHOOK_URL,
            json={
                "source": source,
                "chat_id": str(chat_id),
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            },
            headers={"X-Agnes-Secret": SECRET_TOKEN}
        )
    return resp.json()["response"]

# Register handlers
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Hi! How can I help?")))
app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text(
    "/shift — View shifts\n/report — Request daily digest\n/menu — View menu\n/status — Check order status"
)))

if __name__ == "__main__":
    app.run_polling()
```

**Step 3: Register the webhook**

```bash
curl -F "url=https://your-domain.example.com/webhook/telegram" \
     -F "secret_token=$TELEGRAM_SECRET" \
     "https://api.telegram.org/bot$API_TOKEN/setWebhook"
```

**Cited Reference — Telegram Webhook Verification:**
Telegram requires HTTPS endpoints. Use the `secret_token` parameter in `setWebhook` and verify the `X-Telegram-Bot-Api-Secret-Token` header on inbound requests to prevent spoofing. [[Source: Telegram Bot API docs]]

### 4b. WhatsApp Cloud API Setup

**Documentation References:**
- WhatsApp Business Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
- Webhook setup: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-endpoint
- Phone Number ID & Access Token management: Meta Business Settings

**Step 1: Configure Facebook Developer App**

```python
# whatsapp_webhook.py — FB Graph API webhook receiver
import os
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException

WHATSAPP_VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]

app = FastAPI()

@app.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    """FB sends GET request with hub.challenge to verify endpoint."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return {"hub.challenge": challenge}
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook/whatsapp")
async def receive_whatsapp_message(request: Request):
    """Process inbound WhatsApp messages."""
    body = await request.json()
    
    # Validate signature (production requirement)
    # See: https://developers.facebook.com/docs/whatsapp/cloud-api/security-guides
    
    entries = body.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])
            
            for msg in messages:
                wa_id = msg["from"]
                text = msg["text"]["body"]
                
                # Route to Agnes orchestrator
                response = await call_agnes_orchestrator(
                    source="whatsapp",
                    chat_id=str(wa_id),
                    user_id=str(wa_id),
                    message=text
                )
                
                # Send reply via WhatsApp API
                await send_whatsapp_reply(wa_id, response)
    
    return {"status": "success"}

async def send_whatsapp_reply(to_wa_id: str, text: str):
    """Send outbound message via WhatsApp Cloud API."""
    import httpx
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text}
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=headers)
```

**Step 2: Register webhook endpoint in Meta Business Suite**

Via Facebook Developer Console → WhatsApp → Configuration → Add Callback URL:
```
https://your-domain.example.com/webhook/whatsapp
Verify Token: <your-chosen-token>
Fields: messages, messaging_profile_purchases, messaging_optins
```

**Cited Reference — WhatsApp Webhook Security:**
Meta requires a public HTTPS endpoint. In production, validate incoming signatures and use the `hub.verify_token` for initial subscription verification. Template messages are required for initiating conversations outside the 24-hour window. [[Source: Meta WhatsApp Cloud API docs]]

---

## Phase 5: Volunter Coordination Module

Telegram commands for volunteer management:

```python
# Volunteer command handlers
COMMAND_HANDLERS = {
    "shift": {
        "description": "View upcoming shifts",
        "handler": show_upcoming_shifts
    },
    "sign-up": {
        "description": "Sign up for open shifts",
        "handler": signup_for_shift
    },
    "swap": {
        "description": "Request shift swap with another volunteer",
        "handler": process_swap_request
    },
    "report": {
        "description": "Submit incident/customer feedback report",
        "handler": submit_feedback_report
    }
}
```

**Automated shift notification (scheduled task):**

```json
{
  "action": "create",
  "params": {
    "name": "Shift Reminder Broadcast",
    "description": "Reminds volunteers of their shifts 2 hours before start time",
    "schedule_type": "cron",
    "cron_expr": "0 */2 * * *",
    "timezone": "Asia/Singapore",
    "display_schedule": "Every 2 hours",
    "prompt": "Check the volunteer shift schedule for today. For each volunteer who has a shift starting within the next 2 hours, prepare a brief reminder message: 'Hi [Name], your shift at Kopi & Rempah starts at [TIME]. See you there!' Send these reminders through the Telegram bot to the respective volunteers.",
    "agent_type": "super",
    "timeout_seconds": 120,
    "notify_config": {
      "channels": ["push"]
    }
  }
}
```

---

## Deployment Checklist

### Infrastructure Requirements

| Component | Specification | Notes |
|---|---|---|
| **Hosting** | VPS or container (Docker) | Minimum: 2 vCPU, 4GB RAM |
| **Runtime** | Python 3.11+, Node.js 20+ | Or whatever your Agnes SDK supports |
| **HTTPS Endpoint** | Valid TLS certificate | Required for both Telegram & WhatsApp webhooks |
| **Database** | PostgreSQL or SQLite | Stores conversation history, task state, volunteer roster |
| **Message Queue** | Redis/RabbitMQ (optional) | For high-volume concurrent message handling |

### Environment Variables

```bash
# Telegram
TELEGRAM_API_TOKEN=abc123:def456...
TELEGRAM_SECRET=my-webhook-secret
TELEGRAM_BOT_USERNAME=kopiremash_assistant_bot

# WhatsApp
WHATSAPP_VERIFY_TOKEN=verify-token-string
WHATSAPP_PHONE_NUMBER_ID=123456789
WHATSAPP_ACCESS_TOKEN=EAA...

# Agnes Backend
AGNES_WEBHOOK=https://agnes-backend.internal/api/v1/tasks
AGNES_AUTH_TOKEN=agency-auth-key

# Database
DATABASE_URL=postgresql://user:pass@localhost/agnes_claw
```

### Quick Start Commands

```bash
# 1. Clone and install dependencies
git clone https://github.com/your-org/agnes-claw-commerce.git
cd app
pip install -r requirements.txt

# 2. Set environment variables
cp .env.template .env
# Edit .env with your credentials

# 3. Initialise persistent memory
python cli.py init-memory --merchant "Kopi & Rempah" --location "Singapore"

# 4. Register all scheduled tasks
python cli.py register-tasks --config config/scheduled_tasks.yaml

# 5. Start webhook servers
docker-compose up -d

# 6. Verify connections
python cli.py health-check
```

---

## Error Handling & Fallback Strategies

```python
class AgnesIntegrationError(Exception):
    """Base exception for AgnesClaw integration failures."""
    pass

class WebhookTimeout(AgnesIntegrationError):
    """Agnes backend did not respond within timeout window."""
    pass

class MemoryCorruption(AgnesIntegrationError):
    """Identity or Soul data inconsistent or missing."""
    pass

def robust_call_agnes(message_data: dict, max_retries: int = 2) -> str:
    """Call Agnes with retry + fallback logic."""
    for attempt in range(max_retries + 1):
        try:
            response = http_client.post(
                AGNES_WEBHOOK_URL,
                json=message_data,
                timeout=30.0  # Seconds
            )
            response.raise_for_status()
            return response.json()["response"]
        except Timeout:
            if attempt < max_retries:
                continue
            return "⚠️ System busy — please try again in a moment."
        except ConnectionError:
            log_error(f"Connection refused: {traceback.format_exc()}")
            return "⚠️ Service temporarily unavailable."
    
    raise AgnesIntegrationError("Max retries exceeded")
```

---

## Scaling Considerations

1. **Message volume:** At scale (>1000 msgs/day), replace direct HTTP calls with a message queue (Redis Streams, Kafka) between webhook receivers and the Agnes processor.

2. **Multi-tenant support:** Namespace identity/soul data by `merchant_id`. Each merchant gets isolated memory stores.

3. **Rate limiting:** Telegram allows ~30 messages/sec per bot. WhatsApp Cloud API allows ~80 concurrent sessions per number. Implement circuit breakers.

4. **Data retention:** Archive conversation logs quarterly. Compress old records. Retain only aggregated trend data for ML-driven forecasting.

---

## Cited Documentation Sources

1. **Scheduler Skill Documentation** — Task configuration schema, cron syntax, agent types, notification channels. [Loaded internally]

2. **Telegram Bot API** — Official reference for bot methods, webhook registration, and update objects.  
   https://core.telegram.org/bots/api

3. **Telegram BotFather** — Instructions for creating and managing bots.  
   https://core.telegram.org/bots#botfather

4. **WhatsApp Business Cloud API** — Meta's official documentation for Cloud API, webhook setup, and messaging.  
   https://developers.facebook.com/docs/whatsapp/cloud-api

5. **WhatsApp Webhook Security** — Signature validation and callback configuration.  
   https://developers.facebook.com/d
