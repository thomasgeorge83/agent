"""Registry mapping shop names to Shop instances.

Register a shop with the ``@register_shop`` decorator (see amazon.py). Look one
up with ``get_shop("amazon")`` or enumerate with ``list_shops()``.
"""

from __future__ import annotations

from typing import Dict, List, Type

from ..errors import UnknownShop
from .base import Shop

_REGISTRY: Dict[str, Shop] = {}


def register_shop(cls: Type[Shop]) -> Type[Shop]:
    """Class decorator: instantiate and register a Shop subclass by its name."""
    if not getattr(cls, "name", ""):
        raise ValueError(f"{cls.__name__} must set a non-empty 'name'.")
    _REGISTRY[cls.name.lower()] = cls()
    return cls


def get_shop(name: str) -> Shop:
    try:
        return _REGISTRY[name.lower()]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise UnknownShop(f"Unknown shop {name!r}. Available: {known}.")


def list_shops() -> List[Shop]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]
