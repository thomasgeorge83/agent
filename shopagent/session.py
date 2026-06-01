"""Per-shop session storage and browser lifecycle.

Each shop gets its own session file: ``auth_state.<shop>.json`` in the project
root. These files are secrets (they grant account access) and are git-ignored.
No password is ever stored — only the cookies/local storage of a manual login.
"""

import os
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

# Project root = parent of the shopagent package directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Be polite: small pause between page actions so we don't hammer a site.
ACTION_DELAY_SECONDS = 1.0


def session_path(shop_name: str) -> str:
    """Absolute path to the session file for a given shop."""
    safe = "".join(c for c in shop_name.lower() if c.isalnum() or c in "-_")
    return os.path.join(ROOT, f"auth_state.{safe}.json")


def has_session(shop_name: str) -> bool:
    return os.path.exists(session_path(shop_name))


@contextmanager
def browser_page(shop_name: str, headless: bool, use_session: bool = True):
    """Yield a Playwright page, loading the shop's saved session if present.

    Always closes the browser on exit. When ``use_session`` is False (used by
    the login flow), starts a clean context so the user can sign in fresh.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        kwargs = {}
        path = session_path(shop_name)
        if use_session and os.path.exists(path):
            kwargs["storage_state"] = path
        context = browser.new_context(**kwargs)
        page = context.new_page()
        try:
            yield page, context
        finally:
            browser.close()
