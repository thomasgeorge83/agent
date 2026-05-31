# Amazon Search Agent (learning project)

A small browser-automation agent (Python + Playwright) that signs in to **your
own** Amazon account and searches for an item.

> Security rules for this repo live in [CLAUDE.md](CLAUDE.md). In short: no
> passwords in code, secrets via git-ignored files only, no personal data in
> logs, respect Amazon's Terms of Service, automate only your own account.

## How login works (no password stored)

You log in **manually one time** in a real browser window. Playwright saves the
resulting session (`auth_state.json`, git-ignored). The agent reuses that
session, so your password and OTP are never typed or stored by any script.

## Setup

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies and the browser
pip install -r requirements.txt
python -m playwright install chromium

# 3. Create your local config (no secrets in it)
Copy-Item .env.example .env
```

## Use

```powershell
# One-time: log in manually; saves the session
python login.py

# Then: search (session is reused, no password needed)
python search.py "wireless mouse"
```

If a search later says the session is invalid/expired, just re-run
`python login.py`.

## Files

| File              | Purpose                                            |
| ----------------- | -------------------------------------------------- |
| `login.py`        | One-time manual login; saves `auth_state.json`.    |
| `search.py`       | Loads the session and runs a search (skeleton).    |
| `.env.example`    | Template config — copy to `.env`. No secrets.      |
| `.gitignore`      | Keeps secrets, sessions, logs out of git.          |
| `CLAUDE.md`       | Security & workflow rules for this repo.            |
