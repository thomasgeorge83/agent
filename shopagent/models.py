"""Shop-agnostic data models.

Kept deliberately generic so every shop maps onto the same shapes. Prices stay
as the site's displayed string (e.g. "$19.99") to avoid currency/parse errors;
add a parsed numeric field later if you need arithmetic.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    title: str
    price: Optional[str] = None
    rating: Optional[str] = None
    url: Optional[str] = None
    shop: Optional[str] = None
    image_url: Optional[str] = None
    reviews_count: Optional[str] = None
    features: list = field(default_factory=list)  # list[str] bullet points
    availability: Optional[str] = None


@dataclass
class OrderResult:
    """Outcome of a place/modify/cancel order action."""

    ok: bool
    message: str
    order_id: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class CartItem:
    title: str
    price: Optional[str] = None
    quantity: Optional[str] = None


@dataclass
class CartReview:
    """A read-back of the cart after adding an item.

    This is the deliberate stopping point of the ordering flow: the item is in
    the cart and these are the contents, but NO order has been placed.
    """

    items: list = field(default_factory=list)  # list[CartItem]
    subtotal: Optional[str] = None
    item_count: int = 0
    note: str = ""
