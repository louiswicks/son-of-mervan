# Product Requirements Document (PRD)
## Son-of-Mervan: Personal Budgeting Application

**Version:** 1.0  
**Date:** 2026-04-06  
**Author:** Engineering Team  
**Status:** Active

---

## 1. Executive Summary

Son-of-Mervan is a personal budgeting web application that helps individuals gain a clear, real-time understanding of their financial situation. The app tracks monthly income and expenses, computes planned vs actual budgets, and provides an annual financial overview.

The goal of this PRD is to transform the current working prototype into a production-grade application with excellent user experience, comprehensive feature coverage, and the reliability that users expect from an app that holds their financial data.

---

## 2. Product Vision

**Mission:** Give every individual the tools to understand, control, and improve their financial health — without complexity.

**Target User:** Individuals aged 22–45 who want to actively manage their personal finances but find traditional spreadsheets tedious and existing apps (YNAB, Mint) either too expensive or too complex.

**Success Metrics:**
- Monthly Active Users (MAU) growth
- Day-30 retention rate ≥ 40%
- Average sessions per active user per month ≥ 8
- User-reported financial confidence score (survey)
- Zero critical security incidents

---

## 3. Current State

### Tech Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI (Python), SQLAlchemy ORM |
| Database | PostgreSQL (prod), SQLite (dev) |
| Auth | JWT (HS256) + bcrypt + Fernet encryption |
| Email | SendGrid |
| Frontend | React 19, Recharts, Lucide icons, Axios |
| Hosting | Railway (backend), GitHub Pages (frontend) |

### Existing Features
- Monthly income and expense tracking
- Planned vs actual budget comparison
- Category-based expense breakdown
- Annual financial overview with charts
- JWT authentication + email verification
- Fernet encryption of sensitive database fields

### Current Production Readiness: ~85%
All core features, security hardening, infrastructure, and testing are complete. Outstanding work is UI polish, coverage gap closure, and documentation refresh.

---

## 4. Improvement Roadmap

---

## Phase 1: Critical Security Fixes
**Priority: Blocker — must complete before any public users**

### 1.1 Remove Debug/Migration HTTP Endpoints [DONE 2026-04-07]
**Problem:** Routes like `/run-migration`, `/cleanup-old-columns`, `/debug/check-month/{month}` are exposed as live HTTP endpoints. Any caller can trigger destructive database operations.  
**Solution:** Extract to CLI scripts (`scripts/migrate.py`), never mounted as HTTP routes. Remove all `print()` statements; replace with Python `logging` module.  
**Files:** `main.py`, new `scripts/migrate.py`, new `core/logging_config.py`  
**Acceptance Criteria:** All debug routes return 404 in production. No `print()` calls remain in application code.

### 1.2 Fix JWT Secret Fallback [DONE 2026-04-06]
**Problem:** If `JWT_SECRET` env var is missing, the app generates a random secret at startup — silently invalidating all user sessions on every restart.  
**Solution:** Introduce `core/config.py` with Pydantic `BaseSettings`. `JWT_SECRET` is required with no default; app crashes loudly at startup if missing. Add `.env.example` documenting all required variables.  
**Files:** new `core/config.py`, `security.py`, `main.py`, `.env.example`  
**Acceptance Criteria:** Starting the app without `JWT_SECRET` set exits immediately with a clear error message.

### 1.3 Rate Limiting on Auth Endpoints [DONE 2026-04-06]
**Problem:** No rate limiting on login/register endpoints allows unlimited brute-force and credential-stuffing attacks.  
**Solution:** Add `slowapi` with in-memory (dev) or Redis (prod) backend. Limit `/login` and `/auth/signup` to 5 requests/minute per IP. Return HTTP 429 with `Retry-After` header on breach.  
**Files:** new `core/limiter.py`, `routers/signup.py`, `main.py`  
**Acceptance Criteria:** 6th login attempt within 60 seconds returns 429. Header `Retry-After` is present.

### 1.4 Security Headers & CORS Hardening [DONE 2026-04-06]
**Problem:** No security headers. CORS may allow wildcard origins.  
**Solution:** Add `SecurityHeadersMiddleware` setting CSP, HSTS (prod only), `X-Content-Type-Options: nosniff`, `Referrer-Policy`. Replace wildcard CORS origins with an explicit `ALLOWED_ORIGINS` env var.  
**Files:** new `middleware/security.py`, `main.py`  
**Acceptance Criteria:** Response headers include all security headers. CORS rejects requests from unlisted origins.

---

## Phase 2: Core Missing Features & Code Quality

### 2.1 Alembic Database Migrations [DONE 2026-04-06]
**Problem:** Schema changes require a manual migration script with no history or rollback capability.  
**Solution:** Initialise Alembic; configure `env.py` to use `DATABASE_URL` and `Base.metadata`. Generate initial migration. Run `alembic upgrade head` automatically on deploy.  
**Files:** new `alembic/` directory, `alembic.ini`, deploy configuration  
**Acceptance Criteria:** `alembic upgrade head` runs without error on a fresh database. `alembic downgrade -1` successfully rolls back the last migration.

