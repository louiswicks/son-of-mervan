# Son of Mervan — CLAUDE.md

## What this project is
Personal budget planning and expense tracking app ("SYITB — Start Your Income Tracking Budget").
Users plan monthly budgets (salary + expense line items), track actual spending against the plan, and review annual overviews.

## Tech stack
- **Backend:** Python 3, FastAPI, SQLAlchemy ORM, PostgreSQL (SQLite fallback for dev)
- **Frontend:** React 19, Tailwind CSS, Recharts — lives in `web/`
- **Auth:** JWT (24h access tokens) + bcrypt + email verification via SendGrid
- **Encryption:** Fernet (symmetric) — all financial data encrypted at rest

## Project layout
```
son-of-louman/
├── main.py                  # Core FastAPI app — most business logic & main endpoints
├── database.py              # ORM models (User, MonthlyData, MonthlyExpense) + Fernet encrypt/decrypt
├── security.py              # JWT creation/verification, bcrypt, Bearer dependency
├── models.py                # Pydantic request/response schemas
├── crud.py                  # Legacy CRUD helpers (partially superseded by inline logic in main.py)
├── email_utils.py           # SendGrid integration (console fallback in dev)
├── migrate_to_encrypted.py  # One-time migration utility (run once, not part of normal flow)
├── requirements.txt
├── routers/                 # See routers/CLAUDE.md
│   ├── signup.py            # POST /auth/signup, GET /auth/verify-email
│   ├── tracker.py           # Legacy tracker routes (partially unused)
│   └── overview.py          # GET /overview/annual?year=YYYY
└── web/                     # See web/CLAUDE.md
    └── src/
        ├── App.js
        └── components/
```

## Key API endpoints (all in main.py unless noted)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/signup` | Register user (router: signup.py) |
| GET | `/auth/verify-email?token=…` | Verify email (router: signup.py) |
| POST | `/login` | Returns JWT; accepts email or username |
| GET | `/verify-token` | Validate existing JWT |
| POST | `/calculate-budget` | Salary + expenses → totals/percentages. `commit=true` saves to DB |
| POST | `/monthly-tracker/{month}` | Upsert actual expenses for a month (YYYY-MM) |
| GET | `/monthly-tracker/{month}` | Fetch grouped actuals for a month |
| GET | `/overview/annual?year=YYYY` | Aggregate all months in a year |

## Database models (database.py)
All financial fields use SQLAlchemy **hybrid properties** for transparent Fernet encrypt/decrypt.

- **User** — `id`, `email` (unencrypted, indexed), `email_verified`, `_username_encrypted`, `password_hash`
- **MonthlyData** — per-user per-month record; encrypted: `_month_encrypted` (YYYY-MM format), `_salary_planned/actual_encrypted`, `_total_planned/actual_encrypted`, `_remaining_planned/actual_encrypted`
- **MonthlyExpense** — line items linked to MonthlyData; encrypted: `_name_encrypted`, `_category_encrypted`, `_planned_amount_encrypted`, `_actual_amount_encrypted`

## Encryption gotcha (important)
Fernet is **non-deterministic** — the same plaintext produces different ciphertext each time.
This means **you cannot filter encrypted columns in SQL**. All lookups that involve encrypted fields (e.g. finding a month by "2025-03") must fetch all records and decrypt in Python.
Example: `find_month_by_value()` in main.py decrypts every row to find the right one — O(n).

## Auth flow
1. `POST /auth/signup` → bcrypt hash password, send SendGrid verification email (JWT 60-min token)
2. User clicks link → `GET /auth/verify-email` → sets `email_verified=True`
3. `POST /login` → checks credentials + `email_verified` → returns 24h JWT
4. Protected routes use `Depends(verify_token)` from security.py

## Environment variables required
| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL URL (falls back to SQLite if unset) |
| `ENCRYPTION_KEY` | 32-byte base64 Fernet key — CRITICAL, must be stable |
| `JWT_SECRET_KEY` | JWT signing secret (auto-generated if unset — should be persistent in prod) |
| `SENDGRID_API_KEY` | Email delivery (prints link to console if unset — fine for dev) |
| `EMAIL_FROM` | Sender address for verification emails |
| `FRONTEND_BASE_URL` | Used in verification email links |
| `CORS_ORIGINS` | Comma-separated allowed origins |

## Running locally
```bash
# Backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd web && npm install && npm start
```

## Deployment
- **Backend:** Railway.app — `https://son-of-mervan-production.up.railway.app`
- **Frontend:** GitHub Pages — `https://louiswicks.github.io/son-of-mervan`
- Frontend uses URL hash routing (`#/route`) for GitHub Pages compatibility

## Known issues / tech debt
- `crud.py` is partially unused — `main.py` duplicates some logic inline
- Migration endpoints `/run-migration` and `/cleanup-old-columns` still live in `main.py` — should be removed after confirming migration is done
- Heavy debug `print()` statements inside `calculate-budget` endpoint — should be cleaned up
- Frontend `API_BASE_URL` is hardcoded to the Railway prod URL in `App.js` — should be an env var
- Expense categories are hardcoded in the frontend: `["Housing","Transportation","Food","Utilities","Insurance","Healthcare","Entertainment","Other"]`

## Expense upsert pattern
When saving actual expenses, the app matches by **decrypted name + category**. If found → update `actual_amount`. If not → insert new record. Planned amounts are preserved when updating actuals.
