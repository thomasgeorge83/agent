"""Cart helper CLI — add an item to your cart, or review the cart.

This NEVER places an order. Adding to cart requires --confirm; the script stops
at the cart page so you can review and check out yourself in the browser.

Usage:
    python cart.py review                                   # show cart contents
    python cart.py add --url "https://www.amazon.com/dp/B0XXXXXXX" --confirm
    python cart.py add --shop amazon --url "<product url>" --confirm
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from shopagent import add_to_cart, render_cart, review_cart, ShopAgentError

load_dotenv()

DEFAULT_SHOP = os.environ.get("SHOP", "amazon")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add to cart or review cart (never places an order).")
    parser.add_argument("action", choices=["add", "review"], help="What to do.")
    parser.add_argument("--shop", default=DEFAULT_SHOP, help=f"Which shop (default {DEFAULT_SHOP}).")
    parser.add_argument("--url", help="Product URL (required for 'add').")
    parser.add_argument("--confirm", action="store_true",
                        help="Required to actually add to cart (deliberate opt-in).")
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser.")
    args = parser.parse_args()

    try:
        if args.action == "add":
            if not args.url:
                parser.error("'add' requires --url.")
            review = add_to_cart(args.shop, args.url, confirm=args.confirm, headless=args.headless)
        else:
            review = review_cart(args.shop, headless=args.headless)
    except ShopAgentError as exc:
        sys.exit(str(exc))

    print(render_cart(review))


if __name__ == "__main__":
    main()
