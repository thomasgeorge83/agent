# Shop Agent (learning project)

A modular browser-automation toolkit (Python + Playwright) that signs in to
**your own** online-shop accounts and works with them — currently searching and
checking prices, with order actions stubbed out for future work. Amazon is the
first supported shop; the design makes adding more shops a one-file job.

> Security rules for this repo live in [CLAUDE.md](CLAUDE.md). In short: no
> passwords in code, secrets via git-ignored files only, no personal data in
> logs, respect each shop's Terms of Service, automate only your own account.

## How login works (no password stored)

You log in **manually one time** per shop in a real browser window. Playwright
saves the resulting session (`auth_state.<shop>.json`, git-ignored). The agent
reuses that session, so your password and OTP are never typed or stored.

## Architecture

```
shopagent/              reusable core (import this)
  models.py             Product, OrderResult
  errors.py             SessionExpired, BlockedBySite, ActionNotSupported, ...
  session.py            per-shop session files + browser lifecycle
  agent.py              login / search / get_product orchestration
  render.py             text + JSON output
  shops/
    base.py             Shop base class — the extension point
    registry.py         name -> Shop lookup
    amazon.py           Amazon implementation
login.py / price_check.py / gui.py   thin entry points over the package
```

**Add a new shop:** create `shopagent/shops/<name>.py` with a `Shop` subclass
(set `name`/`label`/`base_url`, implement `is_logged_in` and `search`), decorate
it with `@register_shop`, and import it in `shops/__init__.py`. It then appears
in the CLI (`--shop <name>`) and the GUI dropdown automatically.

**Order actions** (`place_order`, `modify_order`, `cancel_order`) are defined on
the base class but **refuse by default** (`ActionNotSupported`) and require an
explicit `confirm=True`. They are intentionally not wired to spend money yet.

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

### Desktop app (easiest)

Double-click **`Price Checker.bat`** to open the GUI. Pick a shop, type an item,
click **Check Price**, and see the top matches. First time for a shop, click
**Log in** to do the one-time manual sign-in.

### Command line

```powershell
# One-time per shop: log in manually; saves the session
python login.py --shop amazon

# Then: check a price (session is reused, no password needed)
python price_check.py "wireless mouse"
python price_check.py "wireless mouse" --shop amazon --top 5
python price_check.py "wireless mouse" --json       # machine-readable
python price_check.py --url "https://www.amazon.com/dp/B0XXXXXXX"
python price_check.py --list-shops                  # show available shops
```

If a check later says the session is invalid/expired, just re-run
`python login.py --shop <name>`.

> Reminder: always use the existing `.venv` (activate it); don't recreate it.

## Files

| File / dir        | Purpose                                            |
| ----------------- | -------------------------------------------------- |
| `shopagent/`      | Reusable core package (models, shops, agent).      |
| `login.py`        | One-time manual login per shop; saves the session. |
| `price_check.py`  | CLI: search/read a product and report its price.   |
| `gui.py`          | Desktop GUI (Tkinter) with a shop dropdown.        |
| `Price Checker.bat` | Double-click launcher for the GUI.               |
| `.env.example`    | Template config — copy to `.env`. No secrets.      |
| `.gitignore`      | Keeps secrets, sessions, logs out of git.          |
| `CLAUDE.md`       | Project instructions, security & workflow rules.   |
