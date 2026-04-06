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

### Current Production Readiness: ~40%
The core logic works but the app has critical security gaps, zero test coverage, missing fundamental features (edit/delete expenses, password reset), and no production infrastructure (Docker, CI/CD, monitoring, backups).

---

## 4. Improvement Roadmap

---

## Phase 1: Critical Security Fixes
**Priority: Blocker — must complete before any public users**

### 1.1 Remove Debug/Migration HTTP Endpoints
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

### 2.1 Alembic Database Migrations
**Problem:** Schema changes require a manual migration script with no history or rollback capability.  
**Solution:** Initialise Alembic; configure `env.py` to use `DATABASE_URL` and `Base.metadata`. Generate initial migration. Run `alembic upgrade head` automatically on deploy.  
**Files:** new `alembic/` directory, `alembic.ini`, deploy configuration  
**Acceptance Criteria:** `alembic upgrade head` runs without error on a fresh database. `alembic downgrade -1` successfully rolls back the last migration.

### 2.2 Full CRUD for Expenses and Income
**Problem:** Users cannot edit or delete expenses/income entries. A mis-typed amount is permanent.  
**Solution:** Add `PUT /expenses/{id}` and `DELETE /expenses/{id}` endpoints with user ownership validation. Implement soft-delete (`deleted_at` column) so data is never physically removed. Frontend: edit (pencil) and delete (trash) icons per row; confirmation modal before delete.  
**Files:** `routers/tracker.py`, `models.py`, `crud.py`, `web/src/components/ExpenseRow.jsx`, new `web/src/components/ConfirmModal.jsx`  
**Acceptance Criteria:** User can edit any expense they own. User cannot edit another user's expense (returns 403). Deleted expenses disappear from UI but remain in DB with `deleted_at` set.

### 2.3 Password Reset Flow
**Problem:** No password recovery exists. A user who forgets their password is permanently locked out.  
**Solution:** `POST /auth/password-reset-request` sends a SendGrid email with a signed, time-limited token link (1-hour TTL). `POST /auth/password-reset-confirm` validates the token (single-use) and updates the password. Frontend: "Forgot password?" link on login page; two new pages for request and confirm flows.  
**Files:** `routers/signup.py`, `models.py` (PasswordResetToken), `email_utils.py`, new frontend pages  
**Acceptance Criteria:** User receives email within 30 seconds of request. Token link works once only. Expired tokens return a clear error. Reused tokens are rejected.

### 2.4 JWT Refresh Token Mechanism
**Problem:** Long-lived access tokens are a security risk; short-lived tokens force frequent re-logins.  
**Solution:** Issue `access_token` (15-min TTL) and `refresh_token` (30-day TTL, httpOnly cookie) on login. `POST /auth/refresh` issues new access tokens. `POST /auth/logout` revokes the refresh token. Frontend Axios interceptor catches 401, silently refreshes, retries original request. Access token stored in memory only (not localStorage).  
**Files:** `routers/signup.py`, `models.py` (RefreshToken), `security.py`, `web/src/api/client.js`, `web/src/store/authStore.js`  
**Acceptance Criteria:** User stays logged in for 30 days without action. Logging out invalidates the session on all future requests immediately.

### 2.5 Pagination and Filtering
**Problem:** All expenses are returned in a single API call. Performance degrades and UI becomes unusable with large datasets.  
**Solution:** Add `?page=1&page_size=25&month=2025-03&category=Food` query params to expense endpoints. Return `{ items, total, page, pages }` envelope. Add DB indexes on `(user_id, date)` and `(user_id, category)`. Frontend: pagination controls and filter bar.  
**Files:** `routers/tracker.py`, `models.py`, `web/src/components/ExpenseList.jsx`, new `web/src/components/FilterBar.jsx`  
**Acceptance Criteria:** API returns correct page slice. Total count matches unfiltered row count. Response time under 200ms with 10,000 expense rows.

### 2.6 Account Management
**Problem:** Users cannot update their profile, change their password while logged in, or delete their account.  
**Solution:** `GET/PUT /users/me` (profile), `PUT /users/me/password` (requires current password), `DELETE /users/me` (30-day soft-delete grace period with confirmation email). Frontend: Account Settings page with Profile, Security, and Danger Zone sections.  
**Files:** new `routers/users.py`, new `services/user_service.py`, new `web/src/pages/AccountSettings.jsx`  
**Acceptance Criteria:** Profile updates persist. Password change requires correct current password. Account deletion sends confirmation email and removes all personal data after 30 days. GDPR-compliant.

