# Frontend — CLAUDE.md

## Stack
React 19, React Router v6 (`createHashRouter`), Tailwind CSS, Recharts (charts), Lucide React (icons), Axios (HTTP), `@tanstack/react-query` (server state), Zustand (client state), `react-hot-toast` (feedback). Build tooling: Create React App.

## Source layout
```
web/src/
├── App.jsx                          # Root: QueryClientProvider + AuthProvider wrapper
├── App.js                           # Legacy CRA entry (thin re-export of App.jsx; can be removed)
├── router.jsx                       # createHashRouter — all routes defined here
├── index.js                         # React entry point
├── index.css
├── api/
│   ├── client.js                    # Shared Axios instance; reads REACT_APP_API_URL; 401 refresh interceptor
│   ├── auth.js                      # login, signup, verifyEmail, refresh, logout, passwordReset*
│   ├── budget.js                    # calculateBudget
│   ├── expenses.js                  # updateExpense, deleteExpense
│   ├── users.js                     # getProfile, updateProfile, changePassword, deleteAccount
│   ├── recurring.js                 # listRecurring, createRecurring, updateRecurring, deleteRecurring, triggerGenerate
│   ├── savings.js                   # listGoals, createGoal, updateGoal, deleteGoal, addContribution
│   ├── alerts.js                    # listAlerts, createAlert, updateAlert, deleteAlert + notifications CRUD
│   ├── insights.js                  # getMonthlySummary, getSpendingTrends, getSpendingHeatmap
│   ├── export.js                    # exportCSV, exportPDF (responseType: blob)
│   ├── audit.js                     # getExpenseAudit
│   └── currency.js                  # getCurrencies, getExchangeRates
├── hooks/
│   ├── useBudget.js                 # useCalculateBudget mutation
│   ├── useExpenses.js               # useTrackerData, useUpdateExpense, useDeleteExpense
│   ├── useAnnualSummary.js          # useAnnualSummary (staleTime 5 min)
│   ├── useProfile.js                # useProfile, useUpdateProfile, useChangePassword
│   ├── useRecurring.js              # useRecurring, useCreate/Update/DeleteRecurring, useTriggerGenerate
│   ├── useSavings.js                # useSavingsGoals, useCreate/Update/DeleteGoal, useAddContribution
│   ├── useAlerts.js                 # useBudgetAlerts + notification hooks (polls every 60s)
│   ├── useInsights.js               # useMonthlySummary, useSpendingTrends, useSpendingHeatmap
│   ├── useAudit.js                  # useExpenseAudit
│   ├── useCurrency.js               # useCurrencies, useExchangeRates, currencySymbol helper
│   └── useTheme.js                  # reads uiStore.theme; applies data-theme attr + dark class to <html>
├── store/
│   ├── authStore.js                 # Zustand: isAuthenticated, token (in-memory), loading; handleLogin, clearAuth
│   └── uiStore.js                   # Zustand: theme (light/dark), activeModal
├── context/
│   └── AuthContext.jsx              # Thin wrapper — runs refreshSession() on mount; exposes handleLogout
├── components/
│   ├── AuthGuard.jsx                # Route guard + desktop sidebar + mobile bottom tab bar + notification bell
│   ├── LoginPage.jsx
│   ├── SignUpPage.jsx
│   ├── ForgotPasswordPage.jsx
│   ├── ResetPasswordPage.jsx
│   ├── VerifyEmailPage.jsx
│   ├── SonOfMervan.jsx             # Budget planning — salary + expense rows + results + charts
│   ├── MonthlyTracker.jsx          # Expense tracker — month picker, edit/delete per row, history drawer, export
│   ├── AnnualOverview.jsx          # Year selector + charts + table + CSV export
│   ├── AccountSettings.jsx         # Profile, security, base currency, danger zone
│   ├── RecurringExpensesPage.jsx   # Recurring template management
│   ├── SavingsGoalsPage.jsx        # Savings goal CRUD + contribution logging
│   ├── BudgetAlertsPage.jsx        # Alert threshold management
│   ├── InsightsPage.jsx            # Monthly summary, trends chart, category chart, heatmap
│   ├── ConfirmModal.jsx            # Reusable confirmation dialog
│   ├── ErrorBoundary.jsx           # Class component; renders fallback UI on unhandled throw
│   ├── AsyncBoundary.jsx           # ErrorBoundary + Suspense (falls back to SkeletonCard)
│   ├── Skeleton.jsx                # Shimmer skeleton components for loading states
│   └── Toast.jsx                   # Legacy toast (replaced by react-hot-toast; kept for compatibility)
├── mocks/
│   └── handlers.js                 # MSW-style handler documentation for test stubs
├── styles/
│   ├── tokens.css                  # CSS custom properties for colours + Recharts; light/dark overrides
│   └── breakpoints.css             # Breakpoint reference + .safe-area-bottom utility
└── tests/
    ├── LoginPage.test.jsx
    ├── AuthGuard.test.jsx
    ├── SonOfMervan.test.jsx
    └── MonthlyTracker.test.jsx
```

