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

# Then: check a price (session is reused, no password needed)
python price_check.py "wireless mouse"
python price_check.py "wireless mouse" --top 5      # more results
python price_check.py "wireless mouse" --json       # machine-readable
python price_check.py --url "https://www.amazon.com/dp/B0XXXXXXX"
```

If a check later says the session is invalid/expired, just re-run
`python login.py`.

> Reminder: always use the existing `.venv` (activate it); don't recreate it.

## Files

| File              | Purpose                                            |
| ----------------- | -------------------------------------------------- |
| `login.py`        | One-time manual login; saves `auth_state.json`.    |
| `price_check.py`  | Searches/loads a product and reports its price.    |
| `.env.example`    | Template config — copy to `.env`. No secrets.      |
| `.gitignore`      | Keeps secrets, sessions, logs out of git.          |
| `CLAUDE.md`       | Project instructions, security & workflow rules.   |
