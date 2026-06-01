"""Amazon shop implementation.

Ports the read-only search/price logic that was validated against live Amazon.
Order actions are intentionally left as the base-class refusals for now.
"""

from __future__ import annotations

import os
from typing import Optional

from playwright.sync_api import TimeoutError as PWTimeout

from ..errors import BlockedBySite, SessionExpired
from ..models import Product
from .base import Shop
from .registry import register_shop


@register_shop
class AmazonShop(Shop):
    name = "amazon"
    label = "Amazon"
    base_url = os.environ.get("AMAZON_URL", "https://www.amazon.com").rstrip("/")

    def is_logged_in(self, page) -> bool:
        for selector in ("#nav-link-accountList-nav-line-1", "#nav-link-accountList"):
            try:
                el = page.locator(selector)
                if el.count():
                    txt = (el.first.inner_text(timeout=1000) or "").strip().lower()
                    if txt and "sign in" not in txt:
                        return True
            except Exception:
                continue
        return False

    def check_blocked(self, page) -> None:
        body = (page.locator("body").inner_text(timeout=5000) or "").lower()
        url = page.url.lower()
        if ("enter the characters you see" in body
                or "type the characters" in body
                or "/errors/validatecaptcha" in url):
            raise BlockedBySite(
                "Amazon showed a CAPTCHA / robot check. Try again later, run "
                "with a visible browser, or log in again."
            )
        if "/ap/signin" in url:
            raise SessionExpired("Amazon session expired. Log in again.")

    def _price(self, scope) -> Optional[str]:
        """Extract a price within ``scope`` (a search card or product page).

        Amazon renders the canonical price in ``.a-offscreen`` (visually hidden),
        which inner_text cannot read — so read its text_content first, then fall
        back to assembling the visible whole+fraction parts.
        """
        price = self.text_content_or_none(scope.locator(".a-price .a-offscreen").first)
        if price:
            return price
        whole = self.text_or_none(scope.locator(".a-price-whole").first)
        if whole:
            frac = self.text_or_none(scope.locator(".a-price-fraction").first)
            symbol = self.text_or_none(scope.locator(".a-price-symbol").first) or "$"
            whole = whole.replace(".", "").replace(",", "").strip()
            return f"{symbol}{whole}.{frac}" if frac else f"{symbol}{whole}"
        return None

    def _title(self, card) -> Optional[str]:
        """Pick the product title from a result card.

        A card can hold several h2 elements (brand line + product line); the
        product name is the longest, so prefer that over the short brand label.
        """
        h2 = card.locator("h2")
        best = None
        for i in range(h2.count()):
            txt = (self.text_content_or_none(h2.nth(i)) or "").strip()
            if txt and (best is None or len(txt) > len(best)):
                best = txt
        return best

    def search(self, page, query: str, top: int) -> list[Product]:
        page.goto(self.base_url, wait_until="domcontentloaded")
        self.check_blocked(page)
        self.be_polite()

        page.fill("#twotabsearchtextbox", query)
        page.press("#twotabsearchtextbox", "Enter")
        try:
            page.wait_for_selector('[data-component-type="s-search-result"]', timeout=15000)
        except PWTimeout:
            self.check_blocked(page)  # may raise a clearer error
            return []
        self.check_blocked(page)

        results = page.locator('[data-component-type="s-search-result"]')
        out: list[Product] = []
        count = min(results.count(), top)
        for i in range(count):
            r = results.nth(i)
            title = self._title(r)
            if not title:
                continue
            price = self._price(r)
            if not price and "see options" in (r.inner_text() or "").lower():
                price = "multiple options — open link"
            rating = self.text_or_none(r.locator(".a-icon-alt"))
            url = self.abs_url(self.attr_or_none(r.locator("h2 a"), "href")
                               or self.attr_or_none(r.locator("a.a-link-normal"), "href"))
            out.append(Product(title=title, price=price, rating=rating, url=url, shop=self.name))
        return out

    def get_product(self, page, url: str) -> Optional[Product]:
        page.goto(url, wait_until="domcontentloaded")
        self.check_blocked(page)
        self.be_polite()
        title = self.text_or_none(page.locator("#productTitle")) \
            or self.text_or_none(page.locator("h1"))
        if not title:
            return None
        price = (self._price(page.locator("#corePrice_feature_div").first)
                 or self._price(page))
        rating = self.text_or_none(page.locator("#acrPopover .a-icon-alt")) \
            or self.text_or_none(page.locator(".a-icon-alt"))
        return Product(title=title, price=price, rating=rating,
                       url=url.split("?")[0], shop=self.name)
