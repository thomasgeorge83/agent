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


def _require_session(session_name: str) -> None:
    if not has_session(session_name):
        raise SessionExpired(
            f"No saved session for '{session_name}'. Log in to it first."
        )


def login(shop_name: str, headless: bool = False) -> bool:
    """Open a browser for a one-time manual login; save the session on success.

    Returns True if a signed-in session was saved. No password is stored — only
    the resulting cookies/local storage. The session is saved under the shop's
    ``session_name`` (shops can share one login).
    """
    shop = get_shop(shop_name)
    with browser_page(shop.session_name, headless=headless, use_session=False) as (page, context):
        page.goto(shop.base_url, wait_until="domcontentloaded")
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
    _require_session(shop.session_name)
    with browser_page(shop.session_name, headless=headless) as (page, _context):
        return shop.search(page, query, top)


def get_product(shop_name: str, url: str, headless: bool = False) -> Optional[Product]:
    shop = get_shop(shop_name)
    _require_session(shop.session_name)
    with browser_page(shop.session_name, headless=headless) as (page, _context):
        return shop.get_product(page, url)


def add_to_cart(shop_name: str, url: str, *, confirm: bool = False,
                headless: bool = False) -> CartReview:
    """Add a product to the cart and read it back. Never places an order.

    Requires ``confirm=True``. Uses a visible browser by default so you can see
    exactly what happens.
    """
    shop = get_shop(shop_name)
    _require_session(shop.session_name)
    with browser_page(shop.session_name, headless=headless) as (page, _context):
        return shop.add_to_cart(page, url, confirm=confirm)


def review_cart(shop_name: str, headless: bool = False) -> CartReview:
    shop = get_shop(shop_name)
    _require_session(shop.session_name)
    with browser_page(shop.session_name, headless=headless) as (page, _context):
        return shop.review_cart(page)