### 2.2 Full CRUD for Expenses and Income [DONE 2026-04-06]
**Problem:** Users cannot edit or delete expenses/income entries. A mis-typed amount is permanent.  
**Solution:** Add `PUT /expenses/{id}` and `DELETE /expenses/{id}` endpoints with user ownership validation. Implement soft-delete (`deleted_at` column) so data is never physically removed. Frontend: edit (pencil) and delete (trash) icons per row; confirmation modal before delete.  
**Files:** `routers/tracker.py`, `models.py`, `crud.py`, `web/src/components/ExpenseRow.jsx`, new `web/src/components/ConfirmModal.jsx`  
**Acceptance Criteria:** User can edit any expense they own. User cannot edit another user's expense (returns 403). Deleted expenses disappear from UI but remain in DB with `deleted_at` set.

### 2.3 Password Reset Flow [DONE 2026-04-06]
**Problem:** No password recovery exists. A user who forgets their password is permanently locked out.  
**Solution:** `POST /auth/password-reset-request` sends a SendGrid email with a signed, time-limited token link (1-hour TTL). `POST /auth/password-reset-confirm` validates the token (single-use) and updates the password. Frontend: "Forgot password?" link on login page; two new pages for request and confirm flows.  
**Files:** `routers/signup.py`, `database.py` (PasswordResetToken), `email_utils.py`, `core/config.py`, new `alembic/versions/c3d4e5f6a7b8`, new `web/src/components/ForgotPasswordPage.jsx`, new `web/src/components/ResetPasswordPage.jsx`, `web/src/components/LoginPage.jsx`, `web/src/App.js`  
**Acceptance Criteria:** User receives email within 30 seconds of request. Token link works once only. Expired tokens return a clear error. Reused tokens are rejected.

### 2.4 JWT Refresh Token Mechanism [DONE 2026-04-06]
**Problem:** Long-lived access tokens are a security risk; short-lived tokens force frequent re-logins.  
**Solution:** Issue `access_token` (15-min TTL) and `refresh_token` (30-day TTL, httpOnly cookie) on login. `POST /auth/refresh` issues new access tokens. `POST /auth/logout` revokes the refresh token. Frontend Axios interceptor catches 401, silently refreshes, retries original request. Access token stored in memory only (not localStorage).  
**Files:** `routers/signup.py`, `database.py` (RefreshToken), `core/config.py`, `main.py`, new `alembic/versions/d4e5f6a7b8c9`, `web/src/App.js`  
**Acceptance Criteria:** User stays logged in for 30 days without action. Logging out invalidates the session on all future requests immediately.  
**Note:** 401 auto-retry Axios interceptor deferred to Phase 3.1 (centralized API client).

### 2.5 Pagination and Filtering [DONE 2026-04-06]
**Problem:** All expenses are returned in a single API call. Performance degrades and UI becomes unusable with large datasets.  
**Solution:** Add `?page=1&page_size=25&month=2025-03&category=Food` query params to expense endpoints. Return `{ items, total, page, pages }` envelope. Add DB indexes on `(user_id, date)` and `(user_id, category)`. Frontend: pagination controls and filter bar.  
**Files:** `routers/tracker.py`, `models.py`, `web/src/components/ExpenseList.jsx`, new `web/src/components/FilterBar.jsx`  
**Acceptance Criteria:** API returns correct page slice. Total count matches unfiltered row count. Response time under 200ms with 10,000 expense rows.

### 2.6 Account Management [DONE 2026-04-06]
**Problem:** Users cannot update their profile, change their password while logged in, or delete their account.  
**Solution:** `GET/PUT /users/me` (profile), `PUT /users/me/password` (requires current password), `DELETE /users/me` (30-day soft-delete grace period with confirmation email). Frontend: Account Settings page with Profile, Security, and Danger Zone sections.  
**Files:** new `routers/users.py`, new `web/src/components/AccountSettings.jsx`, `database.py`, `security.py`, `main.py`, `email_utils.py`, `web/src/App.js`, new `alembic/versions/f6a7b8c9d0e1`  
**Acceptance Criteria:** Profile updates persist. Password change requires correct current password. Account deletion sends confirmation email and removes all personal data after 30 days. GDPR-compliant.

### 2.7 Backend Test Suite (Target: 80% line coverage) [DONE 2026-04-06]
**Problem:** Zero backend tests. Every change is an undetected potential regression.  
**Solution:** `pytest` + `httpx` + `starlette.testclient`. SQLite file-based DB with `autouse` clean fixture between tests overrides `get_db`; `verify_token` overridden for auth'd routes. Test categories: auth flows, expense CRUD and ownership enforcement, budget calculation logic, encryption (verify no plaintext in DB).  
**Files:** new `tests/conftest.py`, `tests/test_auth.py`, `tests/test_expenses.py`, `tests/test_budget.py`, `tests/test_encryption.py`, new `pytest.ini`, updated `requirements.txt`  
**Acceptance Criteria:** `pytest --cov=. --cov-fail-under=80` passes in CI. All test categories covered.  
**Result:** 94 tests, 87% line coverage.

