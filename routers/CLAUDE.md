# Routers — CLAUDE.md

These FastAPI routers are all included in `main.py` via `app.include_router(...)`.

---

## signup.py — `/auth` prefix
User registration, email verification, password reset, and token lifecycle.

| Method | Path | What it does |
|--------|------|-------------|
| POST | `/auth/signup` | Validates password policy, bcrypt hashes, creates User, sends SendGrid verification email |
| GET | `/auth/verify-email?token=…` | Decodes JWT verification token, sets `email_verified=True` |
| POST | `/auth/password-reset-request` | Sends a signed 1-hour reset link via SendGrid |
| POST | `/auth/password-reset-confirm` | Validates token (single-use), updates password hash |
| POST | `/auth/refresh` | Issues a new 15-min access token from the httpOnly refresh cookie |
| POST | `/auth/logout` | Revokes the refresh token, deletes the cookie |

**Password policy:** ≥8 chars, at least one uppercase, lowercase, digit, and special character.

---

## users.py — `/users` prefix
Authenticated user profile and account management.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/users/me` | Return decrypted profile (username, email, base_currency) |
| PUT | `/users/me` | Update username or base_currency |
| PUT | `/users/me/password` | Change password (requires correct current password) |
| DELETE | `/users/me` | Soft-delete account (`deleted_at` set); sends confirmation email; 30-day grace period |

---

## overview.py — `/overview` prefix
Annual aggregation.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/overview/annual?year=YYYY` | Fetch all MonthlyData for the user in a given year; aggregate per-month + year totals |

Month filtering decrypts every row in Python (Fernet non-deterministic). Missing months are returned as zero-value placeholders so the frontend always receives all 12 months.

---

## recurring.py — `/recurring-expenses` prefix
Recurring expense templates. APScheduler runs `generate_all_recurring` daily at 00:05 UTC to create planned `MonthlyExpense` rows from active templates.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/recurring-expenses` | List user's active recurring expenses |
| POST | `/recurring-expenses` | Create a template (name, category, amount, frequency, start/end dates) |
| PUT | `/recurring-expenses/{id}` | Update; ownership enforced |
| DELETE | `/recurring-expenses/{id}` | Soft-delete |
| POST | `/recurring-expenses/generate` | Manual trigger — runs generation immediately for the current user |

**Amount scaling:** daily × days-in-month, weekly × 4, monthly × 1, yearly ÷ 12.

---

## savings.py — `/savings-goals` prefix
Savings goal CRUD and contribution tracking.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/savings-goals` | List user's goals with on-track/behind/ahead status |
| POST | `/savings-goals` | Create a goal (name, target_amount, target_date) |
| PUT | `/savings-goals/{id}` | Update |
| DELETE | `/savings-goals/{id}` | Soft-delete |
| POST | `/savings-goals/{id}/contributions` | Log a contribution (updates `current_amount`) |

---

## alerts.py — `/budget-alerts` and `/notifications` prefix
Budget threshold alerts and in-app notification management. `check_budget_alerts` runs daily at 00:10 UTC.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/budget-alerts` | List active alerts |
| POST | `/budget-alerts` | Create alert (category, threshold_pct 1–100) |
| PUT | `/budget-alerts/{id}` | Update threshold or active flag |
| DELETE | `/budget-alerts/{id}` | Soft-delete |
| GET | `/notifications` | List newest 50 + `unread_count` |
| PATCH | `/notifications/{id}/read` | Mark single notification read |
| PATCH | `/notifications/read-all` | Mark all unread as read |
| DELETE | `/notifications/{id}` | Hard-delete |

Alert deduplication uses `dedup_key = "ba:{alert_id}:{YYYY-MM}"` so a breach fires at most one notification per alert per month.

---

## insights.py — `/insights` prefix
Spending analysis endpoints. All decryption happens in Python; no encrypted SQL filtering.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/insights/monthly-summary?month=YYYY-MM` | MoM % change per category, biggest overspend, net income, ranked insight cards (max 5) |
| GET | `/insights/trends?months=6` | Per-category actual spend per month + 3-month rolling averages + overall income/spending trend |
| GET | `/insights/heatmap?year=YYYY` | Monthly spending totals with quartile-based intensity levels 0–4 |

---

## export.py — `/export` prefix
Rate-limited to 1 request/minute per IP (slowapi).

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/export/csv?from=YYYY-MM&to=YYYY-MM` | Streams all non-deleted expenses in range as CSV |
| GET | `/export/pdf?month=YYYY-MM` | Generates monthly budget report PDF (fpdf2); overspend rows highlighted red |

---

## audit.py — `/audit` prefix
Expense change history.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/audit/expenses/{id}` | Return AuditLog entries for an expense, newest first; ownership enforced |

AuditLog rows are plaintext (no Fernet) so history survives encryption-key rotation. `expense_id` is not a foreign key so audit rows persist after soft-delete.

---

## currency.py — `/currency` prefix
Currency list and exchange rates. APScheduler syncs rates daily at 00:15 UTC from Frankfurter API (open.er-api.com as fallback).

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/currency/list` | Returns supported ISO 4217 currency codes |
| GET | `/currency/rates` | Returns latest stored ExchangeRate rows |

---

## tracker.py — `/tracker` prefix (legacy)
Legacy routes that overlap with the `/monthly-tracker/{month}` endpoints in `main.py`.

| Method | Path | What it does |
|--------|------|-------------|
| POST | `/tracker/` | Save monthly tracking data |
| GET | `/tracker/{month}` | Retrieve tracking data for a month |

**Status:** The frontend calls the `main.py` endpoints, not these. Candidate for removal.
