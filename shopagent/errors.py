"""Exception types shared across the toolkit.

These are shop-agnostic so callers (CLI, GUI) can handle them uniformly
regardless of which online shop raised them.
"""


class ShopAgentError(Exception):
    """Base class for all shopagent errors."""


class SessionExpired(ShopAgentError):
    """The saved session for a shop is missing or no longer logged in."""


class BlockedBySite(ShopAgentError):
    """The shop served a CAPTCHA / robot check instead of real content."""


class UnknownShop(ShopAgentError):
    """Requested a shop that is not registered."""


class ActionNotSupported(ShopAgentError):
    """A shop does not implement the requested action (e.g. ordering)."""
