"""The Shop extension point.

To support a new online shop, subclass ``Shop``, set ``name``/``base_url``,
implement ``is_logged_in`` and ``search`` (and ``get_product`` if the site has
product pages), then register it (see ``shopagent.shops.registry``).

State-changing actions — ``place_order``, ``modify_order``, ``cancel_order`` —
default to raising ``ActionNotSupported``. Override them only when you have
implemented and tested them for that shop. They take an explicit ``confirm``
flag and must refuse unless it is True, because they spend real money.
"""

from __future__ import annotations

import time
from typing import Optional

from playwright.sync_api import TimeoutError as PWTimeout

from ..errors import ActionNotSupported
from ..models import CartReview, OrderResult, Product
from ..session import ACTION_DELAY_SECONDS


class Shop:
    #: Short, unique, lowercase identifier (e.g. "amazon"). Used for CLI/GUI
    #: selection and, by default, for the session filename.
    name: str = ""
    #: Human-friendly label shown in the UI.
    label: str = ""
    #: Base URL, no trailing slash.
    base_url: str = ""
    #: Which saved session to use. Defaults to ``name``; set it to another
    #: shop's name to share one login across storefronts (e.g. Amazon Now
    #: reuses the "amazon" session). None = use ``name``.
    session_key: str = ""
    #: Whether this shop is a general catalog included in "Compare All".
    #: Sub-storefronts like Amazon Fresh/Now set this False so the comparison
    #: stays apples-to-apples across full-catalog platforms.
    comparable: bool = True
    #: Whether a saved login session is required to search. Some sites (e.g.
    #: Flipkart) expose public search, so price-checking works without login.
    requires_login: bool = True
    #: Hidden shops stay registered (and usable by name) but are left out of the
    #: UI/CLI shop lists. Lets us keep working code without showing it.
    hidden: bool = False
    #: Whether ``is_logged_in`` reliably detects a completed sign-in. When False,
    #: the login flow waits for the user to confirm (press Enter) instead of
    #: auto-detecting, so the browser is never closed mid-login.
    auto_login_detection: bool = True

    @property
    def session_name(self) -> str:
        return self.session_key or self.name

    # ---- small shared helpers (used by subclasses) ---------------------
    @staticmethod
    def text_or_none(locator) -> Optional[str]:
        try:
            if locator.count():
                t = (locator.first.inner_text(timeout=2000) or "").strip()
                return t or None
        except PWTimeout:
            return None
        return None

    @staticmethod
    def text_content_or_none(locator) -> Optional[str]:
        """Like text_or_none but reads text even when it is visually hidden.

        Amazon's price is inside ``.a-offscreen`` (clipped off-screen), so
        ``inner_text`` returns "" for it — use ``text_content`` instead.
        """
        try:
            if locator.count():
                t = (locator.first.text_content(timeout=2000) or "").strip()
                return t or None
        except PWTimeout:
            return None
        return None

    @staticmethod
    def attr_or_none(locator, name: str) -> Optional[str]:
        try:
            if locator.count():
                return locator.first.get_attribute(name, timeout=2000)
        except PWTimeout:
            return None
        return None

    def abs_url(self, href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        if href.startswith("http"):
            return href.split("?")[0]
        return f"{self.base_url}{href.split('?')[0]}"

    @staticmethod
    def be_polite() -> None:
        time.sleep(ACTION_DELAY_SECONDS)

    # ---- required overrides --------------------------------------------
    def is_logged_in(self, page) -> bool:
        """Return True if the page shows a signed-in account."""
        raise NotImplementedError

    def check_blocked(self, page) -> None:
        """Raise BlockedBySite / SessionExpired if the page is a wall.

        Default: no-op. Override to detect CAPTCHAs and sign-in redirects.
        """
        return None

    def search(self, page, query: str, top: int) -> list[Product]:
        """Search the shop and return up to ``top`` products."""
        raise NotImplementedError

    # ---- optional overrides --------------------------------------------
    def get_product(self, page, url: str) -> Optional[Product]:
        """Return a single product from its page URL, or None."""
        raise ActionNotSupported(
            f"{self.label or self.name}: fetching a product by URL is not supported yet."
        )

    # ---- cart actions (no purchase; override to enable) ----------------
    def add_to_cart(self, page, url: str, *, confirm: bool = False, **kwargs) -> CartReview:
        """Add the product at ``url`` to the cart and read the cart back.

        This must NOT place an order — it stops at the cart. Implementations
        must refuse unless ``confirm`` is True.
        """
        raise ActionNotSupported(
            f"{self.label or self.name}: adding to cart is not implemented yet."
        )

    def review_cart(self, page) -> CartReview:
        """Read the current cart contents without changing anything."""
        raise ActionNotSupported(
            f"{self.label or self.name}: reviewing the cart is not implemented yet."
        )

    # ---- state-changing actions (guarded; override to enable) ----------
    def place_order(self, page, url: str, *, confirm: bool = False, **kwargs) -> OrderResult:
        # Intentionally NOT implemented. Placing an order spends real money and
        # is deliberately out of scope until explicitly built and confirmed.
        raise ActionNotSupported(
            f"{self.label or self.name}: placing orders is not implemented yet."
        )

    def modify_order(self, page, order_id: str, *, confirm: bool = False, **kwargs) -> OrderResult:
        raise ActionNotSupported(
            f"{self.label or self.name}: modifying orders is not implemented yet."
        )

    def cancel_order(self, page, order_id: str, *, confirm: bool = False, **kwargs) -> OrderResult:
        raise ActionNotSupported(
            f"{self.label or self.name}: cancelling orders is not implemented yet."
        )
