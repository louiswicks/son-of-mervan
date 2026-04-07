# Son of Mervan — CLAUDE.md

## What this project is
Personal budget planning and expense tracking app ("SYITB — Start Your Income Tracking Budget").
Users plan monthly budgets (salary + expense line items), track actual spending against the plan, manage savings goals, set budget alerts, and review annual overviews.

## Tech stack
- **Backend:** Python 3, FastAPI, SQLAlchemy ORM, PostgreSQL (SQLite fallback for dev)
- **Frontend:** React 19, React Router v6, Tailwind CSS, Recharts, React Query, Zustand — lives in `web/`
- **Auth:** JWT — 15-min access tokens (in-memory) + 30-day refresh tokens (httpOnly cookie) + bcrypt + email verification via SendGrid
- **Encryption:** Fernet (symmetric) — all financial data encrypted at rest
- **Config:** `core/config.py` — Pydantic `BaseSettings`; `JWT_SECRET` is required with no default (app crashes loudly at startup if missing)

## Project layout
```
son-of-louman/
├── main.py                  # Core FastAPI app — login, calculate-budget, monthly-tracker, audit helpers
├── database.py              # All ORM models + Fernet encrypt/decrypt hybrid properties
├── security.py              # JWT creation/verification, bcrypt, Bearer dependency
├── models.py                # Pydantic request/response schemas
├── crud.py                  # Legacy CRUD helpers (partially unused; main.py handles most logic inline)
├── email_utils.py           # SendGrid integration (console fallback in dev)
├── requirements.txt
├── pytest.ini
├── ruff.toml
├── core/
│   ├── config.py            # Pydantic BaseSettings — all env vars, fails fast if required vars absent
│   ├── limiter.py           # slowapi rate limiter instance (in-memory)
│   ├── logging_config.py    # structlog JSON logging setup
│   └── cache.py             # Redis cache helpers (annual overview TTL)
├── routers/                 # See routers/CLAUDE.md
│   ├── signup.py            # /auth/* — signup, verify-email, password-reset, refresh, logout
│   ├── users.py             # /users/me — profile, password change, account delete
│   ├── tracker.py           # Legacy /tracker/* (partially unused; frontend uses main.py endpoints)
│   ├── overview.py          # /overview/annual
│   ├── recurring.py         # /recurring-expenses
│   ├── savings.py           # /savings-goals + /savings-goals/{id}/contributions
│   ├── alerts.py            # /budget-alerts + /notifications + check_budget_alerts scheduler job
│   ├── insights.py          # /insights/monthly-summary, /insights/trends, /insights/heatmap
│   ├── export.py            # /export/csv, /export/pdf
│   ├── audit.py             # /audit/expenses/{id}
│   └── currency.py          # /currency/list, /currency/rates + sync_exchange_rates scheduler job
├── alembic/                 # Database migration history
│   └── versions/
├── scripts/
│   ├── backup.py            # pg_dump → gzip → Cloudflare R2
│   ├── restore.py           # Restore from R2 backup (--dry-run flag)
│   └── migrate.py           # CLI migration helper (replaces the removed HTTP migration routes)
└── web/                     # See web/CLAUDE.md
    └── src/
        ├── App.jsx
        ├── router.jsx
        ├── api/             # Axios wrappers per feature module
        ├── hooks/           # React Query hooks per feature
        ├── store/           # Zustand stores (authStore, uiStore)
        ├── context/         # AuthContext.jsx (thin session-restore wrapper)
        ├── components/      # All page and UI components
        └── styles/          # CSS custom properties and breakpoints
```

