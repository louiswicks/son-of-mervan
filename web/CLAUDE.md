# Frontend — CLAUDE.md

## Stack
React 19, Tailwind CSS, Recharts (charts), Lucide React (icons), Axios (HTTP), Create React App build tooling.

## Source layout
```
web/src/
├── App.js                          # Root: auth state, routing, API_BASE_URL
├── App.css                         # Global styles
├── index.js                        # React entry point
└── components/
    ├── LoginPage.jsx               # Email + password login form
    ├── SignUpPage.jsx              # Registration form with password policy UI
    ├── VerifyEmailPage.jsx         # Handles #/verify-email?token=… on load
    ├── SonOfMervan.jsx             # Budget planning — salary input + expense rows + results
    ├── MonthlyTracker.jsx          # Actual expense tracking — month picker + entry form
    ├── AnnualOverview.jsx          # Year selector + aggregated charts/table
    └── Toast.jsx                   # Notification overlay (success/error/info)
```

## Routing
Uses **URL hash routing** (`#/route`) — no React Router. Reason: deployed on GitHub Pages which can't handle path-based routing.

Hash is read from `window.location.hash` and a `hashchange` listener drives view switching in `App.js`.

Key routes:
- `#/` or `#/login` → LoginPage
- `#/signup` → SignUpPage
- `#/verify-email` → VerifyEmailPage (token read from query string)
- `#/budget` → SonOfMervan (protected)
- `#/tracker` → MonthlyTracker (protected)
- `#/overview` → AnnualOverview (protected)

## Auth state
- JWT stored in `localStorage` under key `token`
- `App.js` calls `GET /verify-token` on load to confirm token is still valid
- On logout: token removed from localStorage, hash set to `#/login`
- All API calls include `Authorization: Bearer <token>` header

## API base URL (known issue)
`API_BASE_URL` is defined at the top of `App.js` and **hardcoded** to the Railway production URL.
When working locally you'll need to change this or set it via an env variable.

## State management
Plain React hooks — no Redux or context. Each page component manages its own local state via `useState`/`useEffect`/`useCallback`/`useMemo`.

## Key data flows

### Budget planning (SonOfMervan.jsx)
1. User enters salary + list of expense rows (name, category, planned amount)
2. `POST /calculate-budget` with `commit=false` → preview totals, percentages, savings rate
3. User clicks "Save" → same request with `commit=true` → persists to DB
4. Response shown as breakdown table + Recharts pie chart

### Monthly tracking (MonthlyTracker.jsx)
1. User picks month (YYYY-MM picker)
2. `GET /monthly-tracker/{month}` → loads existing planned vs actual per category
3. User enters actual amounts → `POST /monthly-tracker/{month}`
4. UI updates with new remaining balance

### Annual overview (AnnualOverview.jsx)
1. User selects year
2. `GET /overview/annual?year=YYYY` → per-month + year totals
3. Displayed as bar/line chart (Recharts) + summary table

## Expense categories (hardcoded)
```js
["Housing", "Transportation", "Food", "Utilities", "Insurance", "Healthcare", "Entertainment", "Other"]
```

## Build & deploy
```bash
cd web
npm install
npm start          # dev server on localhost:3000
npm run build      # production build → web/build/
npm run deploy     # gh-pages deploy to GitHub Pages (if configured)
```
