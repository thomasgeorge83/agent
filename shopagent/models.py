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


@dataclass
class OrderResult:
    """Outcome of a place/modify/cancel order action."""

    ok: bool
    message: str
    order_id: Optional[str] = None
    details: dict = field(default_factory=dict)
