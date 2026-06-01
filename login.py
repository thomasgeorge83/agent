"""One-time manual login to Amazon.

This saves an authenticated browser *session* so the agent never needs — and
never stores — your password. You log in by hand (handling any OTP / CAPTCHA),
and only the resulting session cookies are saved.

Run:
    python login.py

A browser window opens. Sign in to Amazon manually. The script watches the page
and, once it sees you are signed in, saves the session automatically and closes.
No "press Enter" step is required, so it also works when launched from the GUI.

The session is written to auth_state.json next to this script. That file is
git-ignored and must be treated as a secret (it grants access to your account).
"""

import os
import sys
import time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
AMAZON_URL = os.environ.get("AMAZON_URL", "https://www.amazon.com").rstrip("/")
AUTH_FILE = os.path.join(HERE, "auth_state.json")

# How long to wait for a manual sign-in before giving up (minutes).
LOGIN_TIMEOUT_SECONDS = 5 * 60
POLL_SECONDS = 2


def is_logged_in(page) -> bool:
    """True once the Amazon nav greeting shows an account (not 'sign in')."""
    for selector in ("#nav-link-accountList-nav-line-1", "#nav-link-accountList"):
        try:
            el = page.locator(selector)
            if el.count():
                txt = (el.first.inner_text(timeout=1000) or "").strip().lower()
                if txt and "sign in" not in txt:
                    return True
        except Exception:
            continue
    return False


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(AMAZON_URL, wait_until="domcontentloaded")

        print("\n A browser window is open.")
        print(" 1. Click 'Sign in' and log in to Amazon manually.")
        print("    (Handle any OTP / 2FA / CAPTCHA in that window.)")
        print(" 2. Once you see 'Hello, <your name>', the session saves itself.\n")
        print(" Waiting for you to sign in... (do not close the browser)\n")

        deadline = time.time() + LOGIN_TIMEOUT_SECONDS
        confirmed = 0
        try:
            while time.time() < deadline:
                if is_logged_in(page):
                    # Require two consecutive positive checks to avoid saving
                    # on a half-loaded page.
                    confirmed += 1
                    if confirmed >= 2:
                        break
                else:
                    confirmed = 0
                time.sleep(POLL_SECONDS)
            else:
                print(" Timed out waiting for sign-in. Nothing was saved.")
                print(" Run login again and complete the sign-in.\n")
                browser.close()
                return 1

            context.storage_state(path=AUTH_FILE)
            print(f"\n Signed in. Session saved to {os.path.basename(AUTH_FILE)}.")
            print(" Keep it secret — it is git-ignored and grants account access.\n")
            browser.close()
            return 0
        except Exception as exc:
            # E.g. the user closed the browser before signing in.
            print(f" Login did not complete: {exc}")
            try:
                browser.close()
            except Exception:
                pass
            return 1


if __name__ == "__main__":
    sys.exit(main())
