"""Orchestration: tie a Shop together with a browser session.

These functions are what the CLI and GUI call. They resolve a shop by name,
open a browser with that shop's saved session, and run an action — translating
low-level Playwright issues into the shared error types.
"""

from __future__ import annotations

import time
from typing import List, Optional

from .errors import SessionExpired
from .models import CartReview, Product
from .session import browser_page, has_session, session_path
from .shops import get_shop

# How long to wait for a manual sign-in before giving up.
LOGIN_TIMEOUT_SECONDS = 5 * 60
LOGIN_POLL_SECONDS = 2


def shop_has_session(shop_name: str) -> bool:
    """True if the (possibly shared) session for this shop exists."""
    return has_session(get_shop(shop_name).session_name)


def _require_session(shop) -> None:
    """Ensure a session exists, unless the shop allows login-free searching."""
    if shop.requires_login and not has_session(shop.session_name):
        raise SessionExpired(
            f"No saved session for '{shop.label or shop.name}'. Log in to it first."
        )


def login(shop_name: str, headless: bool = False, wait_for_user=None) -> bool:
    """Open a browser for a one-time manual login; save the session on success.

    No password is stored — only the resulting cookies/local storage, saved under
    the shop's ``session_name`` (shops can share one login).

    Two completion modes:
    * Shops with reliable ``is_logged_in`` (``auto_login_detection`` True, e.g.
      Amazon) save automatically once sign-in is detected.
    * Otherwise (e.g. Flipkart, grocery apps) we cannot reliably detect sign-in,
      so we wait for the user to confirm. ``wait_for_user`` is a blocking
      callable (e.g. ``input``) that returns when the user is done; the session
      is then saved regardless of detection. This avoids closing the browser
      mid-login. Returns True if a session was saved.
    """
    shop = get_shop(shop_name)
    with browser_page(shop.session_name, headless=headless, use_session=False,
                       mobile=shop.mobile) as (page, context):
        page.goto(shop.base_url, wait_until="domcontentloaded")

        if not shop.auto_login_detection:
            # User-confirmed flow. Block until they signal completion, then save
            # whatever session the browser now holds.
            if wait_for_user is not None:
                wait_for_user()
            else:
                # No way to ask the user (e.g. headless/automated) — fall back to
                # a bounded wait so we don't hang forever.
                time.sleep(min(LOGIN_TIMEOUT_SECONDS, 60))
            context.storage_state(path=session_path(shop.session_name))
            return True

        deadline = time.time() + LOGIN_TIMEOUT_SECONDS
        confirmed = 0
        while time.time() < deadline:
            try:
                if shop.is_logged_in(page):
                    confirmed += 1
                    if confirmed >= 2:  # two consecutive checks = stable
                        context.storage_state(path=session_path(shop.session_name))
                        return True
                else:
                    confirmed = 0
            except Exception:
                confirmed = 0
            time.sleep(LOGIN_POLL_SECONDS)
    return False


def search(shop_name: str, query: str, top: int = 3, headless: bool = False) -> List[Product]:
    shop = get_shop(shop_name)
    _require_session(shop)
    with browser_page(shop.session_name, headless=headless, mobile=shop.mobile) as (page, _context):
        return shop.search(page, query, top)


def compare(query: str, shop_names: List[str], top: int = 1,
            headless: bool = False) -> "dict[str, dict]":
    """Search the same query across several shops for side-by-side comparison.

    Returns ``{shop_name: {"label", "products", "error"}}``. A shop that has no
    session or errors out is reported via its ``error`` field rather than
    aborting the whole comparison, so the UI can still show the others.
    """
    results: dict[str, dict] = {}
    for name in shop_names:
        entry: dict = {"label": name, "products": [], "error": None}
        try:
            shop = get_shop(name)
            entry["label"] = shop.label or name
            if shop.requires_login and not has_session(shop.session_name):
                entry["error"] = f"Not logged in. Log in to {entry['label']} first."
            else:
                with browser_page(shop.session_name, headless=headless,
                                  mobile=shop.mobile) as (page, _ctx):
                    entry["products"] = shop.search(page, query, top)
        except SessionExpired as exc:
            entry["error"] = str(exc)
        except Exception as exc:
            entry["error"] = str(exc)
        results[name] = entry
    return results


def get_product(shop_name: str, url: str, headless: bool = False) -> Optional[Product]:
    shop = get_shop(shop_name)
    _require_session(shop)
    with browser_page(shop.session_name, headless=headless, mobile=shop.mobile) as (page, _context):
        return shop.get_product(page, url)


def add_to_cart(shop_name: str, url: str, *, confirm: bool = False,
                headless: bool = False) -> CartReview:
    """Add a product to the cart and read it back. Never places an order.

    Requires ``confirm=True``. Uses a visible browser by default so you can see
    exactly what happens.
    """
    shop = get_shop(shop_name)
    _require_session(shop)
    with browser_page(shop.session_name, headless=headless, mobile=shop.mobile) as (page, _context):
        return shop.add_to_cart(page, url, confirm=confirm)


def review_cart(shop_name: str, headless: bool = False) -> CartReview:
    shop = get_shop(shop_name)
    _require_session(shop)
    with browser_page(shop.session_name, headless=headless, mobile=shop.mobile) as (page, _context):
        return shop.review_cart(page)