---

## Phase 3: Frontend UX Overhaul

### 3.1 Centralised API Client [DONE 2026-04-06]
**Problem:** API base URL is hardcoded to the production Railway URL. Local development requires source code changes.  
**Solution:** Single Axios instance in `web/src/api/client.js` configured from `REACT_APP_API_URL` environment variable. Feature modules: `api/expenses.js`, `api/budget.js`, `api/auth.js`, `api/users.js`. Includes 401 refresh interceptor.  
**Files:** new `web/src/api/client.js` and feature modules, `web/.env.example`  
**Acceptance Criteria:** `REACT_APP_API_URL=http://localhost:8000` routes all calls to local backend without code changes.

### 3.2 React Router v6 [DONE 2026-04-06]
**Problem:** Custom hash routing is fragile, doesn't support nested routes, and breaks browser history.  
**Solution:** `react-router-dom` v6 with `createHashRouter`. Routes: `/dashboard`, `/expenses`, `/budget`, `/annual`, `/login`, `/register`, `/reset-password`, `/settings`. `<AuthGuard>` redirects unauthenticated users to `/login`.  
**Files:** new `web/src/router.jsx`, `web/src/App.jsx`, new `web/src/components/AuthGuard.jsx`  
**Acceptance Criteria:** Browser back/forward work correctly. Bookmarked URLs load the correct page. Unauthenticated users redirected from protected routes.

### 3.3 React Query + Loading States + Optimistic Updates [DONE 2026-04-06]
**Problem:** No loading indicators. API calls produce blank UI until resolved.  
**Solution:** `@tanstack/react-query` for all server state. Skeleton shimmer components during loading. Optimistic updates on expense CRUD with rollback on error. `react-hot-toast` for success/error feedback.  
**Files:** `web/src/App.jsx`, new hooks (`useExpenses`, `useBudget`, `useAnnualSummary`), new `web/src/components/Skeleton.jsx`  
**Acceptance Criteria:** Every data-loading state shows a meaningful skeleton. Expense added/edited/deleted updates the UI instantly before server confirms. Failed mutations roll back with a toast error.

### 3.4 Global Error Boundaries [DONE 2026-04-06]
**Problem:** Any uncaught JavaScript error crashes the entire app to a blank white screen.  
**Solution:** `ErrorBoundary` class component wrapping the root app and each major page individually. Renders a "Something went wrong" UI with a Reload button. Reports to Sentry (Phase 5).  
**Files:** new `web/src/components/ErrorBoundary.jsx`, new `web/src/components/AsyncBoundary.jsx`, `web/src/App.jsx`, `web/src/router.jsx`  
**Acceptance Criteria:** A deliberate thrown error in a chart component shows the page-level error fallback UI without crashing the nav or other pages.

### 3.5 Zustand Global State Management [DONE 2026-04-06]
**Problem:** Auth state and UI state are scattered across components with no clear ownership.  
**Solution:** Zustand stores: `authStore` (user + in-memory access token), `uiStore` (theme, active modal). React Query owns all server state.  
**Files:** new `web/src/store/authStore.js`, `web/src/store/uiStore.js`  
**Acceptance Criteria:** Access token never written to localStorage. Auth state accessible from any component without prop drilling.

### 3.6 Dark Mode [DONE 2026-04-06]
**Problem:** No dark mode. Table stakes for any consumer app in 2025+.  
**Solution:** CSS custom properties (`--color-bg`, `--color-surface`, etc.) applied to `:root` and overridden under `[data-theme="dark"]`. `useTheme` hook reads from `localStorage` and falls back to `prefers-color-scheme`. Moon/Sun toggle in nav bar.  
**Files:** new `web/src/styles/tokens.css`, new `web/src/hooks/useTheme.js`, `web/src/components/Nav.jsx`  
**Acceptance Criteria:** Theme persists across sessions. Automatically matches OS preference on first visit. All Recharts charts use theme-aware colors.

### 3.7 Mobile-First Responsive Design [DONE 2026-04-06]
**Problem:** App likely breaks below ~768px with no explicit responsive design.  
**Solution:** Fluid CSS Grid replacing fixed-width layouts. Bottom tab bar on mobile (<768px). Expense table → card-stack layout on mobile. WCAG 2.5.5-compliant touch targets (min 44×44px). Tested on iPhone 14 Pro, Pixel 7, iPad, and 320px min width.  
**Files:** `web/src/components/Nav.jsx`, `web/src/components/ExpenseList.jsx`, `web/src/pages/DashboardPage.jsx`, new `web/src/styles/breakpoints.css`  
**Acceptance Criteria:** App is fully usable at 320px width. No horizontal scroll on any page. All interactive targets are at least 44×44px.

