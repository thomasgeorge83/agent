# Project Instructions

These rules apply to ALL code and tooling created in this repository. Follow them
without being asked.

## 1. Source control — push to GitHub

- This project is version-controlled with Git and pushed to the user's GitHub account.
- After a meaningful unit of work is created or changed, commit it with a clear
  message and push to the GitHub remote (`origin`).
- **Never push until you have confirmed no secrets or personal data are included**
  in the commit (see Section 2 & 3). Run a secret check before every push.
- Do not force-push to shared branches or rewrite published history unless the
  user explicitly asks.
- Do not skip hooks (`--no-verify`) or signing.

## 2. No credentials in code — ever

- **Never** hard-code usernames, passwords, API keys, tokens, OTP secrets, or
  cookies in source files, tests, comments, or commit messages.
- Read all secrets at runtime from environment variables or a local `.env` file
  that is **git-ignored**, or from the OS keychain / a secrets manager.
- Commit a `.env.example` with placeholder keys only (no real values).
- Prefer reusing an authenticated browser **session/cookie file** (created by a
  one-time manual login) over automating password entry. The session file is a
  secret too — it must be git-ignored and never logged.

## 3. Security & privacy first

- Treat security as a blocking requirement, not an afterthought. If a step would
  create a vulnerability or leak data, stop and flag it.
- Never log, print, or write to disk any personal data (names, addresses, emails,
  order history, payment info) or secrets. Redact before logging.
- Pin/review any third-party dependency or browser extension before adding it.
  Prefer well-maintained, widely-used packages; avoid abandoned or obscure ones.
- Keep dependencies updated; run an audit (`pip-audit`, `npm audit`) and fix
  high/critical issues.
- Respect the target site's Terms of Service and `robots.txt`. Automate only the
  user's own account, with their authorization. Use conservative rate limits.
- Least privilege: request only the access the task needs. No telemetry that
  sends data to third parties.
- `.gitignore` must cover `.env`, session/cookie files, browser profiles, logs,
  screenshots, and any data dumps.

## 4. Before every commit — checklist

1. `git diff --staged` reviewed for secrets and personal data.
2. `.env`, session files, profiles, logs are git-ignored (not staged).
3. Dependency audit clean (or known issues documented).
4. Clear commit message describing the change.