### 2.7 Backend Test Suite (Target: 80% line coverage)
**Problem:** Zero backend tests. Every change is an undetected potential regression.  
**Solution:** `pytest` + `httpx.AsyncClient` + `pytest-asyncio`. SQLite in-memory DB fixture overrides `get_db` in tests. Test categories: auth flows, expense CRUD and ownership enforcement, budget calculation logic, encryption (verify no plaintext in DB).  
**Files:** new `tests/conftest.py`, `tests/test_auth.py`, `tests/test_expenses.py`, `tests/test_budget.py`, `tests/test_encryption.py`  
**Acceptance Criteria:** `pytest --cov=. --cov-fail-under=80` passes in CI. All test categories covered.

---

## Phase 3: Frontend UX Overhaul

### 3.1 Centralised API Client
**Problem:** API base URL is hardcoded to the production Railway URL. Local development requires source code changes.  
**Solution:** Single Axios instance in `web/src/api/client.js` configured from `REACT_APP_API_URL` environment variable. Feature modules: `api/expenses.js`, `api/budget.js`, `api/auth.js`. Includes 401 refresh interceptor.  
**Files:** new `web/src/api/client.js` and feature modules, `web/.env.example`  
**Acceptance Criteria:** `REACT_APP_API_URL=http://localhost:8000` routes all calls to local backend without code changes.

### 3.2 React Router v6
**Problem:** Custom hash routing is fragile, doesn't support nested routes, and breaks browser history.  
**Solution:** `react-router-dom` v6 with `createHashRouter`. Routes: `/dashboard`, `/expenses`, `/budget`, `/annual`, `/login`, `/register`, `/reset-password`, `/settings`. `<AuthGuard>` redirects unauthenticated users to `/login`.  
**Files:** new `web/src/router.jsx`, `web/src/App.jsx`, new `web/src/components/AuthGuard.jsx`  
**Acceptance Criteria:** Browser back/forward work correctly. Bookmarked URLs load the correct page. Unauthenticated users redirected from protected routes.

### 3.3 React Query + Loading States + Optimistic Updates
**Problem:** No loading indicators. API calls produce blank UI until resolved.  
**Solution:** `@tanstack/react-query` for all server state. Skeleton shimmer components during loading. Optimistic updates on expense CRUD with rollback on error. `react-hot-toast` for success/error feedback.  
**Files:** `web/src/App.jsx`, new hooks (`useExpenses`, `useBudget`, `useAnnualSummary`), new `web/src/components/Skeleton.jsx`  
**Acceptance Criteria:** Every data-loading state shows a meaningful skeleton. Expense added/edited/deleted updates the UI instantly before server confirms. Failed mutations roll back with a toast error.

### 3.4 Global Error Boundaries
**Problem:** Any uncaught JavaScript error crashes the entire app to a blank white screen.  
**Solution:** `ErrorBoundary` class component wrapping the root app and each major page individually. Renders a "Something went wrong" UI with a Reload button. Reports to Sentry (Phase 5).  
**Files:** new `web/src/components/ErrorBoundary.jsx`, new `web/src/components/AsyncBoundary.jsx`, `web/src/App.jsx`  
**Acceptance Criteria:** A deliberate thrown error in a chart component shows the page-level error fallback UI without crashing the nav or other pages.

### 3.5 Zustand Global State Management
**Problem:** Auth state and UI state are scattered across components with no clear ownership.  
**Solution:** Zustand stores: `authStore` (user + in-memory access token), `uiStore` (theme, active modal). React Query owns all server state.  
**Files:** new `web/src/store/authStore.js`, `web/src/store/uiStore.js`  
**Acceptance Criteria:** Access token never written to localStorage. Auth state accessible from any component without prop drilling.

### 3.6 Dark Mode
**Problem:** No dark mode. Table stakes for any consumer app in 2025+.  
**Solution:** CSS custom properties (`--color-bg`, `--color-surface`, etc.) applied to `:root` and overridden under `[data-theme="dark"]`. `useTheme` hook reads from `localStorage` and falls back to `prefers-color-scheme`. Moon/Sun toggle in nav bar.  
**Files:** new `web/src/styles/tokens.css`, new `web/src/hooks/useTheme.js`, `web/src/components/Nav.jsx`  
**Acceptance Criteria:** Theme persists across sessions. Automatically matches OS preference on first visit. All Recharts charts use theme-aware colors.

