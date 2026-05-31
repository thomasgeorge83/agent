"""Amazon price-checker agent.

Uses the saved browser session from login.py (no password is used or stored) to
search your Amazon account for an item and report the price, title, rating, and
link of the top matches. You can also check a single product page by URL.

Account/personal data is never printed or logged.

Usage:
    python price_check.py "logitech mouse"
    python price_check.py "logitech mouse" --top 5
    python price_check.py "logitech mouse" --json
    python price_check.py --url "https://www.amazon.com/dp/B0XXXXXXX"
    python price_check.py "logitech mouse" --headless

If a search reports the session is invalid/expired, re-run:  python login.py
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

load_dotenv()

AMAZON_URL = os.environ.get("AMAZON_URL", "https://www.amazon.com").rstrip("/")
AUTH_FILE = "auth_state.json"
# Be polite: small pause between page actions so we don't hammer the site.
ACTION_DELAY_SECONDS = 1.0


@dataclass
class Product:
    title: str
    price: Optional[str]
    rating: Optional[str]
    url: Optional[str]


class SessionExpired(Exception):
    """The saved session is no longer logged in."""


class BlockedByAmazon(Exception):
    """Amazon served a CAPTCHA / robot check instead of content."""


def _abs_url(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    if href.startswith("http"):
        return href.split("?")[0]
    return f"{AMAZON_URL}{href.split('?')[0]}"


def _check_not_blocked(page) -> None:
    """Detect Amazon's bot/CAPTCHA wall and a logged-out session."""
    body = (page.locator("body").inner_text(timeout=5000) or "").lower()
    if "enter the characters you see" in body or "type the characters" in body \
            or "/errors/validatecaptcha" in page.url.lower():
        raise BlockedByAmazon(
            "Amazon showed a CAPTCHA / robot check. Try again later, run with "
            "--headless removed (visible browser), or re-run login.py."
        )
    if "/ap/signin" in page.url.lower() or "sign in" in body[:400] and "hello," not in body:
        # Heuristic: a search/product page should not redirect to sign-in.
        if "/ap/signin" in page.url.lower():
            raise SessionExpired("Session expired. Re-run: python login.py")


def _text_or_none(locator) -> Optional[str]:
    try:
        if locator.count():
            t = locator.first.inner_text(timeout=2000).strip()
            return t or None
    except PWTimeout:
        return None
    return None


def _attr_or_none(locator, name: str) -> Optional[str]:
    try:
        if locator.count():
            return locator.first.get_attribute(name, timeout=2000)
    except PWTimeout:
        return None
    return None


def search_products(page, query: str, top: int) -> list[Product]:
    page.goto(AMAZON_URL, wait_until="domcontentloaded")
    _check_not_blocked(page)
    time.sleep(ACTION_DELAY_SECONDS)

    page.fill("#twotabsearchtextbox", query)
    page.press("#twotabsearchtextbox", "Enter")
    try:
        page.wait_for_selector('[data-component-type="s-search-result"]', timeout=15000)
    except PWTimeout:
        _check_not_blocked(page)  # may raise a clearer error
        return []
    _check_not_blocked(page)

    results = page.locator('[data-component-type="s-search-result"]')
    out: list[Product] = []
    count = min(results.count(), top)
    for i in range(count):
        r = results.nth(i)
        title = _text_or_none(r.locator("h2"))
        if not title:
            continue
        price = _text_or_none(r.locator(".a-price .a-offscreen"))
        rating = _text_or_none(r.locator(".a-icon-alt"))
        url = _abs_url(_attr_or_none(r.locator("h2 a"), "href")
                       or _attr_or_none(r.locator("a.a-link-normal"), "href"))
        out.append(Product(title=title, price=price, rating=rating, url=url))
    return out


def product_from_url(page, url: str) -> Optional[Product]:
    page.goto(url, wait_until="domcontentloaded")
    _check_not_blocked(page)
    time.sleep(ACTION_DELAY_SECONDS)
    title = _text_or_none(page.locator("#productTitle")) or _text_or_none(page.locator("h1"))
    if not title:
        return None
    price = (_text_or_none(page.locator(".a-price .a-offscreen"))
             or _text_or_none(page.locator("#corePrice_feature_div .a-offscreen")))
    rating = _text_or_none(page.locator('#acrPopover .a-icon-alt')) \
        or _text_or_none(page.locator(".a-icon-alt"))
    return Product(title=title, price=price, rating=rating, url=url.split("?")[0])


def run(query: Optional[str], url: Optional[str], top: int, headless: bool) -> list[Product]:
    if not os.path.exists(AUTH_FILE):
        sys.exit(f"No session found ({AUTH_FILE}). Run `python login.py` first.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        try:
            if url:
                product = product_from_url(page, url)
                return [product] if product else []
            return search_products(page, query, top)
        finally:
            browser.close()


def render_text(products: list[Product], label: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if not products:
        return f"No results for {label!r} (checked {stamp})."
    lines = [f"Price check for {label!r} — {stamp}", "-" * 56]
    for i, prod in enumerate(products, 1):
        title = (prod.title[:70] + "…") if len(prod.title) > 71 else prod.title
        lines.append(f"{i}. {title}")
        lines.append(f"   Price : {prod.price or 'not shown'}")
        if prod.rating:
            lines.append(f"   Rating: {prod.rating}")
        if prod.url:
            lines.append(f"   Link  : {prod.url}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Amazon item prices using your saved session.")
    parser.add_argument("query", nargs="?", help="Item to search for, e.g. \"logitech mouse\".")
    parser.add_argument("--url", help="Check a specific product page by URL instead of searching.")
    parser.add_argument("--top", type=int, default=3, help="How many search results to show (default 3).")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text.")
    parser.add_argument("--headless", action="store_true",
                        help="Run without a visible browser (may trigger bot checks more often).")
    args = parser.parse_args()

    if not args.query and not args.url:
        args.query = os.environ.get("SEARCH_QUERY")
    if not args.query and not args.url:
        parser.error("provide an item to search for, or --url for a specific product.")

    try:
        products = run(args.query, args.url, args.top, args.headless)
    except SessionExpired as exc:
        sys.exit(str(exc))
    except BlockedByAmazon as exc:
        sys.exit(str(exc))

    label = args.url or args.query
    if args.json:
        print(json.dumps([asdict(p) for p in products], indent=2, ensure_ascii=False))
    else:
        print(render_text(products, label))


if __name__ == "__main__":
    main()
