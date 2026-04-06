Orient yourself to this codebase by doing the following in order:

1. Read CLAUDE.md in the project root — this is your primary reference. It covers architecture, endpoints, DB models, encryption constraints, auth flow, env vars, and known tech debt.

2. If the task involves the frontend, read web/CLAUDE.md — component map, routing strategy, auth state, API base URL issue, data flows.

3. If the task involves the API routers, read routers/CLAUDE.md — what each router owns, relationship to main.py, which are legacy.

4. Read the specific file(s) relevant to the task before making any changes. Never modify code you haven't read.

Key facts to hold in mind at all times:
- All financial fields in DB are Fernet-encrypted. You CANNOT filter them in SQL — always decrypt in Python.
- main.py contains most business logic. crud.py is partially legacy.
- The frontend uses hash routing (#/route) for GitHub Pages compatibility.
- JWT tokens are 24h. Email verification tokens are 60-min.
- Months are stored and compared as "YYYY-MM" strings after decryption.
