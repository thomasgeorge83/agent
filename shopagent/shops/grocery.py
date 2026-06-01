"""Quick-commerce / grocery shops: Flipkart Minutes and BigBasket.

Both are heavily **delivery-location gated**: without a serviceable pincode set
on a logged-in session they show a "select location / not available" wall and no
products. These implementations therefore:

* require login (so your serviceable address is applied),
* detect the location wall and raise a clear ``BlockedBySite`` message,
* extract products using stable structure where possible.

NOTE: the exact product-card selectors below are best-effort — they could not be
validated against live results because the stores showed no products without a
serviceable location. They are isolated in ``_parse_results`` so they can be
confirmed/adjusted in one place once the store loads for your account.
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

_PRICE_RE = re.compile(r"₹\s?[\d,]+")
_LOCATION_WALL = ("select city", "verify delivery", "only available in selected",
                  "enter pincode", "please enter pincode", "select your location",
                  "choose location")


class _GroceryShop(Shop):
    """Shared helpers for location-gated grocery storefronts."""

    requires_login = True

    def is_logged_in(self, page) -> bool:
        # Best-effort: these apps show account/profile affordances once signed in.
        body = (self.text_or_none(page.locator("body")) or "").lower()
        return "login" not in body[:400]

    def _assert_serviceable(self, page) -> None:
        body = (self.text_or_none(page.locator("body")) or "").lower()
        if any(w in body for w in _LOCATION_WALL):
            raise BlockedBySite(
                f"{self.label} needs a serviceable delivery location. Log in and "
                "set a deliverable address/pincode, then try again."
            )

    def _price_from(self, text: str) -> Optional[str]:
        m = _PRICE_RE.search(text or "")
        return m.group(0).replace(" ", "") if m else None


@register_shop
class FlipkartMinutesShop(_GroceryShop):
    """Flipkart Minutes — Flipkart's quick grocery delivery."""

    name = "flipkart-minutes"
    label = "Flipkart Minutes"
    base_url = os.environ.get("FLIPKART_URL", "https://www.flipkart.com").rstrip("/")
    # Flipkart's grocery results come through the GROCERY marketplace filter.
    search_path = "/search?marketplace=GROCERY&q="

    def check_blocked(self, page) -> None:
        if "captcha" in page.url.lower():
            raise BlockedBySite("Flipkart served a robot check. Try again later.")

    def search(self, page, query: str, top: int) -> list[Product]:
        url = f"{self.base_url}{self.search_path}{query.replace(' ', '%20')}"
        page.goto(url, wait_until="domcontentloaded")
        self.check_blocked(page)
        page.wait_for_timeout(4000)
        self._assert_serviceable(page)
        return self._parse_results(page, top)

    def _parse_results(self, page, top: int) -> list[Product]:
        # Flipkart grocery reuses div[data-id] cards like the main site.
        try:
            page.wait_for_selector("div[data-id]", timeout=10000)
        except PWTimeout:
            return []
        cards = page.locator("div[data-id]")
        out: list[Product] = []
        for i in range(cards.count()):
            if len(out) >= top:
                break
            c = cards.nth(i)
            img = c.locator("img")
            link = c.locator("a[href*='/p/']")
            title = self.attr_or_none(img, "alt") or self.text_or_none(link)
            if not title:
                continue
            price = self._price_from(c.inner_text() or "")
            if not price:
                continue
            out.append(Product(
                title=title.strip(), price=price, rating=None,
                url=self.abs_url(self.attr_or_none(link, "href")),
                shop=self.name, image_url=self.attr_or_none(img, "src"),
            ))
        return out


@register_shop
class BigBasketShop(_GroceryShop):
    """BigBasket — online grocery."""

    name = "bigbasket"
    label = "BigBasket"
    base_url = os.environ.get("BIGBASKET_URL", "https://www.bigbasket.com").rstrip("/")
    search_path = "/ps/?q="

    def check_blocked(self, page) -> None:
        if "captcha" in page.url.lower():
            raise BlockedBySite("BigBasket served a robot check. Try again later.")

    def search(self, page, query: str, top: int) -> list[Product]:
        url = f"{self.base_url}{self.search_path}{query.replace(' ', '%20')}"
        page.goto(url, wait_until="domcontentloaded")
        self.check_blocked(page)
        page.wait_for_timeout(5000)
        self._assert_serviceable(page)
        return self._parse_results(page, top)

    def _parse_results(self, page, top: int) -> list[Product]:
        # BigBasket product pages are under /pd/; cards link there. Selectors are
        # best-effort pending a live, serviceable session to confirm.
        anchors = page.locator("a[href*='/pd/']")
        out: list[Product] = []
        seen: set[str] = set()
        for i in range(anchors.count()):
            if len(out) >= top:
                break
            a = anchors.nth(i)
            href = self.attr_or_none(a, "href") or ""
            if href in seen:
                continue
            seen.add(href)
            text = a.inner_text() or ""
            title = (text.split("\n")[0] or "").strip() or self.attr_or_none(a.locator("img"), "alt")
            if not title:
                continue
            price = self._price_from(text)
            if not price:
                continue
            out.append(Product(
                title=title.strip(), price=price, rating=None,
                url=self.abs_url(href), shop=self.name,
                image_url=self.attr_or_none(a.locator("img"), "src"),
            ))
        return out
