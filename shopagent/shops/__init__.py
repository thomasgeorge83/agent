"""Shop implementations and registry.

Importing this package registers all built-in shops. To add a shop, create a
module here that defines a ``Shop`` subclass decorated with ``@register_shop``,
then import it below so it registers on startup.
"""

from .registry import get_shop, list_shops, register_shop

# Import built-in shops so their @register_shop decorators run.
from . import amazon  # noqa: F401  (registers Amazon, Amazon Fresh, Amazon Now)
from . import flipkart  # noqa: F401  (registers FlipkartShop)
from . import grocery  # noqa: F401  (registers Flipkart Minutes, BigBasket)

__all__ = ["get_shop", "list_shops", "register_shop"]