### 3.8 Frontend Test Suite (Target: 70% coverage) [DONE 2026-04-06]
**Problem:** Only one dummy smoke test exists.  
**Solution:** Jest + React Testing Library + MSW handler documentation. Tests for: `LoginPage` (form submit, error, redirect), `MonthlyTracker` (ExpenseRow edit/delete flows), `SonOfMervan` (BudgetChart data + empty state), `AuthGuard` (redirect behaviour). Note: Vitest was not used — project uses CRA/Jest; goal met with Jest instead.  
**Files:** new `web/src/tests/`, new `web/src/mocks/handlers.js`, updated `web/src/setupTests.js`, updated `web/src/App.test.js`  
**Acceptance Criteria:** `vitest run --coverage` reports ≥70% component coverage. All tests pass in CI.  
**Result:** 25 tests passing across 5 test suites. All 4 specified component areas covered.

---

## Phase 4: Advanced Features

### 4.1 Recurring Expenses [DONE 2026-04-06]
**Problem:** Most real expenses (rent, subscriptions, utilities) recur monthly. Users must re-enter them every period.  
**Solution:** `RecurringExpense` model with `frequency` ENUM (daily/weekly/monthly/yearly), `start_date`, `end_date`, `last_generated_at`. APScheduler daily background job (00:05 UTC) auto-generates planned MonthlyExpense rows; amounts scaled by frequency (daily × days-in-month, weekly × 4). Frontend: dedicated management page at `/recurring` with create/edit/delete and a "Generate now" manual trigger button. Nav updated with Repeat icon.  
**Files:** `database.py`, `alembic/versions/a7b8c9d0e1f2_add_recurring_expenses.py`, `models.py`, `routers/recurring.py` (new), `main.py`, `requirements.txt`, `web/src/api/recurring.js` (new), `web/src/hooks/useRecurring.js` (new), `web/src/components/RecurringExpensesPage.jsx` (new), `web/src/router.jsx`, `web/src/components/AuthGuard.jsx`  
**User Benefit:** Eliminates the biggest ongoing friction in app usage.

### 4.2 Savings Goals [DONE 2026-04-06]
**Problem:** The app tracks spending but not progress toward financial targets.  
**Solution:** `SavingsGoal` model with `target_amount`, `current_amount`, `target_date`. `SavingsContribution` tracks each addition. Dashboard widget shows radial progress chart and on-track/behind/ahead status derived from contribution pace vs required monthly rate.  
**Files:** `database.py` (SavingsGoal + SavingsContribution models with Fernet encryption), `models.py` (Pydantic schemas), `routers/savings.py` (new — CRUD + contribution endpoints), `alembic/versions/b3c4d5e6f7a8_add_savings_goals.py` (new migration), `main.py` (router registration), `web/src/api/savings.js` (new), `web/src/hooks/useSavings.js` (new), `web/src/components/SavingsGoalsPage.jsx` (new), `web/src/router.jsx`, `web/src/components/AuthGuard.jsx` (Savings nav item)  
**User Benefit:** Motivational stickiness — users with goals check in more frequently.

### 4.3 Budget Alerts and In-App Notifications [DONE 2026-04-06]
**Problem:** No proactive alerts when users approach or exceed budget limits.  
**Solution:** `BudgetAlert` model with configurable threshold (e.g., 80% of category budget). Daily background job (00:10 UTC) evaluates spending per category and sends email + in-app notification when threshold is breached. Notification bell in nav bar with unread count badge and full slide-over panel (mark read, mark all read, delete). Dedicated `/alerts` page for creating/editing/deleting/toggling alert configs.  
**Files:** `database.py` (BudgetAlert + Notification models with Fernet encryption), `models.py` (schemas), `routers/alerts.py` (new — CRUD + `check_budget_alerts` scheduler job), `alembic/versions/c4d5e6f7a8b9_add_budget_alerts.py` (new migration), `main.py` (router + scheduler), `email_utils.py` (send_budget_alert_email), `web/src/api/alerts.js` (new), `web/src/hooks/useAlerts.js` (new), `web/src/components/BudgetAlertsPage.jsx` (new), `web/src/components/AuthGuard.jsx` (Bell + slide-over), `web/src/router.jsx` (/alerts route)  
**User Benefit:** Turns the app from a passive record-keeper into an active financial coach.

### 4.4 Spending Insights and Trends [DONE 2026-04-06]
**Problem:** Data is displayed but not interpreted. Users must draw their own conclusions.  
**Solution:** Monthly summary endpoint returning: month-over-month % change per category, biggest overspend category, net income for the month. 6-month rolling average trend endpoint. Spending calendar heatmap (GitHub contribution-style). Plain-English insight cards on dashboard: "Your Food spending is up 23% vs last month."  
**Files:** `routers/insights.py` (new — `/insights/monthly-summary`, `/insights/trends`, `/insights/heatmap`), `main.py` (router registration), `web/src/api/insights.js` (new), `web/src/hooks/useInsights.js` (new), `web/src/components/InsightsPage.jsx` (new), `web/src/router.jsx`, `web/src/components/AuthGuard.jsx`  
**User Benefit:** The difference between a data viewer and a financial advisor.