### 3.7 Mobile-First Responsive Design
**Problem:** App likely breaks below ~768px with no explicit responsive design.  
**Solution:** Fluid CSS Grid replacing fixed-width layouts. Bottom tab bar on mobile (<768px). Expense table → card-stack layout on mobile. WCAG 2.5.5-compliant touch targets (min 44×44px). Tested on iPhone 14 Pro, Pixel 7, iPad, and 320px min width.  
**Files:** `web/src/components/Nav.jsx`, `web/src/components/ExpenseList.jsx`, `web/src/pages/DashboardPage.jsx`, new `web/src/styles/breakpoints.css`  
**Acceptance Criteria:** App is fully usable at 320px width. No horizontal scroll on any page. All interactive targets are at least 44×44px.

### 3.8 Frontend Test Suite (Target: 70% coverage)
**Problem:** Only one dummy smoke test exists.  
**Solution:** Vitest + React Testing Library + MSW for API mocking. Tests for: `LoginForm`, `ExpenseRow` (edit/delete), `BudgetChart` (data + empty state), `AuthGuard` (redirect behaviour).  
**Files:** new `web/src/tests/`, new `web/src/mocks/handlers.js`  
**Acceptance Criteria:** `vitest run --coverage` reports ≥70% component coverage. All tests pass in CI.

---

## Phase 4: Advanced Features

### 4.1 Recurring Expenses
**Problem:** Most real expenses (rent, subscriptions, utilities) recur monthly. Users must re-enter them every period.  
**Solution:** `RecurringExpense` model with `frequency` ENUM (daily/weekly/monthly/yearly), `start_date`, `end_date`, `last_generated_at`. Daily background job auto-generates actual expense rows. Frontend: "Recurring" toggle on expense form; dedicated management page.  
**User Benefit:** Eliminates the biggest ongoing friction in app usage.

### 4.2 Savings Goals
**Problem:** The app tracks spending but not progress toward financial targets.  
**Solution:** `SavingsGoal` model with `target_amount`, `current_amount`, `target_date`. `SavingsContribution` tracks each addition. Dashboard widget shows radial progress chart and on-track/behind/ahead status derived from contribution pace vs required monthly rate.  
**User Benefit:** Motivational stickiness — users with goals check in more frequently.

### 4.3 Budget Alerts and In-App Notifications
**Problem:** No proactive alerts when users approach or exceed budget limits.  
**Solution:** `BudgetAlert` model with configurable threshold (e.g., 80% of category budget). Daily background job evaluates spending per category and sends email + in-app notification when threshold is breached. Notification bell in nav bar with unread count and slide-over panel.  
**User Benefit:** Turns the app from a passive record-keeper into an active financial coach.

### 4.4 Spending Insights and Trends
**Problem:** Data is displayed but not interpreted. Users must draw their own conclusions.  
**Solution:** Monthly summary endpoint returning: month-over-month % change per category, biggest overspend category, net income for the month. 6-month rolling average trend endpoint. Spending calendar heatmap (GitHub contribution-style). Plain-English insight cards on dashboard: "Your Food spending is up 23% vs last month."  
**User Benefit:** The difference between a data viewer and a financial advisor.

### 4.5 Data Export (CSV and PDF)
**Problem:** No way to extract data for personal analysis, tax preparation, or accountant review.  
**Solution:** `GET /export/csv?from=YYYY-MM-DD&to=YYYY-MM-DD` streams expenses as CSV. `GET /export/pdf?month=YYYY-MM` generates a monthly budget report PDF with charts. Export dropdown in expense list and annual overview. Rate-limited to 1 export/minute/user.  
**User Benefit:** Unlocks use cases beyond the app itself.

### 4.6 Audit Trail / Transaction History
**Problem:** No visibility into what changed and when. Recurring generation and soft-deletes create a need for a visible history.  
**Solution:** `AuditLog` model populated by SQLAlchemy event listeners on all CRUD operations. Stores `action`, `changed_fields` (JSONB), `timestamp`, `user_id`. History drawer on each expense row showing all past versions.  
**User Benefit:** Builds user trust — users can see exactly when an amount was changed and what it was before.

### 4.7 Multi-Currency Support
**Problem:** Users who travel or have multi-currency income cannot accurately track in a single view.  
**Solution:** `currency` field (ISO 4217) on all monetary records. Daily exchange rate sync from a free API, stored in `ExchangeRate` model. All aggregates convert to the user's `base_currency` at the rate on the transaction date. Currency selector on expense form; toggle on totals ("Show in GBP / Show in original currencies").  
**User Benefit:** Opens the app to international users.

---

## Phase 5: Production Infrastructure