## Routing
React Router v6 `createHashRouter` in `router.jsx`. Hash-based routing (`#/route`) is used for GitHub Pages compatibility.

Key routes:
- `/login` → LoginPage
- `/register` → SignUpPage
- `/forgot-password` → ForgotPasswordPage
- `/verify-email` → VerifyEmailPage
- `/reset-password` → ResetPasswordPage
- `/` → redirects to `/budget`
- `/budget` → SonOfMervan (protected, wrapped in ErrorBoundary)
- `/expenses` → MonthlyTracker (protected)
- `/annual` → AnnualOverview (protected)
- `/recurring` → RecurringExpensesPage (protected)
- `/savings` → SavingsGoalsPage (protected)
- `/alerts` → BudgetAlertsPage (protected)
- `/insights` → InsightsPage (protected)
- `/settings` → AccountSettings (protected)

`AuthGuard` is the layout component for all protected routes. Unauthenticated users are redirected to `/login`.

## Auth state
- Access token held **in-memory only** in Zustand `authStore` — never written to localStorage
- `AuthContext.jsx` calls `POST /auth/refresh` on mount to restore session from httpOnly cookie
- Axios `client.js` interceptor: on 401, attempts refresh, then retries the original request; on refresh failure calls `clearAuth()` and redirects to login
- On logout: `POST /auth/logout` revokes the refresh token server-side, Zustand store cleared

## API base URL
Configured from `REACT_APP_API_URL` environment variable in `web/src/api/client.js`.
Create `web/.env.local` with:
```
REACT_APP_API_URL=http://localhost:8000
```
Production uses the Railway URL set in CI/CD.

## State management
- **Server state:** React Query (`@tanstack/react-query`) — all API data lives in Query cache
- **Auth state:** Zustand `authStore` — token + authenticated flag
- **UI state:** Zustand `uiStore` — theme, active modal
- **Local component state:** `useState`/`useEffect` for form inputs and ephemeral UI

## Dark mode
`useTheme` reads `uiStore.theme`, applies `data-theme="dark"` + `dark` class to `<html>`, writes to `localStorage`. Tailwind `dark:` variants are active when `<html class="dark">` is set (configured in `web/public/index.html`). CSS custom properties in `tokens.css` drive Recharts chart colours; all charts are theme-aware.

## Expense categories (hardcoded in frontend forms)
```js
["Housing", "Transportation", "Food", "Utilities", "Insurance", "Healthcare", "Entertainment", "Other"]
```

## Key data flows

### Budget planning (SonOfMervan.jsx)
1. User enters salary + expense rows (name, category, planned amount)
2. `POST /calculate-budget` with `commit=false` → preview totals, percentages, savings rate
3. User clicks "Save" → same request with `commit=true` → persists to DB

### Monthly tracking (MonthlyTracker.jsx)
1. User picks month (YYYY-MM)
2. `GET /monthly-tracker/{month}` → loads planned vs actual per category
3. User enters actual amounts → `POST /monthly-tracker/{month}` (upsert)
4. Edit (pencil) and delete (trash) icons per row; history drawer (clock icon) shows AuditLog entries
5. Export dropdown: CSV (`/export/csv`) or PDF (`/export/pdf`) via blob download

### Annual overview (AnnualOverview.jsx)
1. User selects year
2. `GET /overview/annual?year=YYYY` → per-month + year totals
3. Displayed as Recharts bar/line chart + summary table; CSV export button

## Build & deploy
```bash
cd web
npm install
npm start          # dev server on localhost:3000
npm test           # Jest test suite (target: ≥70% coverage)
npm run build      # production build → web/build/
```

Deployment to GitHub Pages is handled by `deploy.yml` GitHub Actions workflow after CI passes on `main`.