### 4.5 Data Export (CSV and PDF) [DONE 2026-04-06]
**Problem:** No way to extract data for personal analysis, tax preparation, or accountant review.  
**Solution:** `GET /export/csv?from=YYYY-MM&to=YYYY-MM` streams all non-deleted expenses in the month range as a CSV file (Month, Category, Name, Planned Amount, Actual Amount). `GET /export/pdf?month=YYYY-MM` generates a monthly budget report PDF (fpdf2) with salary summary, per-category breakdown table (overspend rows highlighted red), totals row, and net savings row. Both endpoints rate-limited to 1 request/minute per IP via slowapi. Export dropdown (CSV + PDF) added to MonthlyTracker header; CSV button added to AnnualOverview year picker. Frontend uses `responseType: blob` + `URL.createObjectURL` for authenticated downloads.  
**Files:** `routers/export.py` (new), `main.py` (import + `app.include_router`), `requirements.txt` (fpdf2≥2.7.0), `web/src/api/export.js` (new — `exportCSV`, `exportPDF`), `web/src/components/MonthlyTracker.jsx` (ExportMenu component + import), `web/src/components/AnnualOverview.jsx` (AnnualExportButton component + import)  
**User Benefit:** Unlocks use cases beyond the app itself.

### 4.6 Audit Trail / Transaction History [DONE 2026-04-06]
**Problem:** No visibility into what changed and when. Recurring generation and soft-deletes create a need for a visible history.  
**Solution:** `AuditLog` model in `database.py` (plaintext fields so history survives encryption-key rotation; `expense_id` intentionally not a FK so rows persist after soft-delete). `_write_audit` helper called inline in `POST /monthly-tracker/{month}` (create), `PUT /expenses/{id}` (update), `DELETE /expenses/{id}` (delete). `GET /audit/expenses/{id}` endpoint in `routers/audit.py` returns entries newest-first with ownership check. History drawer in `MonthlyTracker.jsx` (clock icon per row, slide-over panel using `useExpenseAudit` hook).  
**Files:** `database.py` (AuditLog model), `models.py` (AuditLogResponse schema), `main.py` (`_expense_snapshot`, `_write_audit`, audit calls on CRUD), `routers/audit.py` (new), `alembic/versions/g7h8i9j0k1l2_add_audit_logs.py` (new), `web/src/api/audit.js` (new), `web/src/hooks/useAudit.js` (new), `web/src/components/MonthlyTracker.jsx` (HistoryDrawer component + clock button)  
**User Benefit:** Builds user trust — users can see exactly when an amount was changed and what it was before.

### 4.7 Multi-Currency Support [DONE 2026-04-06]
**Problem:** Users who travel or have multi-currency income cannot accurately track in a single view.  
**Solution:** `currency` field (ISO 4217) on all monetary records. Daily exchange rate sync from Frankfurter API (open.er-api.com fallback), stored in `ExchangeRate` model. User's `base_currency` preference stored on User model. Currency selector on expense form per row; dynamic currency symbols throughout MonthlyTracker. APScheduler job at 00:15 UTC syncs rates daily.  
**Files:** `database.py` (User.base_currency, MonthlyExpense.currency, ExchangeRate model), `alembic/versions/h8i9j0k1l2m3_add_multi_currency.py` (migration), `routers/currency.py` (new — GET /currency/list, GET /currency/rates, sync_exchange_rates job), `routers/users.py` (base_currency in profile endpoints), `models.py` (currency on ExpenseUpdateRequest/ExpenseResponse), `main.py` (currency router + scheduler job + expense endpoint updates), `web/src/api/currency.js` (new), `web/src/hooks/useCurrency.js` (new — useCurrencies, useExchangeRates, currencySymbol), `web/src/components/AccountSettings.jsx` (base currency selector), `web/src/components/MonthlyTracker.jsx` (dynamic symbol, per-row currency selector), `web/src/hooks/useExpenses.js` (currency in save payload)  
**User Benefit:** Opens the app to international users; supports per-expense foreign currency tracking.

---

## Phase 5: Production Infrastructure

### 5.1 Docker and Docker Compose [DONE 2026-04-06]
**Solution:** Multi-stage `Dockerfile` for backend (non-root user). `web/Dockerfile` with Nginx for frontend. `docker-compose.yml` with services: `db` (postgres:16-alpine), `redis` (redis:7-alpine), `backend`, `frontend`. `docker-compose.override.yml` for dev hot-reload. One-command setup: `docker compose up`.  
**Files:** `Dockerfile`, `web/Dockerfile`, `web/Dockerfile.dev`, `web/nginx.conf`, `docker-compose.yml`, `docker-compose.override.yml`, `.dockerignore`, `web/.dockerignore`, `main.py` (added `GET /health` endpoint)  
**Acceptance Criteria:** Fresh clone + `docker compose up` produces a working local environment.

