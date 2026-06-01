# Shop Agent (learning project)

A modular browser-automation toolkit (Python + Playwright) that signs in to
**your own** online-shop accounts and works with them — currently searching and
checking prices, with order actions stubbed out for future work. The design
makes adding more shops a one-file job.

Shops available: **Amazon**, **Amazon Fresh** (groceries), **Amazon Now**
(quick-commerce), and **Flipkart**. Fresh and Now reuse your regular Amazon
login (no second sign-in) and are **delivery-location gated**. Flipkart's search
is public, so price-checking it needs no login.

**Log in to All:** the GUI's *Log in to All* button signs you in to every
platform that needs a login, one at a time (a browser opens for each; it saves
automatically). Shops sharing a login (Amazon/Fresh/Now) are done once, and
login-free shops (Flipkart) are skipped.

**Compare All:** the *Compare All* button searches the same item across the
general-catalog platforms (Amazon, Flipkart, …) and shows the results **side by
side**, one column per platform, each with image, price and rating.

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

**Cart actions** (`add_to_cart`, `review_cart`) add an item to your cart and read
it back, but **stop at the cart — they never check out**. `add_to_cart` requires
`confirm=True`. **Order actions** (`place_order`, `modify_order`, `cancel_order`)
are defined on the base class but **refuse by default** (`ActionNotSupported`).
Nothing in this project places an order or spends money.

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
click **Check Price**, and browse the matches as cards with a **thumbnail**,
price and rating. Click **Details** on a card for a larger image and the
product's feature bullets, or **Open in browser** to view the listing. First
time for a shop, click **Log in** to do the one-time manual sign-in.

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

# Cart (NEVER places an order; stops at the cart for you to review)
python cart.py review
python cart.py add --url "https://www.amazon.com/dp/B0XXXXXXX" --confirm
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
| `cart.py`         | CLI: add to cart / review cart (never orders).     |
| `gui.py`          | Desktop GUI (Tkinter): cards, thumbnails, details. |
| `Price Checker.bat` | Double-click launcher for the GUI.               |
| `.env.example`    | Template config — copy to `.env`. No secrets.      |
| `.gitignore`      | Keeps secrets, sessions, logs out of git.          |
| `CLAUDE.md`       | Project instructions, security & workflow rules.   |
