Caveman mode: **full**. Triaging `platform_app`.

---

## 2026-04-15 Incident Addendum (Cloud Run 503 + Apps Script failures)

### Root causes confirmed

1. Apps Script live `WEBHOOK_URL` pointed to wrong region domain (`europe-west1`) while service runs in `asia-southeast1`.
2. Cloud Run runtime missing `DATABASE_URL`/required secrets causes startup `RuntimeError` in production config path.
3. Cloud Build deploy path had no migration execution; `Procfile` release hook not used by Cloud Run.

### Fixes applied

1. Added `migrate` step to root `cloudbuild.yaml` using Cloud Run Job execution before deploy.
2. Deploy step now waits on migration success (`waitFor: ['migrate']`).
3. Architecture doc updated with Cloud Run-specific migration model and checklist including region-accurate Apps Script webhook URL.

### Ops actions still required (outside git)

1. In Cloud Run service vars/secrets, set `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_SHEET_ID`, `WEBHOOK_SECRET`.
2. Ensure Cloud Run Job `slushies-migrate` exists and has same DB/secret wiring as runtime service.
3. In live Apps Script editor, set `WEBHOOK_URL` to:
	`https://slushies-411994757215.asia-southeast1.run.app/webhook/form-submit`
4. Verify `WEBHOOK_SECRET` in Apps Script matches Cloud Run `WEBHOOK_SECRET` exactly.

### Verification commands

```bash
gcloud run services describe slushies --region=asia-southeast1
gcloud run services describe slushies --region=asia-southeast1 --format='value(spec.template.spec.containers[0].env)'
gcloud run jobs execute slushies-migrate --region=asia-southeast1 --wait
gcloud run services logs tail slushies --region=asia-southeast1
```

---

## 🔍 Code Triage — platform_app

### 🔴 CRITICAL

**`dashboard/participant.html` — EMPTY**
File exists, template registered, renders blank page. Participant detail view broken. Write this first.

**`app.py` (root) — DEAD / CONFLICTING SCAFFOLD**
Old standalone Flask file. Own `SQLAlchemy` setup, own `SurveyResponse` model, 3 routes. Sits beside `platform_app/`. Not wired to anything but confusing. Delete or it'll bite someone.

---

### 🟠 HIGH

**`config.py` — `ProductionConfig.SQLALCHEMY_DATABASE_URI` set at class body level**
`os.getenv("DATABASE_URL")` runs at import time. If env not yet loaded, attribute is `None` before `init_app` checks. Mostly fine on Railway (env injected before import) but fragile. Move full URI resolution into `init_app` only.

**`sheets_service.py` — hardcoded sheet tab name**
`"Sheet1!A2:AJ"` in `fetch_all_rows`. Tab rename → silent empty return → zero rows synced, no error raised. Accept tab name as param or raise on empty-with-no-error.

**`register.html` — role field user-controlled**
`<select name="role">` lets admin create another admin. Intentional? If so fine. If not, strip `<option value="admin">` and hardcode `staff` for self-service, admin-only escalation separate.

---

### 🟡 MEDIUM

**`dashboard/index.html` — React loaded from unpkg, no SRI**
```html
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js">
```
No `integrity=` hash. CDN compromise → XSS on dashboard. Add SRI or self-host.

**`api.py /responses GET` — no pagination**
`SurveyResponse.query.all()` returns everything. 500 participants × 2 surveys = 1000 rows fine now, painful later. Add `?limit=&offset=` or paginate.

**`GrowthCard` model — no DB-level uniqueness on `participant_id`**
"One-to-one in practice" but nothing enforces it. Multiple reprocessings append rows. Export uses `max(id)` workaround. Add `unique=True` or switch to upsert pattern.

**`run.py` `init-db` — bypasses Alembic**
`db.create_all()` skips migration history. Running in prod after deploy = schema drift. Guard: check `FLASK_ENV != production` before allowing `init-db`, or remove and rely solely on `flask db upgrade`.

---

### 🟢 LOW / POLISH

**`sync_service.py` — `cohens_d` never populated on `GrowthCard`**
Field exists, always `NULL`. Either compute group-level after all post surveys, or drop column until that pipeline exists. Confusing as-is.

**`webhook.py` — dev mode bypasses secret entirely**
`_verify_secret` returns `True` when `WEBHOOK_SECRET=""`. Fine in dev, but if prod deploy forgets to set var → open webhook. Add explicit `FLASK_ENV` guard or log loud warning.

**`tests/test_pipeline_and_config.py` — mutates class-level config**
`ProductionConfig.SQLALCHEMY_DATABASE_URI = None` in tests. No teardown isolation if tests run in unusual order. Use `monkeypatch` or `unittest.mock.patch` instead.

**`sync_service.py` — `process_row` flush before commit**
`db.session.flush()` to get `participant.id` before `SurveyResponse` write. Exception between flush + commit → participant row in session but response fails. Already handled by `IntegrityError` catch but worth explicit test coverage.

---

### 📋 SUMMARY TABLE

| Severity | File | Issue |
|----------|------|-------|
| 🔴 | `app/templates/dashboard/participant.html` | Empty — page broken |
| 🔴 | `app.py` (root) | Dead conflicting scaffold |
| 🟠 | `config.py` | URI resolved at import time |
| 🟠 | `sheets_service.py` | Hardcoded tab name, silent fail |
| 🟠 | `register.html` | Admin self-escalation via form |
| 🟡 | `dashboard/index.html` | No SRI on React CDN |
| 🟡 | `api.py` | No pagination on `/responses` |
| 🟡 | `GrowthCard` model | No unique constraint on `participant_id` |
| 🟡 | `run.py` | `init-db` bypasses Alembic in prod |
| 🟢 | `GrowthCard` | `cohens_d` always NULL |
| 🟢 | `webhook.py` | Empty secret = open endpoint in prod |
| 🟢 | tests | Class mutation, no monkeypatch |

Fix reds first. Two participant.html blank page will confuse every staff user immediately.