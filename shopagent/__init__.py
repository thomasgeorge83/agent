"""shopagent — a modular, multi-shop browser-automation toolkit.

Core ideas
----------
* A **Shop** (see ``shopagent.shops.base.Shop``) encapsulates everything
  site-specific: its URL, how to tell you are logged in, and how to perform
  actions (search, get product, place/modify order). Add a new online shop by
  subclassing ``Shop`` and registering it — nothing else needs to change.
* **Actions** are methods on a Shop. Read-only actions (search, price) are
  implemented. State-changing actions (place/modify/cancel order) default to
  refusing with ``ActionNotSupported`` until a shop explicitly implements them,
  and require an explicit confirmation flag, because they spend real money.
* The session for each shop is created by a one-time manual login and reused;
  no password is ever typed or stored. See ``shopagent.session``.

Public API is re-exported here for convenience.
"""

# Load .env BEFORE importing shop modules: shops read their storefront URLs
# (AMAZON_URL etc.) from the environment at import time, so config must be in
# place first. This makes every entry point (CLI, GUI) pick up .env regardless
# of its own import order.
from dotenv import load_dotenv as _load_dotenv

_load_dotenv()

from .errors import (
    ActionNotSupported,
    BlockedBySite,
    SessionExpired,
    ShopAgentError,
    UnknownShop,
)
from .models import CartItem, CartReview, OrderResult, Product
from .agent import add_to_cart, compare, get_product, login, review_cart, search, shop_has_session
from .render import render_cart, render_json, render_text
from .shops import get_shop, list_shops, register_shop
from .shops.base import Shop

__all__ = [
    "ActionNotSupported",
    "BlockedBySite",
    "SessionExpired",
    "ShopAgentError",
    "UnknownShop",
    "CartItem",
    "CartReview",
    "OrderResult",
    "Product",
    "add_to_cart",
    "compare",
    "get_product",
    "login",
    "review_cart",
    "search",
    "shop_has_session",
    "render_cart",
    "render_json",
    "render_text",
    "get_shop",
    "list_shops",
    "register_shop",
    "Shop",
]
