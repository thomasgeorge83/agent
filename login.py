"""One-time manual login to Amazon.

This saves an authenticated browser *session* so the agent never needs — and
never stores — your password. You log in by hand (handling any OTP / CAPTCHA),
and only the resulting session cookies are saved.

Run:
    python login.py

A browser window opens. Sign in to Amazon manually, then return to this
terminal and press Enter. The session is written to auth_state.json, which is
git-ignored and must be treated as a secret (it grants access to your account).
"""

import os

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

AMAZON_URL = os.environ.get("AMAZON_URL", "https://www.amazon.com")
AUTH_FILE = "auth_state.json"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(AMAZON_URL, wait_until="domcontentloaded")

        print("\n A browser window is open.")
        print(" 1. Click 'Sign in' and log in to Amazon manually.")
        print("    (Handle any OTP / 2FA / CAPTCHA in that window.)")
        print(" 2. Confirm you are signed in (you should see 'Hello, <name>').")
        print(" 3. Return here and press Enter to save the session.\n")
        input(" Press Enter once you are fully logged in... ")

        context.storage_state(path=AUTH_FILE)
        print(f"\n Session saved to {AUTH_FILE}.")
        print(" Keep it secret — it is git-ignored and grants account access.\n")
        browser.close()


if __name__ == "__main__":
    main()
