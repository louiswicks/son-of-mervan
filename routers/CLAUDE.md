# Routers — CLAUDE.md

These FastAPI routers are included in `main.py` via `app.include_router(...)`.

## signup.py — `/auth` prefix
Handles user registration and email verification.

| Method | Path | What it does |
|--------|------|-------------|
| POST | `/auth/signup` | Validates password policy, bcrypt hashes password, creates User, sends SendGrid verification email |
| GET | `/auth/verify-email?token=…` | Decodes JWT verification token, sets `email_verified=True` on User |

**Password policy** (enforced in signup.py):
- Minimum 8 characters
- At least one uppercase, one lowercase, one digit, one special character

**Email verification token:** JWT with 60-minute TTL. If `SENDGRID_API_KEY` is not set, the verification link is printed to the console — useful for local dev.

## tracker.py — `/tracker` prefix (legacy)
Legacy routes that overlap with the `/monthly-tracker/{month}` endpoints in `main.py`.
These use `crud.py` helper functions.

| Method | Path | What it does |
|--------|------|-------------|
| POST | `/tracker/` | Save monthly tracking data |
| GET | `/tracker/{month}` | Retrieve tracking data for a month |

**Status:** Partially unused. The frontend currently calls `/monthly-tracker/{month}` in `main.py`, not these routes. Candidate for removal or consolidation.

## overview.py — `/overview` prefix
Annual aggregation endpoint.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/overview/annual?year=YYYY` | Fetch all MonthlyData for user in given year, aggregate totals, return per-month breakdown + year totals |

**Implementation note:** Month filtering happens in Python after decryption (because Fernet is non-deterministic). Months are compared by checking if the decrypted YYYY-MM string starts with the requested year.
Missing months are returned as zero-value placeholders so the frontend always gets all 12 months.
