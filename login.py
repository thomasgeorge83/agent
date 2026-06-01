"""One-time manual login to an online shop (thin wrapper over shopagent).

Opens a browser, watches the page, and once you are signed in saves that shop's
session automatically — no password is typed or stored, and no "press Enter"
step is needed (so it also works when launched from the GUI).

Run:
    python login.py                 # default shop (amazon)
    python login.py --shop amazon

Sessions are written to auth_state.<shop>.json in the project root. Those files
are git-ignored secrets (they grant account access).
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from shopagent import login, ShopAgentError
from shopagent.shops import get_shop

load_dotenv()

DEFAULT_SHOP = os.environ.get("SHOP", "amazon")


def main() -> int:
    parser = argparse.ArgumentParser(description="Log in to an online shop and save its session.")
    parser.add_argument("--shop", default=DEFAULT_SHOP, help=f"Which shop to log in to (default {DEFAULT_SHOP}).")
    args = parser.parse_args()

    try:
        shop = get_shop(args.shop)
    except ShopAgentError as exc:
        print(str(exc))
        return 1

    print(f"\n A browser window is opening for {shop.label}.")
    print(" 1. Sign in manually (handle any OTP / 2FA / CAPTCHA).")
    print(" 2. Once you are signed in, the session saves itself and the browser closes.\n")
    print(" Waiting for you to sign in... (do not close the browser)\n")

    try:
        ok = login(args.shop, headless=False)
    except ShopAgentError as exc:
        print(f" Login could not complete: {exc}")
        return 1

    if ok:
        print(f"\n Signed in. Session for {shop.label} saved.")
        print(" Keep it secret — it is git-ignored and grants account access.\n")
        return 0
    print(" Timed out waiting for sign-in. Nothing was saved. Try again.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