### 5.1 Docker and Docker Compose
**Solution:** Multi-stage `Dockerfile` for backend (non-root user). `web/Dockerfile` with Nginx for frontend. `docker-compose.yml` with services: `db` (postgres:16-alpine), `redis` (redis:7-alpine), `backend`, `frontend`. `docker-compose.override.yml` for dev hot-reload. One-command setup: `docker compose up`.  
**Acceptance Criteria:** Fresh clone + `docker compose up` produces a working local environment.

### 5.2 CI/CD Pipeline (GitHub Actions)
**Solution:**  
- `ci.yml` (on every PR): backend tests (pytest + coverage), frontend tests (vitest), lint (ruff + eslint), security scan (bandit + npm audit)  
- `deploy.yml` (on merge to `main`): CI as prerequisite → Railway deploy → smoke test `GET /health`  
- Branch protection: CI must pass, 1 review required before merge  
**Acceptance Criteria:** Broken code is blocked from reaching `main`. Merge to `main` automatically deploys within 5 minutes.

### 5.3 Monitoring and Error Tracking
**Solution:** Sentry `sentry-sdk[fastapi]` on backend; `@sentry/react` on frontend. Both report errors with user context and stack traces. Structured JSON logging via `structlog`. `GET /health` endpoint returning `{ status, db, version }` for Railway health checks.  
**Acceptance Criteria:** A deliberate 500 error appears in Sentry within 60 seconds. Railway restarts unhealthy instances automatically.

### 5.4 Database Backups
**Solution:** Daily `pg_dump` → gzip → upload to Cloudflare R2 (S3-compatible) via `scripts/backup.py`. 30 daily + 12 monthly retention. Railway cron at `0 3 * * *`. `scripts/restore.py` with dry-run flag. Alert email if backup job fails.  
**Acceptance Criteria:** Backup runs daily without manual intervention. Restore procedure documented and tested monthly.

### 5.5 Performance Optimisation
**Solution:** Redis caching on `GET /overview/annual` (1-hour TTL, invalidated on writes). SQLAlchemy `selectinload` to eliminate N+1 queries. Connection pool: `pool_size=10`, `max_overflow=20`. Composite DB indexes on highest-traffic query patterns. React Query `staleTime`: 5 min for annual data, 30s for current-month data.  
**Acceptance Criteria:** Dashboard loads in <200ms with 5 years of expense data. `EXPLAIN ANALYZE` shows index scans on all primary queries.

---

## 5. Differentiating "Best App" Features (Post Phase 5)

These features separate a solid budgeting app from a category leader:

| Feature | Description | Inspiration |
|---|---|---|
| **Envelope Budgeting** | Zero-based allocation: every pound of income assigned to a named "envelope" at month start. Overspending one envelope borrows from another. | YNAB's core methodology |
| **Net Worth Dashboard** | Assets minus liabilities, tracked monthly. The single most meaningful long-term financial metric. | Mint, Copilot |
| **"What If" Scenario Planner** | Sliders adjusting category budgets and instantly recomputing savings goal timelines. "If I cut coffee by £50/month, I hit my deposit goal 4 months earlier." | Unique differentiator |
| **Weekly Spending Pace Indicator** | "At this pace you'll overspend Food by £87 by month end." Linear projection updated daily. | Internal original |
| **Financial Health Score** | 0–100 monthly score from savings rate, budget adherence, emergency fund coverage. Plain-English explanation of what's driving it. | Credit score model applied to budgeting |
| **Smart Categorisation** | Suggest category based on expense description + user's own past categorisation history. "Tesco" → "Groceries". | Mint's bank-connected categorisation, reimplemented without bank APIs |

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

## 7. Out of Scope

- Bank/open banking API integration (Plaid, TrueLayer) — manual entry only for v1
- Investment portfolio tracking
- Tax filing integration
- Multi-user household accounts
- Mobile native app (iOS/Android) — web-first
- AI/LLM-powered financial advice

---

## 8. Implementation Sequence

```
Phase 1 (Week 1–2):   Security fixes — must complete before any public users
  1.1 → 1.2 → 1.3 → 1.4

Phase 2 (Week 3–6):   Core features — 2.1 (Alembic) must go first
  2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 (tests written alongside)

Phase 3 (Week 7–10):  Frontend — 3.1 (API client) unblocks all others
  3.1 → 3.2 → 3.3 → 3.7 → 3.4 → 3.5 → 3.6 → 3.8

Phase 4 (Week 11–18): Advanced features — mostly independent
  4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7

Phase 5 (Ongoing):    Infrastructure — 5.1 can start immediately
  5.1 → 5.2 (once tests exist) → 5.3 → 5.4 → 5.5
```

---

*This document will be updated as requirements evolve. All feature decisions should reference back to the product vision: give individuals the tools to understand, control, and improve their financial health — without complexity.*
