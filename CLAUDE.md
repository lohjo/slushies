# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Dev server
flask run

# Run all tests
pytest tests/ -v --tb=short --strict-markers

# Run a single test file
pytest tests/test_score_service.py -v

# Run a single test
pytest tests/test_score_service.py::test_act_totals -v

# DB migrations
flask db upgrade
flask db migrate -m "description"

# CLI commands
flask init-db          # dev only — blocked in production
flask create-admin     # interactive prompt for first admin user
flask sync             # pull all rows from Google Sheets manually
```

## Architecture

**Entry point:** `run.py` — creates the Flask app via `create_app(FLASK_ENV)` and registers CLI commands.

**App factory:** `app/__init__.py` — initialises SQLAlchemy, Flask-Login, Flask-Bcrypt, Flask-Migrate, Flask-Limiter, and registers four blueprints: `auth`, `dashboard`, `api` (`/api`), `webhook` (`/webhook`).

**Data pipeline** (all survey processing flows through this):
```
Google Sheets row
  → sheets_service.parse_row()        # flat list → typed dict, safe_float() on numerics
  → score_service.compute_all_totals() # pure Python, no Flask/DB deps
  → sync_service.process_row()        # upsert Participant, dedup via sheet_row_index,
                                      #   write SurveyResponse, trigger card generation
  → card_service.generate_card()      # HTML→PDF via WeasyPrint (post+pre both present)
```

Two entry points call the same pipeline: `POST /webhook/form-submit` (Apps Script real-time) and `POST /api/sync` (manual full-sheet pull). Both are idempotent — `sheet_row_index` is the deduplication key.

**Webhook auth:** `/webhook/form-submit` is NOT protected by Flask-Login. It uses `hmac.compare_digest()` against `X-Webhook-Secret` header. All `/api/*` and `/dashboard` routes require Flask-Login session.

**Score service** (`app/services/score_service.py`) is framework-free — tests run without app context or fixtures. Rosenberg has 5 reverse-scored items (C2, C5, C6, C8, C9); the others are straight sums.

**Database:** SQLite in dev (`instance/platform_dev.db`), PostgreSQL in prod. Schema managed via Alembic. `DATABASE_URL` is required in production — the app refuses to start without it.

**PDF output:** `instance/cards/growth_card_{code}_{date}.pdf` — git-ignored. Generated only when both pre and post responses exist for a participant.

## Key constraints

- `COL_MAP` in `sheets_service.py` must stay aligned with Google Sheet column order. If form questions reorder, update only `COL_MAP` — nothing else changes.
- `flask init-db` is blocked in production. Use `flask db upgrade` for all schema changes in non-dev environments.
- `WEBHOOK_SECRET` must never be empty in production — the endpoint is fail-closed.
- `GrowthCard` records are append-only — regenerating a card creates a new record, never overwrites.
- Adding a new psychometric scale requires: new columns in `models.py` + migration, new `COL_MAP` entry, new `compute_*` function in `score_service.py`, call it in `compute_all_totals()`, update the card template, add tests.

## Environment variables

Minimum to run locally: `FLASK_ENV`, `SECRET_KEY`, `GOOGLE_SHEET_ID`, `WEBHOOK_SECRET`.
Production additionally requires: `DATABASE_URL` (PostgreSQL), `GOOGLE_SERVICE_ACCOUNT_JSON` (preferred over file path).
