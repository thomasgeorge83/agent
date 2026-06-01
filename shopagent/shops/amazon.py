"""Amazon shop implementation.

Ports the read-only search/price logic that was validated against live Amazon.
Order actions are intentionally left as the base-class refusals for now.
"""

from __future__ import annotations

import os
from typing import Optional

from playwright.sync_api import TimeoutError as PWTimeout

from ..errors import ActionNotSupported, BlockedBySite, SessionExpired
from ..models import CartItem, CartReview, Product
from .base import Shop
from .registry import register_shop


@register_shop
class AmazonShop(Shop):
    name = "amazon"
    label = "Amazon"
    hidden = True  # kept working, but not shown in the UI (per current shop set)
    base_url = os.environ.get("AMAZON_URL", "https://www.amazon.com").rstrip("/")
    #: Where a search starts. Subclasses (e.g. Amazon Now) override this.
    search_url = base_url
    #: Search box selector used to type the query.
    search_box = "#twotabsearchtextbox"

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
        page.goto(self.search_url, wait_until="domcontentloaded")
        self.check_blocked(page)
        self.be_polite()

        page.fill(self.search_box, query)
        page.press(self.search_box, "Enter")
        try:
            page.wait_for_selector('[data-component-type="s-search-result"]', timeout=15000)
        except PWTimeout:
            self.check_blocked(page)  # may raise a clearer error
            return []
        self.check_blocked(page)

        results = page.locator('[data-component-type="s-search-result"]')
        out: list[Product] = []
        # Scan all result cards (not just the first `top`) so that skipping
        # multi-seller listings still lets us collect `top` priced products.
        for i in range(results.count()):
            if len(out) >= top:
                break
            r = results.nth(i)
            title = self._title(r)
            if not title:
                continue
            price = self._price(r)
            # Skip multi-seller "see options" listings that have no single price.
            if not price:
                continue
            rating = self.text_or_none(r.locator(".a-icon-alt"))
            url = self.abs_url(self.attr_or_none(r.locator("h2 a"), "href")
                               or self.attr_or_none(r.locator("a.a-link-normal"), "href"))
            image_url = self.attr_or_none(r.locator("img.s-image"), "src")
            out.append(Product(title=title, price=price, rating=rating, url=url,
                               shop=self.name, image_url=image_url))
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
        reviews_count = self.text_or_none(page.locator("#acrCustomerReviewText"))
        image_url = (self.attr_or_none(page.locator("#landingImage"), "src")
                     or self.attr_or_none(page.locator("#imgBlkFront"), "src")
                     or self.attr_or_none(page.locator("#main-image"), "src"))
        availability = self.text_or_none(page.locator("#availability"))
        features = []
        bullets = page.locator("#feature-bullets li span.a-list-item")
        for i in range(min(bullets.count(), 8)):
            txt = self.text_or_none(bullets.nth(i))
            if txt:
                features.append(txt)
        return Product(title=title, price=price, rating=rating,
                       url=url.split("?")[0], shop=self.name,
                       image_url=image_url, reviews_count=reviews_count,
                       features=features, availability=availability)

    # ---- cart actions (NO purchase) ------------------------------------
    CART_URL = "/gp/cart/view.html"

    def add_to_cart(self, page, url: str, *, confirm: bool = False, **kwargs) -> CartReview:
        """Add a product to the cart and read the cart back. Never checks out.

        Safety: this only ever visits the product page and the cart page. It
        never navigates to a /gp/buy/ checkout URL and never clicks "Place your
        order". Requires confirm=True.
        """
        if not confirm:
            raise ActionNotSupported(
                "add_to_cart requires confirm=True (a deliberate opt-in). "
                "It adds the item to your cart but never places an order."
            )

        page.goto(url, wait_until="domcontentloaded")
        self.check_blocked(page)
        self.be_polite()

        add_btn = page.locator("#add-to-cart-button")
        if not add_btn.count():
            raise ActionNotSupported(
                "Couldn't find an 'Add to Cart' button on this page. It may be a "
                "multi-seller listing or require choosing options first; open the "
                "link and pick options, then try a direct product URL."
            )
        add_btn.first.click()
        self.be_polite()

        # Some products show a "protection plan / add-on" interstitial — decline
        # it so we land in a clean state. Never confirm any upsell.
        for sel in ("#attachSiNoCoverage", "#siNoCoverage-announce",
                    "input[name='submit.attach-sidesheet-no-thanks-button']"):
            btn = page.locator(sel)
            if btn.count():
                try:
                    btn.first.click(timeout=2000)
                except Exception:
                    pass
                break

        return self.review_cart(page)

    def review_cart(self, page) -> CartReview:
        """Read cart contents. Read-only: changes nothing, places nothing."""
        page.goto(f"{self.base_url}{self.CART_URL}", wait_until="domcontentloaded")
        self.check_blocked(page)
        self.be_polite()

        rows = page.locator("[data-name='Active Items'] .sc-list-item, .sc-list-item")
        items: list[CartItem] = []
        for i in range(rows.count()):
            row = rows.nth(i)
            title = (self.text_or_none(row.locator(".sc-product-title"))
                     or self.text_content_or_none(row.locator(".a-truncate-full")))
            if not title:
                continue
            price = self._price(row)
            qty = self.attr_or_none(row.locator("input.sc-quantity-textfield"), "value") \
                or self.text_or_none(row.locator(".sc-quantity-textfield")) \
                or self.text_or_none(row.locator("[data-a-selector='value']"))
            items.append(CartItem(title=title.strip(), price=price, quantity=qty))

        subtotal = (self.text_content_or_none(page.locator("#sc-subtotal-amount-activecart .a-offscreen"))
                    or self.text_content_or_none(page.locator("#sc-subtotal-amount-buybox .a-offscreen")))
        count_txt = self.text_or_none(page.locator("#sc-subtotal-label-activecart")) or ""

        return CartReview(
            items=items,
            subtotal=subtotal,
            item_count=len(items),
            note="Item(s) are in your cart. No order has been placed.",
        )