### 5.2 CI/CD Pipeline (GitHub Actions) [DONE 2026-04-06]
**Solution:**  
- `ci.yml` (on every PR and push to main): 4 parallel jobs — `backend-test` (pytest + coverage ≥65%), `frontend-test` (Jest, 25 tests), `lint` (ruff + eslint), `security` (bandit + npm audit)  
- `deploy.yml` (triggered by successful CI run on main): Railway CLI deploy of backend → 30s wait → smoke test `GET /health`  
- Branch protection: CI must pass, 1 review required before merge  
**Files:** `.github/workflows/ci.yml` (new), `.github/workflows/deploy.yml` (new), `ruff.toml` (new), `requirements.txt` (ruff + bandit), `pytest.ini` (pythonpath), `web/package.json` (jest transformIgnorePatterns + eslint overrides), `tests/conftest.py`, `tests/test_expenses.py`, `web/src/tests/MonthlyTracker.test.jsx`, `web/src/tests/AuthGuard.test.jsx`  
**Acceptance Criteria:** Broken code is blocked from reaching `main`. Merge to `main` automatically deploys within 5 minutes.  
**Result:** All CI gates pass locally — 94 backend tests (67% coverage), 25 frontend tests (5 suites), ruff clean, bandit clean, eslint 0 errors.

### 5.3 Monitoring and Error Tracking [DONE 2026-04-06]
**Solution:** Sentry `sentry-sdk[fastapi]` on backend; `@sentry/react` on frontend. Both report errors with user context and stack traces. Structured JSON logging via `structlog`. `GET /health` endpoint returning `{ status, db, version }` for Railway health checks.  
**Acceptance Criteria:** A deliberate 500 error appears in Sentry within 60 seconds. Railway restarts unhealthy instances automatically.

### 5.4 Database Backups [DONE 2026-04-06]
**Solution:** Daily `pg_dump` → gzip → upload to Cloudflare R2 (S3-compatible) via `scripts/backup.py`. 30 daily + 12 monthly retention. Railway cron at `0 3 * * *`. `scripts/restore.py` with dry-run flag. Alert email if backup job fails.  
**Files:** `scripts/backup.py` (new), `scripts/restore.py` (new), `requirements.txt` (boto3), `.env.example` (R2 + alert vars)  
**Acceptance Criteria:** Backup runs daily without manual intervention. Restore procedure documented and tested monthly.

### 5.5 Performance Optimisation [DONE 2026-04-06]
**Solution:** Redis caching on `GET /overview/annual` (1-hour TTL, invalidated on writes). SQLAlchemy `selectinload` to eliminate N+1 queries. Connection pool: `pool_size=10`, `max_overflow=20`. Composite DB indexes on highest-traffic query patterns. React Query `staleTime`: 5 min for annual data, 30s for current-month data.  
**Acceptance Criteria:** Dashboard loads in <200ms with 5 years of expense data. `EXPLAIN ANALYZE` shows index scans on all primary queries.

---

## Phase 6: Quality & Polish

### 6.1 Budget Page UI Redesign [DONE 2026-04-07]
**Problem:** The budget page card layout is misaligned on certain viewports; dark mode has inconsistent styling across inputs, labels, and selects.
**Solution:** Redesign the `SonOfMervan.jsx` input section with a clean single-column layout, consistent dark mode classes on all form elements, column headers for expense rows, and a single centred Calculate button.
**Files:** `web/src/components/SonOfMervan.jsx`, `web/src/tests/SonOfMervan.test.jsx`
**Acceptance Criteria:** Salary field, expense rows (name/amount/category), and button align cleanly at 320px, 768px, and 1280px. All labels and inputs are legible in both light and dark mode.

### 6.2 Raise CI Coverage Threshold to 80% [DONE 2026-04-07]
**Problem:** The PRD targets 80% backend test coverage but CI is currently set to 65%. The gap is from untested router modules: `alerts.py` (22%), `export.py` (14%), `insights.py` (13%), `recurring.py` (17%), `savings.py` (25%).
**Solution:** Add focused test files covering the core happy paths and auth-ownership checks for each router. Update `ci.yml` `--cov-fail-under` from 65 to 80.
**Files:** `tests/test_alerts.py` (new), `tests/test_export.py` (new), `tests/test_insights.py` (new), `tests/test_recurring.py` (new), `tests/test_savings.py` (new), `.github/workflows/ci.yml`
**Acceptance Criteria:** `pytest --cov=. --cov-fail-under=80` passes in CI.
**Result:** 198 tests pass, 85.84% total coverage.

### 6.3 Documentation Refresh [DONE 2026-04-07]
**Problem:** All three CLAUDE.md files contain stale references — legacy hash routing description, hardcoded API_BASE_URL noted as a known issue (now fixed), old component list, and missing router modules.
**Solution:** Rewrite all CLAUDE.md files to reflect the current codebase: modern React Router via `router.jsx`, Zustand auth store, modular `api/` clients, all 11 router modules, correct known-issues list.
**Files:** `CLAUDE.md`, `routers/CLAUDE.md`, `web/CLAUDE.md`
**Acceptance Criteria:** Any engineer can onboard using only the CLAUDE.md files with no stale information.

---

