# MailPulse

**企业邮件智能中枢** — AI-Powered Email Intelligence for Multi-Company Operations

Turn scattered Gmail emails into structured business intelligence, automated reports, and trackable client relationships.

## Features

- 🧠 **AI Analysis** — Claude-powered email scoring, classification, and summarization
- 📊 **Automated Reports** — Scheduled DOCX/PDF reports delivered to Telegram groups and individuals
- 🤖 **Interactive Bot** — Ask questions about your emails in natural language via Telegram
- 👥 **Role-Based Access** — Owner / Manager / Member permissions per company
- 📈 **Client Tracking** — Auto-extracted client profiles with conversation history
- ⚡ **SLA Monitoring** — Response time tracking with auto-escalation
- 🌐 **Admin Dashboard** — Full-featured web interface (Chinese/English)

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   MailPulse                       │
├─────────────┬──────────────┬────────────────────┤
│  Admin Web  │  Telegram Bot │  Digest Engine     │
│  (Next.js)  │  (Python)     │  (Python Cron)     │
├─────────────┴──────────────┴────────────────────┤
│              Supabase (PostgreSQL + Storage)      │
├─────────────────────────────────────────────────┤
│     Gmail API    │   Claude API   │  Telegram API │
└─────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Gmail API credentials ([setup guide](docs/gmail-setup.md))
- Telegram Bot token ([setup guide](docs/telegram-setup.md))
- Supabase project
- Anthropic API key

### 1. Clone & Setup

```bash
git clone https://github.com/your-username/mailpulse.git
cd mailpulse
```

### 2. Database

Create a Supabase project, then run migrations in order:

```bash
# Execute in Supabase SQL Editor
engine/migrations/001_core_schema.sql
engine/migrations/002_events_audit.sql
engine/migrations/003_schedules.sql
```

### 3. Engine (Python Backend)

```bash
cd engine
cp .env.example .env  # Fill in your credentials
pip install -e .
python -m src.entrypoint  # Starts Bot + Scheduler
```

### 4. Admin Panel (Next.js)

```bash
cd admin
cp .env.example .env.local  # Fill in Supabase keys
npm install
npm run dev  # http://localhost:3000
```

### 5. Deploy to Railway

```bash
# Engine
cd engine && railway up

# Admin
cd admin && railway up
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Engine | Python 3.11, Gmail API, Anthropic Claude |
| Admin | Next.js 16, TypeScript, Tailwind CSS |
| Database | Supabase (PostgreSQL) |
| Storage | Supabase Storage |
| Messaging | Telegram Bot API |
| Deployment | Railway |

## License

MIT — see [LICENSE](LICENSE)