@register_shop
class AmazonNowShop(AmazonShop):
    """Amazon Now — the fast/quick-commerce storefront.

    Reuses the regular Amazon login (``session_key = "amazon"``) and all of the
    AmazonShop parsing/cart logic; only the storefront entry point differs.
    Amazon Now is region-specific (primarily amazon.in); set AMAZON_NOW_URL in
    your .env to point at the right storefront for your account.
    """

    name = "amazon-now"
    label = "Amazon Now"
    hidden = True  # kept working, but not shown in the UI (per current shop set)
    session_key = "amazon"  # share the regular Amazon session — no second login
    comparable = False  # niche storefront; keep out of the Compare-All view
    base_url = os.environ.get("AMAZON_URL", "https://www.amazon.com").rstrip("/")
    search_url = os.environ.get("AMAZON_NOW_URL", f"{base_url}/now").rstrip("/")
    # Now is a single-page app with its own search box (no #twotabsearchtextbox).
    search_box = "input[aria-label='Search products']"

    def _dismiss_bottom_sheet(self, page) -> None:
        """Close the delivery-location pop-up that blocks interaction, if shown."""
        closer = page.locator("button[aria-label='Close bottom sheet']")
        if closer.count():
            try:
                closer.first.click(force=True, timeout=3000)
                page.wait_for_timeout(1000)
            except Exception:
                pass

    def _assert_available(self, page) -> None:
        """Raise a clear error if Now isn't serving this location.

        We read only the storefront status text — never the saved addresses or
        name that this page may also contain.
        """
        body = (self.text_or_none(page.locator("body")) or "").lower()
        if "not available in your area" in body or "store is temporarily unavailable" in body:
            raise BlockedBySite(
                "Amazon Now is not available at your delivery location "
                "(it is a hyperlocal service in select cities). Try regular "
                "Amazon, or set AMAZON_NOW_URL to a serviceable region."
            )

    def search(self, page, query: str, top: int) -> list[Product]:
        page.goto(self.search_url, wait_until="domcontentloaded")
        self.check_blocked(page)
        page.wait_for_timeout(2500)
        self._dismiss_bottom_sheet(page)
        self._assert_available(page)

        box = page.locator(self.search_box)
        if not box.count():
            raise BlockedBySite(
                "Couldn't find the Amazon Now search box — the storefront may "
                "be unavailable in your area or its layout changed."
            )
        box.first.fill(query)
        box.first.press("Enter")
        page.wait_for_timeout(4000)
        self._assert_available(page)
        # Product-card parsing for Now is not implemented: the store is
        # unavailable at this location, so it could not be validated against
        # real results. Once Now serves your area, add selectors here.
        return []


@register_shop
class AmazonFreshShop(AmazonShop):
    """Amazon Fresh — grocery storefront on the regular Amazon site.

    Fresh uses the standard search box and result cards, so it reuses all of
    AmazonShop's parsing/cart logic; only the storefront entry point differs.
    Fresh is delivery-location gated: it only returns products when the account
    has a serviceable Fresh delivery address set.
    """

    name = "amazon-fresh"
    label = "Amazon Fresh"
    hidden = False  # shown in the UI (parent AmazonShop is hidden; Fresh is not)
    session_key = "amazon"  # share the regular Amazon session — no second login
    comparable = True  # part of the grocery comparison set
    base_url = os.environ.get("AMAZON_URL", "https://www.amazon.com").rstrip("/")
    search_url = os.environ.get("AMAZON_FRESH_URL", f"{base_url}/fresh").rstrip("/")

    def search(self, page, query: str, top: int) -> list[Product]:
        products = super().search(page, query, top)
        if not products:
            body = (self.text_or_none(page.locator("body")) or "").lower()
            if "not available" in body or "no results" in body:
                raise BlockedBySite(
                    "Amazon Fresh returned no products — it is delivery-location "
                    "gated. Set a serviceable Fresh delivery address on your "
                    "Amazon account (or set AMAZON_FRESH_URL to a serviceable "
                    "region), then try again."
                )
        return products
