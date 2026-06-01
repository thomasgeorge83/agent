"""Command-line price checker (thin wrapper over the shopagent package).

Uses a shop's saved session (no password is used or stored) to search for an
item and report title / price / rating / link, or to read one product by URL.
No account/personal data is logged.

Usage:
    python price_check.py "logitech mouse"
    python price_check.py "logitech mouse" --shop amazon --top 5
    python price_check.py "logitech mouse" --json
    python price_check.py --url "https://www.amazon.com/dp/B0XXXXXXX"
    python price_check.py --list-shops

If a check reports the session expired, run:  python login.py --shop <name>
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from shopagent import (
    BlockedBySite,
    SessionExpired,
    ShopAgentError,
    get_product,
    list_shops,
    render_json,
    render_text,
    search,
)

load_dotenv()

DEFAULT_SHOP = os.environ.get("SHOP", "amazon")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check item prices at an online shop using your saved session.")
    parser.add_argument("query", nargs="?", help="Item to search for, e.g. \"logitech mouse\".")
    parser.add_argument("--shop", default=DEFAULT_SHOP, help=f"Which shop to use (default {DEFAULT_SHOP}).")
    parser.add_argument("--url", help="Read a specific product page by URL instead of searching.")
    parser.add_argument("--top", type=int, default=3, help="How many search results to show (default 3).")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text.")
    parser.add_argument("--headless", action="store_true",
                        help="Run without a visible browser (may trigger bot checks more often).")
    parser.add_argument("--list-shops", action="store_true", help="List available shops and exit.")
    args = parser.parse_args()

    if args.list_shops:
        for shop in list_shops():
            print(f"{shop.name:12} {shop.label}")
        return

    if not args.query and not args.url:
        args.query = os.environ.get("SEARCH_QUERY")
    if not args.query and not args.url:
        parser.error("provide an item to search for, or --url for a specific product.")

    try:
        if args.url:
            product = get_product(args.shop, args.url, headless=args.headless)
            products = [product] if product else []
        else:
            products = search(args.shop, args.query, top=args.top, headless=args.headless)
    except (SessionExpired, BlockedBySite, ShopAgentError) as exc:
        sys.exit(str(exc))

    label = args.url or args.query
    if args.json:
        print(render_json(products))
    else:
        print(render_text(products, label))


if __name__ == "__main__":
    main()
