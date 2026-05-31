"""Amazon search agent (skeleton).

Loads the saved session created by login.py (no password needed), confirms the
session is still valid, and runs a search. Build the result-parsing logic out
from here as the next iteration.

Run:
    python search.py "wireless mouse"

If no query is given, SEARCH_QUERY from .env is used.
"""

import os
import sys

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

AMAZON_URL = os.environ.get("AMAZON_URL", "https://www.amazon.com")
AUTH_FILE = "auth_state.json"


def main(query: str) -> None:
    if not os.path.exists(AUTH_FILE):
        sys.exit("No session found. Run `python login.py` first.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        page.goto(AMAZON_URL, wait_until="domcontentloaded")

        # Confirm the saved session is still valid. We intentionally do NOT
        # print the account name or any other personal data.
        if page.locator("#nav-link-accountList").count():
            print("Session loaded.")

        # Run the search.
        page.fill("#twotabsearchtextbox", query)
        page.press("#twotabsearchtextbox", "Enter")
        page.wait_for_selector('[data-component-type="s-search-result"]', timeout=15000)

        # Starter output: print the first few product titles.
        # TODO (next iteration): parse title + price + URL into structured data.
        titles = page.locator('[data-component-type="s-search-result"] h2 span')
        count = titles.count()
        print(f"Found {count} result blocks for: {query}")
        for i in range(min(count, 5)):
            print(f" - {titles.nth(i).inner_text()}")

        browser.close()


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SEARCH_QUERY", "usb-c cable")
    main(q)