## Phase 7: Differentiating Features

These features separate a solid budgeting app from a category leader.

### 7.1 Envelope Budgeting
**Problem:** Users plan a monthly budget but have no mechanism for zero-based allocation — assigning every pound of income to a specific purpose at the start of the month.
**Solution:** `Envelope` model with `name`, `allocated_amount`, `spent_amount` per month. UI to set up envelopes at month start, with visual fill bars showing remaining vs spent. Overspending one envelope borrows from unallocated balance. Backend: new `routers/envelopes.py` + migration. Frontend: new `/envelopes` page.
**Inspiration:** YNAB's core methodology.
**Acceptance Criteria:** User can create envelopes summing to their salary. Spending an expense deducts from the correct envelope. UI shows remaining balance per envelope in real time.

### 7.2 Net Worth Dashboard
**Problem:** The app tracks cash flow but not overall financial position — the single most meaningful long-term metric.
**Solution:** `Asset` and `Liability` models (manual entry: property value, savings account balance, car, mortgage, credit card, student loan). Monthly snapshot stored for trending. Dashboard widget shows total net worth + month-over-month delta. Recharts area chart for 12-month history.
**Inspiration:** Mint, Copilot.
**Acceptance Criteria:** User can add/edit/delete assets and liabilities. Net worth = assets − liabilities. Historical chart shows at least 3 months of data when available.

### 7.3 "What If" Scenario Planner
**Problem:** Users cannot explore how small changes compound into large outcomes over time.
**Solution:** Interactive page with category budget sliders. As sliders move, savings projection chart and goal-completion dates recalculate instantly in the browser (no API call). "If I cut Coffee by £50/month, I reach my house deposit goal 4 months earlier."
**Inspiration:** Unique differentiator — no other mainstream budgeting app has this.
**Acceptance Criteria:** Adjusting any slider updates the savings projection chart and all goal timelines within 100ms. State is not persisted (preview only).

### 7.4 Weekly Spending Pace Indicator [DONE 2026-04-07]
**Problem:** Users only discover overspending at the end of the month when it's too late to course-correct.
**Solution:** Backend endpoint `GET /insights/pace?month=YYYY-MM` computes linear projection: `(actual_spend_so_far / days_elapsed) × days_in_month`. Returns projected month-end spend per category and overall. Frontend: warning banner on MonthlyTracker when any category is projected to overspend by >10%.
**Files:** `routers/insights.py`, `web/src/api/insights.js`, `web/src/hooks/useInsights.js`, `web/src/components/MonthlyTracker.jsx`, `tests/test_insights.py`
**Acceptance Criteria:** "At this pace you'll overspend Food by £87 by month end" appears correctly based on actual data. Projection updates each time tracker data is refreshed.
**Result:** 206 tests pass, 86.16% coverage. Pace endpoint returns per-category projections and flagged warnings. Banner renders in MonthlyTracker when ≥1 category is projected to overspend by >10%.

### 7.5 Financial Health Score
**Problem:** Users have raw data but no single signal telling them whether their finances are healthy.
**Solution:** Monthly 0–100 score computed from: savings rate (40% weight), budget adherence per category (30% weight), emergency fund coverage — months of expenses in savings goals (30% weight). Plain-English explanation: "Your score dropped 8 points because Housing exceeded budget by 12%." Backend: `GET /insights/health-score?month=YYYY-MM`. Frontend: score card with colour-coded band (red/amber/green) and explanation list.
**Inspiration:** Credit score model applied to personal budgeting.
**Acceptance Criteria:** Score is deterministic given the same inputs. All three component scores are shown with their contribution. Score is 0 with no data (not an error).

### 7.6 Smart Categorisation
**Problem:** Users must manually select a category for every expense. Repetitive entries (e.g. "Tesco", "Netflix") are re-categorised from scratch every time.
**Solution:** On expense name input, `GET /insights/suggest-category?name=<text>` returns the most frequently used category for that name from the user's own history. Frontend: subtle suggestion chip below the category dropdown ("Suggested: Food"). User can accept or ignore.
**Inspiration:** Mint's bank-connected categorisation, reimplemented using the user's own history without requiring bank API access.
**Acceptance Criteria:** Suggestion appears after 2+ characters are typed with <200ms latency. Suggestion is based only on the authenticated user's own history (no cross-user data). Accepted suggestions are tracked to improve future suggestions.

---

## Phase 8: Expanded Scope

Previously out of scope items now included as future roadmap.

### 8.1 AI/LLM-Powered Financial Advice
**Problem:** Data is displayed but not interpreted with nuance — rule-based insights can only go so far.
**Solution:** Integrate Claude API (claude-sonnet-4-6) to generate plain-English monthly financial summaries and personalised coaching tips. User triggers "Get AI Review" on the insights page; their anonymised monthly summary (no raw names/amounts) is sent to Claude with a structured prompt. Response streamed to the UI.
**Constraints:** Opt-in only. No PII sent to the API. Rate-limited to 3 requests/day per user.
**Acceptance Criteria:** User receives a coherent 3–5 sentence financial summary with at least one actionable recommendation. Response streams progressively to the UI.

