"""Flipkart shop implementation.

Flipkart's CSS class names are hashed and change often, so this relies on
stable structure instead: result cards are ``div[data-id]``, the product link
is ``a[href*="/p/"]``, the clean product title is the image's ``alt`` attribute,
and the price is the first ``₹`` amount in the card text.

Search works without logging in; a saved session is still used (and required by
the orchestration layer) so logged-in pricing/availability is reflected.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from playwright.sync_api import TimeoutError as PWTimeout

from ..errors import BlockedBySite
from ..models import Product
from .base import Shop
from .registry import register_shop

_PRICE_RE = re.compile(r"₹[\d,]+")
_RATING_RE = re.compile(r"(\d\.\d)\s*\(([\d,]+)\)")


@register_shop
class FlipkartShop(Shop):
    name = "flipkart"
    label = "Flipkart"
    hidden = True  # regular Flipkart kept working but hidden; UI uses Flipkart Minutes
    base_url = os.environ.get("FLIPKART_URL", "https://www.flipkart.com").rstrip("/")
    requires_login = False  # Flipkart search/pricing is public; login is optional

    def is_logged_in(self, page) -> bool:
        # Flipkart shows the account name in the top nav once signed in; when
        # logged out that area says "Login".
        try:
            nav = (self.text_or_none(page.locator("a._3R5DXk, a[href*='/account']"))
                   or self.text_or_none(page.locator("div._1psGvi"))
                   or "")
            return bool(nav) and "login" not in nav.lower()
        except Exception:
            return False

    def check_blocked(self, page) -> None:
        url = page.url.lower()
        if "captcha" in url or "/sorry" in url:
            raise BlockedBySite("Flipkart served a robot check. Try again later.")

    def _dismiss_login_popup(self, page) -> None:
        """Close the login modal Flipkart overlays on first visit, if present."""
        for sel in ("button:has-text('✕')", "button._2KpZ6l._2doB4z", "span._30XB9F"):
            btn = page.locator(sel)
            if btn.count():
                try:
                    btn.first.click(timeout=2000)
                    return
                except Exception:
                    continue

    def _price_from(self, text: str) -> Optional[str]:
        m = _PRICE_RE.search(text or "")
        return m.group(0) if m else None

    def _rating_from(self, text: str) -> Optional[str]:
        m = _RATING_RE.search(text or "")
        return f"{m.group(1)} ({m.group(2)} ratings)" if m else None

    def search(self, page, query: str, top: int) -> list[Product]:
        url = f"{self.base_url}/search?q={query.replace(' ', '%20')}"
        page.goto(url, wait_until="domcontentloaded")
        self.check_blocked(page)
        self.be_polite()
        self._dismiss_login_popup(page)

        try:
            page.wait_for_selector("div[data-id]", timeout=15000)
        except PWTimeout:
            self.check_blocked(page)
            return []

        cards = page.locator("div[data-id]")
        out: list[Product] = []
        for i in range(cards.count()):
            if len(out) >= top:
                break
            c = cards.nth(i)
            link = c.locator("a[href*='/p/']")
            if not link.count():
                continue
            href = self.attr_or_none(link, "href")
            url_abs = self.abs_url(href)
            # The image alt holds a clean product title; fall back to link text.
            img = c.locator("img")
            title = (self.attr_or_none(img, "alt")
                     or self.text_or_none(link))
            if not title:
                continue
            card_text = c.inner_text() or ""
            price = self._price_from(card_text)
            if not price:
                continue  # skip cards without a clear price (ads, etc.)
            rating = self._rating_from(card_text)
            image_url = self.attr_or_none(img, "src")
            out.append(Product(title=title.strip(), price=price, rating=rating,
                               url=url_abs, shop=self.name, image_url=image_url))
        return out

    def get_product(self, page, url: str) -> Optional[Product]:
        page.goto(url, wait_until="domcontentloaded")
        self.check_blocked(page)
        self.be_polite()
        self._dismiss_login_popup(page)
        title = self.text_or_none(page.locator("span.VU-ZEz, span.B_NuCI, h1"))
        if not title:
            return None
        body = page.locator("body").inner_text() or ""
        price = self._price_from(body)
        rating = self._rating_from(body)
        image_url = self.attr_or_none(page.locator("img._396cs4, img._53J4C-, img.DByuf4"), "src")
        return Product(title=title.strip(), price=price, rating=rating,
                       url=url.split("?")[0], shop=self.name, image_url=image_url)
