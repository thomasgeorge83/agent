"""Desktop GUI for the shop agent.

Double-click "Price Checker.bat" (or run `python gui.py` in the venv) to open a
small window: pick a shop, type an item, click Check Price, and see title /
price / rating / link for the top matches. Uses each shop's saved login session
— no password is entered or stored here, and no account/personal data is logged.

If you have not logged in to the selected shop yet (or its session expired), use
the "Log in" button; it runs the one-time manual login in a real browser window.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from shopagent import (
    BlockedBySite,
    SessionExpired,
    ShopAgentError,
    list_shops,
    render_text,
    search,
)
from shopagent.session import has_session

HERE = os.path.dirname(os.path.abspath(__file__))


class PriceCheckerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: threading.Thread | None = None

        self.shops = list_shops()
        self.shop_labels = {s.label: s.name for s in self.shops}

        root.title("Online Shop Price Checker")
        root.minsize(580, 440)

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        # Row 0: shop selector
        ttk.Label(main, text="Shop:").grid(row=0, column=0, sticky="w")
        self.shop_var = tk.StringVar(value=self.shops[0].label if self.shops else "")
        shop_box = ttk.Combobox(
            main, textvariable=self.shop_var, state="readonly",
            values=[s.label for s in self.shops],
        )
        shop_box.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(8, 0))
        shop_box.bind("<<ComboboxSelected>>", lambda _e: self._set_session_status())

        # Row 1: item entry
        ttk.Label(main, text="Item to check:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.query_var = tk.StringVar()
        entry = ttk.Entry(main, textvariable=self.query_var)
        entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        entry.bind("<Return>", lambda _e: self.start_check())
        entry.focus()

        # Row 2: options
        opts = ttk.Frame(main)
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(opts, text="Results:").pack(side="left")
        self.top_var = tk.IntVar(value=3)
        ttk.Spinbox(opts, from_=1, to=10, width=4, textvariable=self.top_var).pack(
            side="left", padx=(4, 16)
        )
        self.show_browser = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, text="Show browser window", variable=self.show_browser
        ).pack(side="left")

        # Row 3: buttons
        btns = ttk.Frame(main)
        btns.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.check_btn = ttk.Button(btns, text="Check Price", command=self.start_check)
        self.check_btn.pack(side="left")
        self.login_btn = ttk.Button(btns, text="Log in", command=self.start_login)
        self.login_btn.pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Clear", command=self.clear_results).pack(side="left", padx=(8, 0))

        # Row 4: results
        self.results = scrolledtext.ScrolledText(
            main, wrap="word", height=14, state="disabled"
        )
        self.results.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        main.rowconfigure(4, weight=1)

        # Row 5: status bar
        self.status = tk.StringVar()
        ttk.Label(main, textvariable=self.status, anchor="w").grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=(6, 0)
        )
        self._set_session_status()

        self.root.after(120, self._drain_queue)

    # ---- helpers --------------------------------------------------------
    def _current_shop(self) -> str:
        return self.shop_labels.get(self.shop_var.get(), "")

    def _set_session_status(self) -> None:
        shop = self._current_shop()
        label = self.shop_var.get()
        if shop and has_session(shop):
            self.status.set(f"{label}: session found. Ready to check prices.")
        else:
            self.status.set(f"{label}: no session yet — click 'Log in' first.")

    def _write(self, text: str) -> None:
        self.results.configure(state="normal")
        self.results.insert("end", text + "\n")
        self.results.see("end")
        self.results.configure(state="disabled")

    def clear_results(self) -> None:
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.configure(state="disabled")

    def _busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.check_btn.configure(state=state)
        self.login_btn.configure(state=state)

    # ---- price check ----------------------------------------------------
    def start_check(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        shop = self._current_shop()
        query = self.query_var.get().strip()
        if not query:
            self.status.set("Enter an item to check.")
            return
        if not has_session(shop):
            self.status.set(f"{self.shop_var.get()}: no session — click 'Log in' first.")
            return
        self._busy(True)
        self.status.set(f"Checking '{query}' at {self.shop_var.get()}…")
        top = max(1, min(10, self.top_var.get()))
        headless = not self.show_browser.get()
        self.worker = threading.Thread(
            target=self._do_check, args=(shop, query, top, headless), daemon=True
        )
        self.worker.start()

    def _do_check(self, shop: str, query: str, top: int, headless: bool) -> None:
        try:
            products = search(shop, query, top=top, headless=headless)
            self.queue.put(("result", (query, products)))
        except (SessionExpired, BlockedBySite, ShopAgentError) as exc:
            self.queue.put(("error", str(exc)))
        except Exception as exc:  # keep the GUI alive on unexpected errors
            self.queue.put(("error", f"Unexpected error: {exc}"))

    # ---- login ----------------------------------------------------------
    def start_login(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        shop = self._current_shop()
        self._busy(True)
        self.status.set(f"Opening {self.shop_var.get()} login… sign in; it saves automatically.")
        self.worker = threading.Thread(target=self._do_login, args=(shop,), daemon=True)
        self.worker.start()

    def _do_login(self, shop: str) -> None:
        try:
            # The GUI runs under pythonw.exe (no console). login.py prints
            # instructions and watches the browser, so launch it with the real
            # python.exe in its own console window. It auto-detects sign-in and
            # saves the session — no "press Enter" needed.
            exe = sys.executable
            if os.name == "nt" and os.path.basename(exe).lower() == "pythonw.exe":
                console_exe = os.path.join(os.path.dirname(exe), "python.exe")
                if os.path.exists(console_exe):
                    exe = console_exe
            creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
            proc = subprocess.run(
                [exe, os.path.join(HERE, "login.py"), "--shop", shop],
                creationflags=creationflags,
            )
            if proc.returncode == 0:
                self.queue.put(("login_done", None))
            else:
                self.queue.put(("error", "Login did not complete. Try again."))
        except Exception as exc:
            self.queue.put(("error", f"Could not start login: {exc}"))

    # ---- queue pump -----------------------------------------------------
    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "result":
                    query, products = payload
                    self._write(render_text(products, query))
                    self._write("")
                    self.status.set(f"Done — {len(products)} result(s) for '{query}'.")
                    self._busy(False)
                elif kind == "login_done":
                    self._set_session_status()
                    self.status.set("Login saved. You can check prices now.")
                    self._busy(False)
                elif kind == "error":
                    self._write(str(payload))
                    self._write("")
                    self.status.set("There was a problem — see details above.")
                    self._busy(False)
        except queue.Empty:
            pass
        self.root.after(120, self._drain_queue)


def main() -> None:
    root = tk.Tk()
    PriceCheckerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