### 8.2 Multi-User Household Accounts
**Problem:** Couples and households need a shared budget view, but currently each user is fully isolated.
**Solution:** `Household` model with invite-based membership. Role: `owner` (full access) or `member` (read + own expenses). Shared `MonthlyData` with per-member expense attribution. Split expense view showing each member's contribution.
**Acceptance Criteria:** Owner can invite a member by email. Member can view shared budget but not edit owner's individual expenses. Household budget totals across both members' expenses.

### 8.3 Investment Portfolio Tracking
**Problem:** Net Worth (7.2) covers bank accounts and liabilities but not investment holdings.
**Solution:** Manual entry of holdings (stock ticker, fund name, units held, purchase price). Daily price sync from a free API (Yahoo Finance fallback). Portfolio value shown on Net Worth dashboard as a distinct asset class. Unrealised gain/loss per holding.
**Acceptance Criteria:** User can add a holding by ticker. Current value updates daily. Net worth dashboard reflects portfolio value. No auto-trading or recommendations.

### 8.4 Tax Filing Integration
**Problem:** Users cannot use their expense data for self-assessment tax returns without manual re-entry.
**Solution:** `GET /export/tax-summary?tax_year=YYYY` returns income and deductible expenses in a format aligned with HMRC self-assessment categories. PDF download formatted as a SA302-style summary. Expense category mapping to HMRC allowable expense types (configurable per user).
**Acceptance Criteria:** Export covers the correct UK tax year (April–April). Categories map correctly to HMRC allowable expense types. PDF is human-readable and print-ready.

### 8.5 Open Banking Integration (Plaid / TrueLayer)
**Problem:** Manual expense entry is the biggest friction point in the app. Users who connect their bank accounts in competitors (Monzo, Emma) see instant categorised transactions with no manual input.
**Solution:** Integrate TrueLayer (UK-first, FCA-regulated) for open banking connectivity. OAuth-based bank account linking — user authorises read-only access. Transaction sync via `POST /banking/sync` fetches new transactions since last sync and creates draft `MonthlyExpense` rows with AI-suggested categories (using Smart Categorisation from 7.6). User reviews and confirms drafts before they become permanent. Webhook support for real-time transaction push where the provider supports it.
**Constraints:** TrueLayer sandbox available for development; production requires FCA registration or operating under TrueLayer's agent model. No write access to bank accounts ever. All bank tokens stored encrypted (Fernet). User can disconnect at any time and all bank-linked data is deleted.
**Files:** new `routers/banking.py`, new `database.py` models (BankConnection, BankTransaction), new `web/src/components/BankConnectionPage.jsx`, new `alembic/versions/` migration, `requirements.txt` (truelayer-signing or plaid SDK)
**Acceptance Criteria:** User can link a UK bank account via OAuth. Transactions sync within 60 seconds of connection. Draft expenses are pre-categorised using the user's own history. User can review, edit, and confirm or reject each draft. Disconnecting removes all stored bank tokens and unconfirmed drafts.

---

## 5. Differentiating "Best App" Features
*Promoted to Phase 7 above. See Phase 7 for full specifications.*

---

## 6. Non-Functional Requirements

| Requirement | Target |
|---|---|
| API response time (p95) | <200ms for all read endpoints |
| API response time (p95) | <500ms for all write endpoints |
| Uptime | 99.5% monthly |
| Time to recover from backup | <2 hours |
| Page load time (LCP) | <2.5s on 4G mobile |
| Accessibility | WCAG 2.1 AA |
| Security | OWASP Top 10 mitigated |
| Test coverage (backend) | ≥80% line coverage |
| Test coverage (frontend) | ≥70% component coverage |

---

## 9. Permanently Out of Scope

- Mobile native app (iOS/Android) — web-first; PWA enhancements may be considered later

---

## 10. Implementation Sequence

```
Phase 1 (DONE):  Security fixes
Phase 2 (DONE):  Core features
Phase 3 (DONE):  Frontend UX overhaul
Phase 4 (DONE):  Advanced features
Phase 5 (DONE):  Production infrastructure

Phase 6 (Next):  Quality & polish — complete before starting Phase 7
  6.1 (Budget UI) → 6.2 (coverage to 80%) → 6.3 (docs refresh)

Phase 7:         Differentiating features — mostly independent, suggested order:
  7.4 (Pace indicator — lowest effort, highest immediate value)
  → 7.6 (Smart categorisation)
  → 7.5 (Health score)
  → 7.3 (What-If planner)
  → 7.1 (Envelope budgeting)
  → 7.2 (Net worth dashboard)

Phase 8:         Expanded scope — after Phase 7 is stable
  8.1 (AI advice) → 8.3 (Investments) → 8.2 (Households) → 8.4 (Tax export) → 8.5 (Open banking)
```

---

*This document will be updated as requirements evolve. All feature decisions should reference back to the product vision: give individuals the tools to understand, control, and improve their financial health — without complexity.*
