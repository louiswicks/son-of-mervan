# E2E Tests — Son-of-Mervan

Critical-path end-to-end tests using [pytest-playwright](https://playwright.dev/python/).

These tests start a **real uvicorn server** on port 8799 backed by an isolated SQLite database.
No mocking — every test exercises the full HTTP stack.

## Prerequisites

```bash
pip install -r requirements.txt
playwright install chromium   # downloads the browser binary (needed for Playwright)
```

## Running locally

From the project root:

```bash
pytest e2e/ -v
```

To see server output during the run add `--capture=no`.

## What is tested

| Scenario | Coverage |
|---|---|
| Signup → email verify → login | `POST /auth/signup`, `GET /auth/verify-email`, `POST /login` |
| Calculate budget (commit=false) | `POST /calculate-budget` read-only planning mode |
| POST monthly tracker actuals | `POST /monthly-tracker/{month}` + `GET /monthly-tracker/{month}` |
| GET annual overview | `GET /overview/annual?year=YYYY` |

## Design notes

- Server is started **once per session** (`scope="session"`) on port 8799 and torn down afterwards.
- The SQLite DB file (`e2e/e2e_test.db`) is deleted when the session ends.
- A dedicated test user (`e2e_test_user@example.com`) is registered and verified at session start.
  One-off scenarios (e.g. `TestSignupVerifyLogin`) register separate disposable accounts.
- Email verification works without SMTP: the server returns `dev_verify_url` in the signup
  response when `SENDGRID_API_KEY` / `SMTP_HOST` are not set, and the conftest extracts the
  JWT token from that URL.
- The `auth_token` session fixture re-uses the same token across all tests that need authentication.

## CI

The `e2e` job in `.github/workflows/ci.yml` runs after `backend-test`.
It installs dependencies, installs the Playwright browser binary, then runs `pytest e2e/ -v`.