## Key API endpoints
All in `main.py` unless noted.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/signup` | Register user — router: signup.py |
| GET | `/auth/verify-email?token=…` | Email verification — router: signup.py |
| POST | `/auth/password-reset-request` | Sends reset email — router: signup.py |
| POST | `/auth/password-reset-confirm` | Validates token, updates password — router: signup.py |
| POST | `/auth/refresh` | Issues new 15-min access token from httpOnly refresh cookie — router: signup.py |
| POST | `/auth/logout` | Revokes refresh token — router: signup.py |
| POST | `/login` | Returns access token + sets refresh cookie; accepts email or username |
| GET | `/verify-token` | Validate existing access token |
| GET | `/health` | `{ status, db, version }` — Railway health checks |
| POST | `/calculate-budget` | Salary + expenses → totals/percentages. `commit=true` saves to DB |
| POST | `/monthly-tracker/{month}` | Upsert actual expenses for a month (YYYY-MM) |
| GET | `/monthly-tracker/{month}` | Fetch grouped actuals for a month |
| PUT | `/expenses/{id}` | Edit an expense — ownership enforced |
| DELETE | `/expenses/{id}` | Soft-delete an expense — ownership enforced |
| GET | `/overview/annual?year=YYYY` | Aggregate all months in a year — router: overview.py |
| GET/PUT | `/users/me` | Profile — router: users.py |
| PUT | `/users/me/password` | Change password — router: users.py |
| DELETE | `/users/me` | Soft-delete account (30-day grace) — router: users.py |
| GET/POST/PUT/DELETE | `/recurring-expenses` | Manage recurring expense templates — router: recurring.py |
| POST | `/recurring-expenses/generate` | Manual trigger for recurring generation — router: recurring.py |
| GET/POST/PUT/DELETE | `/savings-goals` | Savings goal CRUD — router: savings.py |
| POST | `/savings-goals/{id}/contributions` | Log a contribution — router: savings.py |
| GET/POST/PUT/DELETE | `/budget-alerts` | Alert threshold CRUD — router: alerts.py |
| GET/PATCH/DELETE | `/notifications` | In-app notification management — router: alerts.py |
| GET | `/insights/monthly-summary?month=YYYY-MM` | Month-over-month insights — router: insights.py |
| GET | `/insights/trends?months=6` | Per-category rolling averages — router: insights.py |
| GET | `/insights/heatmap?year=YYYY` | Annual spending heatmap — router: insights.py |
| GET | `/export/csv?from=YYYY-MM&to=YYYY-MM` | CSV expense download — router: export.py |
| GET | `/export/pdf?month=YYYY-MM` | Monthly budget PDF — router: export.py |
| GET | `/audit/expenses/{id}` | Expense change history — router: audit.py |
| GET | `/currency/list` | Supported currencies — router: currency.py |
| GET | `/currency/rates` | Latest exchange rates — router: currency.py |

## Database models (database.py)
All financial fields use SQLAlchemy **hybrid properties** for transparent Fernet encrypt/decrypt.

- **User** — `id`, `email` (unencrypted), `email_verified`, `_username_encrypted`, `password_hash`, `base_currency` (ISO 4217, default "GBP"), `deleted_at`
- **MonthlyData** — per-user per-month record; encrypted: `_month_encrypted`, `_salary_planned/actual_encrypted`, `_total_planned/actual_encrypted`, `_remaining_planned/actual_encrypted`
- **MonthlyExpense** — line items linked to MonthlyData; encrypted: `_name_encrypted`, `_category_encrypted`, `_planned_amount_encrypted`, `_actual_amount_encrypted`; plaintext: `currency` (ISO 4217), `deleted_at`
- **PasswordResetToken** — `token_hash` (SHA-256), `user_id`, `expires_at`, `used_at`
- **RefreshToken** — `token_hash`, `user_id`, `expires_at`, `revoked_at`
- **RecurringExpense** — `frequency` (daily/weekly/monthly/yearly), `start_date`, `end_date`, `last_generated_at`; encrypted: name, category, planned_amount
- **SavingsGoal** — `target_amount`, `current_amount`, `target_date`; encrypted: name, description; has `contributions` relationship
- **SavingsContribution** — `amount`, `contributed_at`; linked to SavingsGoal
- **BudgetAlert** — `threshold_pct`, `active`, `deleted_at`; encrypted: `category`
- **Notification** — `type`, `dedup_key`, `read_at`; encrypted: `title`, `message`
- **AuditLog** — plaintext only (survives encryption-key rotation): `expense_id` (not FK), `action`, `before_json`, `after_json`
- **ExchangeRate** — `base`, `target`, `rate`, `fetched_at`

## Encryption gotcha (important)
Fernet is **non-deterministic** — the same plaintext produces different ciphertext each time.
This means **you cannot filter encrypted columns in SQL**. All lookups involving encrypted fields must fetch all records and decrypt in Python.
Example: month lookups in `main.py` decrypt every row to find the right one — O(n) by design.

## Auth flow
1. `POST /auth/signup` → bcrypt hash, send SendGrid verification email (JWT 60-min token)
2. `GET /auth/verify-email` → sets `email_verified=True`
3. `POST /login` → returns 15-min access token (JSON body) + sets 30-day refresh token (httpOnly cookie)
4. Axios interceptor in `web/src/api/client.js` catches 401, calls `POST /auth/refresh`, retries
5. `POST /auth/logout` → revokes refresh token, deletes cookie
6. Protected routes use `Depends(verify_token)` from `security.py`
7. Access token is stored in-memory only (Zustand `authStore`) — never in localStorage

## Background jobs (APScheduler, started in main.py `@app.on_event("startup")`)
| Time (UTC) | Job |
|---|---|
| 00:05 | `generate_all_recurring` — generate planned expenses from recurring templates |
| 00:10 | `check_budget_alerts` — evaluate spending vs thresholds, fire notifications + emails |
| 00:15 | `sync_exchange_rates` — fetch latest rates from Frankfurter API |

## Environment variables required
See `.env.example` for a complete template.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL URL (falls back to SQLite if unset) |
| `ENCRYPTION_KEY` | 32-byte base64 Fernet key — CRITICAL, must be stable |
| `JWT_SECRET` | JWT signing secret — **required**; app refuses to start without it |
| `SENDGRID_API_KEY` | Email delivery (prints link to console if unset — fine for dev) |
| `EMAIL_FROM` | Sender address for verification/alert emails |
| `FRONTEND_BASE_URL` | Used in email links |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `REDIS_URL` | Redis for annual overview cache (optional; skips caching if unset) |
| `SENTRY_DSN` | Backend error tracking (optional) |
| `R2_BUCKET` / `R2_ACCESS_KEY` / `R2_SECRET_KEY` / `R2_ENDPOINT` | Cloudflare R2 for backups |

## Running locally
```bash
# Backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd web && npm install && npm start
```

Or use Docker:
```bash
docker compose up   # starts db + redis + backend + frontend
```

## Testing
```bash
# Backend (target: ≥80% coverage)
pytest --cov=. --cov-fail-under=80

# Frontend (target: ≥70% coverage)
cd web && npm test
```

## Deployment
- **Backend:** Railway.app — `https://son-of-mervan-production.up.railway.app`
- **Frontend:** GitHub Pages — `https://louiswicks.github.io/son-of-mervan`
- Frontend uses React Router v6 `createHashRouter` for GitHub Pages compatibility

## CI/CD (GitHub Actions)
- `ci.yml` — runs on every PR and push to main: backend tests (≥80% coverage), frontend tests, ruff lint, bandit security scan, eslint
- `deploy.yml` — triggered by successful CI on main: Railway CLI deploy → smoke test `GET /health`

## Known issues / tech debt
- `crud.py` is partially unused — `main.py` duplicates some logic inline
- `web/src/App.js` (original CRA entry) still exists alongside `App.jsx` — `App.js` is a thin re-export and can be removed once CRA build config is updated

## Expense upsert pattern
When saving actual expenses, the app matches by **decrypted name + category**. If found → update `actual_amount`. If not → insert new record. Planned amounts are preserved when updating actuals.
