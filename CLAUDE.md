# Project Instructions — Amazon Search Agent

This is the authoritative instruction file for this project. Read it and follow
it on every session, without being asked.

---

## 1. Project overview

A learning **browser-automation agent** (Python + Playwright) that signs in to
the user's **own** Amazon account and searches for items.

- **Language / stack:** Python 3, [Playwright](https://playwright.dev/python/),
  `python-dotenv`.
- **Auth model:** manual login once → saved browser session reused by the agent.
  No password is ever typed by code or stored anywhere.
- **Key files:**
  - `login.py` — one-time manual login; writes the session to `auth_state.json`.
  - `search.py` — loads the session, confirms it's valid, runs a search (skeleton).
  - `.env.example` — config template (no secrets); copy to `.env`.
  - `requirements.txt` — pinned dependencies.
- **Roadmap:** Phase 0 project + safety rails ✅ · Phase 1 login skeleton ✅ ·
  Phase 2 verify session (user runs `login.py`/`search.py`) · Phase 3 real search
  agent (parse title/price/rating/URL, handle expired session & CAPTCHA, polite
  rate limits).

---

## 2. Python environment — use the EXISTING venv

- A virtual environment lives at **`.venv\`** in the project root.
- **Always activate and use the existing `.venv`. Do NOT recreate it** on each run
  or each session, and do not create a second environment.
- Activate before running anything:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  Or call the venv interpreter directly: `.\.venv\Scripts\python.exe script.py`.
- Only run `python -m venv .venv` if `.venv\` does not exist yet (first-time
  setup). After that, just activate it.
- Install/update packages **into the existing venv** (`pip install -r
  requirements.txt`); when adding a dependency, pin it and update
  `requirements.txt`.

---

## 3. Git & GitHub

- **Remote:** `origin` = https://github.com/thomasgeorge83/agent.git
- **Default branch:** `main`.
- **Git executable:** installed but not on PATH — invoke as
  `"C:\Program Files\Git\cmd\git.exe"` (or after a terminal restart, plain `git`).
- After a meaningful unit of work, commit with a clear message and push to
  `origin main` — but only **after the secret check in Section 5 passes**.
- Do not force-push to `main` or rewrite published history unless explicitly asked.
- Do not skip hooks (`--no-verify`) or signing.

---

## 4. No credentials in code — ever

- **Never** hard-code usernames, passwords, API keys, tokens, OTP secrets, or
  cookies in source, tests, comments, or commit messages.
- Read all secrets at runtime from environment variables or the git-ignored
  `.env`, or from the OS keychain / a secrets manager.
- `.env.example` holds placeholder keys only — never real values.
- Prefer reusing the authenticated **session file** (`auth_state.json`) over
  automating password entry. That session file is a secret too: git-ignored,
  never logged, never committed.

---

## 5. Security & privacy first

- Treat security as a blocking requirement. If a step would create a vulnerability
  or leak data, stop and flag it.
- Never log, print, or save personal data (names, addresses, emails, order
  history, payment info) or secrets. Redact before logging.
- Review any third-party dependency or browser extension before adding it. Prefer
  well-maintained, widely-used packages. Run `pip-audit` and fix high/critical issues.
- Respect Amazon's Terms of Service and `robots.txt`. Automate only the user's own
  account, with their authorization. Use conservative rate limits.
- Least privilege; no telemetry to third parties.
- `.gitignore` must keep out: `.env`, `auth_state.json`/session & cookie files,
  browser profiles, `.vs/` and other IDE folders, logs, screenshots, data dumps.

### Secret check — run before EVERY commit/push
1. `git diff --cached --name-only` — confirm no `.env`, `auth_state.json`,
   session/cookie files, `.vs/`, logs, or data dumps are staged.
2. `git diff --cached` — scan the diff for any secret or personal data.
3. Dependency audit clean (or known issues documented).
4. Clear commit message describing the change.
