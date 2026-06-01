"""Desktop GUI for the shop agent.

Double-click "Price Checker.bat" (or run `python gui.py` in the venv) to open the
window: pick a shop, type an item, click Check Price, and browse the matches as
cards with a thumbnail, price and rating. Click "Details" on any card to open a
window with a larger image and the product's feature bullets.

Uses each shop's saved login session — no password is entered or stored here,
and no account/personal data is logged.
"""

import io
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from shopagent import (
    add_to_cart,
    BlockedBySite,
    compare,
    render_cart,
    SessionExpired,
    ShopAgentError,
    get_product,
    list_shops,
    shop_has_session,
)
from shopagent.images import fetch_image_bytes

HERE = os.path.dirname(os.path.abspath(__file__))
THUMB_SIZE = (96, 96)
DETAIL_IMG_SIZE = (320, 320)


class PriceCheckerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: threading.Thread | None = None
        # Keep references to PhotoImage objects so Tk doesn't garbage-collect them.
        self._images: list = []

        self.shops = list_shops()

        root.title("Online Shop Price Comparison")
        root.minsize(820, 560)

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        # Row 0: item entry — searches every platform at once
        ttk.Label(main, text="Item to compare:").grid(row=0, column=0, sticky="w")
        self.query_var = tk.StringVar()
        entry = ttk.Entry(main, textvariable=self.query_var)
        entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(8, 0))
        entry.bind("<Return>", lambda _e: self.start_compare())
        entry.focus()

        # Row 1: options
        opts = ttk.Frame(main)
        opts.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(opts, text="Per platform:").pack(side="left")
        self.top_var = tk.IntVar(value=4)
        ttk.Spinbox(opts, from_=1, to=10, width=4, textvariable=self.top_var).pack(
            side="left", padx=(4, 16)
        )
        self.show_browser = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Show browser window", variable=self.show_browser).pack(side="left")

        # Row 2: buttons — one action: compare across all platforms
        btns = ttk.Frame(main)
        btns.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.compare_btn = ttk.Button(btns, text="Compare Prices", command=self.start_compare)
        self.compare_btn.pack(side="left")
        self.login_all_btn = ttk.Button(btns, text="Log in to platforms", command=self.start_login_all)
        self.login_all_btn.pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Clear", command=self.clear_results).pack(side="left", padx=(8, 0))

        # Row 4: scrollable results area (cards)
        self.canvas = tk.Canvas(main, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.canvas.yview)
        self.cards = ttk.Frame(self.canvas)
        self.cards.bind(
            "<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self._card_window = self.canvas.create_window((0, 0), window=self.cards, anchor="nw")
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(self._card_window, width=e.width)
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.scrollbar.grid(row=3, column=2, sticky="ns", pady=(10, 0))
        main.rowconfigure(3, weight=1)

        # Row 4: status bar
        self.status = tk.StringVar()
        ttk.Label(main, textvariable=self.status, anchor="w").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0)
        )
        self._set_status()

        self.root.after(120, self._drain_queue)

    # ---- helpers --------------------------------------------------------
    def _set_status(self) -> None:
        labels = ", ".join(s.label for s in self.shops)
        self.status.set(f"Ready. Enter an item to compare across: {labels}.")

    def clear_results(self) -> None:
        for child in self.cards.winfo_children():
            child.destroy()
        self._images.clear()

    def _busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.compare_btn.configure(state=state)
        self.login_all_btn.configure(state=state)

    # ---- compare across all platforms ----------------------------------
    def start_compare(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        query = self.query_var.get().strip()
        if not query:
            self.status.set("Enter an item to compare.")
            return
        # Always compare every shown platform. A platform with no session (and
        # that requires login) is still included — compare() reports it as
        # "not logged in" in its own column rather than dropping it.
        names = [s.name for s in self.shops]
        self.clear_results()
        self._busy(True)
        self.status.set(f"Comparing '{query}' across {len(names)} platform(s)…")
        top = max(1, min(10, self.top_var.get()))
        headless = not self.show_browser.get()
        self.worker = threading.Thread(
            target=self._do_compare, args=(query, names, top, headless), daemon=True
        )
        self.worker.start()

    def _do_compare(self, query: str, names: list, top: int, headless: bool) -> None:
        try:
            results = compare(query, names, top=top, headless=headless)
            self.queue.put(("compare", (query, results)))
        except Exception as exc:
            self.queue.put(("error", f"Unexpected error: {exc}"))

    # ---- result rendering ----------------------------------------------
    def _render_comparison(self, query: str, results: dict) -> None:
        """Render one column per platform, side by side, for the same query."""
        wrap = ttk.Frame(self.cards)
        wrap.pack(fill="both", expand=True, padx=4, pady=4)

        ttk.Label(self.cards, text=f"Comparison for '{query}'",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=4)

        for col, (name, entry) in enumerate(results.items()):
            wrap.columnconfigure(col, weight=1, uniform="cmp")
            column = ttk.Frame(wrap, padding=6, relief="solid", borderwidth=1)
            column.grid(row=0, column=col, sticky="nsew", padx=4)

            ttk.Label(column, text=entry.get("label", name),
                      font=("Segoe UI", 10, "bold")).pack(anchor="w")

            if entry.get("error"):
                ttk.Label(column, text=entry["error"], wraplength=200,
                          foreground="#a00", justify="left").pack(anchor="w", pady=(4, 0))
                continue

            products = entry.get("products") or []
            if not products:
                ttk.Label(column, text="No priced results.",
                          foreground="#666").pack(anchor="w", pady=(4, 0))
                continue

            for product in products:
                item = ttk.Frame(column)
                item.pack(fill="x", pady=(8, 0))
                thumb = ttk.Label(item)
                thumb.pack(anchor="w")
                self._load_thumb_async(thumb, product.image_url)
                ttk.Label(item, text=product.title, wraplength=200,
                          justify="left").pack(anchor="w")
                ttk.Label(item, text=product.price or "not shown",
                          font=("Segoe UI", 10, "bold"),
                          foreground="#0a6").pack(anchor="w")
                if product.rating:
                    ttk.Label(item, text=product.rating, foreground="#666").pack(anchor="w")
                row = ttk.Frame(item)
                row.pack(anchor="w", pady=(2, 0))
                if product.url:
                    ttk.Button(row, text="Add to Cart",
                               command=lambda s=name, p=product: self.start_add_to_cart(s, p)).pack(side="left")
                    ttk.Button(row, text="Open",
                               command=lambda u=product.url: webbrowser.open(u)).pack(side="left", padx=(4, 0))

    def _load_thumb_async(self, label: ttk.Label, url) -> None:
        def work():
            data = fetch_image_bytes(url)
            self.queue.put(("thumb", (label, data)))
        threading.Thread(target=work, daemon=True).start()

    # ---- add to cart ----------------------------------------------------
    def start_add_to_cart(self, shop: str, product) -> None:
        if self.worker and self.worker.is_alive():
            self.status.set("Busy — wait for the current action to finish.")
            return
        if not product.url:
            self.status.set("This item has no product link to add.")
            return
        # Confirm before changing the cart. This is the deliberate opt-in that
        # also satisfies the add_to_cart(confirm=True) requirement. It NEVER
        # places an order — it stops at the cart.
        ok = messagebox.askyesno(
            "Add to Cart",
            f"Add this item to your {self.shop_var.get()} cart?\n\n"
            f"{product.title[:120]}\nPrice: {product.price or 'not shown'}\n\n"
            "This only adds it to your cart — it will NOT place an order.",
        )
        if not ok:
            return
        self._busy(True)
        self.status.set("Adding to cart…")
        self.worker = threading.Thread(
            target=self._do_add_to_cart, args=(shop, product.url), daemon=True
        )
        self.worker.start()

    def _do_add_to_cart(self, shop: str, url: str) -> None:
        try:
            review = add_to_cart(shop, url, confirm=True, headless=not self.show_browser.get())
            self.queue.put(("cart", review))
        except (SessionExpired, BlockedBySite, ShopAgentError) as exc:
            self.queue.put(("error", str(exc)))
        except Exception as exc:
            self.queue.put(("error", f"Unexpected error: {exc}"))

    def _set_image(self, label, data, size) -> None:
        if not data:
            label.configure(text="(no image)")
            return
        try:
            img = Image.open(io.BytesIO(data))
            img.thumbnail(size)
            photo = ImageTk.PhotoImage(img)
            self._images.append(photo)  # prevent GC
            label.configure(image=photo)
        except Exception:
            label.configure(text="(no image)")

    # ---- details window -------------------------------------------------
    def open_details(self, shop: str, product) -> None:
        win = tk.Toplevel(self.root)
        win.title(product.title[:60])
        win.minsize(420, 420)
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        img_label = ttk.Label(frame, text="Loading image…")
        img_label.pack()
        # Show the image we already have, then fetch full details for features.
        threading.Thread(
            target=lambda: self.queue.put(("detail_img", (img_label, fetch_image_bytes(product.image_url)))),
            daemon=True,
        ).start()

        ttk.Label(frame, text=product.title, wraplength=380, justify="left",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 0))
        ttk.Label(frame, text=f"Price: {product.price or 'not shown'}").pack(anchor="w")
        if product.rating:
            extra = f" ({product.reviews_count})" if product.reviews_count else ""
            ttk.Label(frame, text=f"Rating: {product.rating}{extra}").pack(anchor="w")

        feat_box = ttk.LabelFrame(frame, text="Details", padding=8)
        feat_box.pack(fill="both", expand=True, pady=(10, 0))
        loading = ttk.Label(feat_box, text="Loading product details…")
        loading.pack(anchor="w")

        if product.url:
            ttk.Button(frame, text="Open in browser",
                       command=lambda: webbrowser.open(product.url)).pack(anchor="w", pady=(10, 0))

        # Fetch richer details (features/availability) in the background.
        if product.url:
            threading.Thread(
                target=self._do_details, args=(shop, product.url, feat_box, loading), daemon=True
            ).start()
        else:
            loading.configure(text="No product URL to load details from.")

    def _do_details(self, shop, url, feat_box, loading) -> None:
        try:
            full = get_product(shop, url, headless=not self.show_browser.get())
            self.queue.put(("details", (feat_box, loading, full)))
        except (SessionExpired, BlockedBySite, ShopAgentError) as exc:
            self.queue.put(("details_err", (loading, str(exc))))
        except Exception as exc:
            self.queue.put(("details_err", (loading, f"Unexpected error: {exc}")))

    # ---- log in to all platforms ---------------------------------------
    def start_login_all(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        # One login per distinct session that needs it. Shops sharing a session
        # (e.g. Amazon Fresh uses the Amazon session) are logged in once;
        # login-free shops and already-logged-in sessions are skipped.
        todo: list[tuple[str, str]] = []  # (shop_name, label)
        seen_sessions: set[str] = set()
        for s in self.shops:
            if not s.requires_login:
                continue
            if s.session_name in seen_sessions:
                continue
            seen_sessions.add(s.session_name)
            if not shop_has_session(s.name):
                todo.append((s.name, s.label))
        if not todo:
            self.status.set("All platforms are already logged in (or need no login).")
            return
        labels = ", ".join(lbl for _, lbl in todo)
        if not messagebox.askyesno(
            "Log in to platforms",
            f"You'll sign in to each of these, one at a time:\n\n{labels}\n\n"
            "For each: a browser AND a small console window open. Sign in fully "
            "in the browser, then click the console window and press Enter to "
            "save. The next platform opens after that. Continue?",
        ):
            return
        self._busy(True)
        self.worker = threading.Thread(target=self._do_login_all, args=(todo,), daemon=True)
        self.worker.start()

    def _do_login_all(self, todo: list) -> None:
        done = []
        for shop_name, label in todo:
            self.queue.put(("status", f"Log in to {label}: a browser is opening…"))
            try:
                exe = sys.executable
                if os.name == "nt" and os.path.basename(exe).lower() == "pythonw.exe":
                    console_exe = os.path.join(os.path.dirname(exe), "python.exe")
                    if os.path.exists(console_exe):
                        exe = console_exe
                creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
                proc = subprocess.run(
                    [exe, os.path.join(HERE, "login.py"), "--shop", shop_name],
                    creationflags=creationflags,
                )
                done.append(f"{label}: {'ok' if proc.returncode == 0 else 'skipped/failed'}")
            except Exception as exc:
                done.append(f"{label}: error ({exc})")
        self.queue.put(("login_all_done", done))

    # ---- queue pump -----------------------------------------------------
    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "thumb":
                    label, data = payload
                    self._set_image(label, data, THUMB_SIZE)
                elif kind == "detail_img":
                    label, data = payload
                    self._set_image(label, data, DETAIL_IMG_SIZE)
                    if not data:
                        label.configure(text="(no image)")
                elif kind == "details":
                    feat_box, loading, full = payload
                    loading.destroy()
                    if full and full.availability:
                        ttk.Label(feat_box, text=full.availability,
                                  foreground="#0a6").pack(anchor="w", pady=(0, 4))
                    feats = (full.features if full else None) or []
                    if feats:
                        for f in feats:
                            ttk.Label(feat_box, text=f"• {f}", wraplength=380,
                                      justify="left").pack(anchor="w")
                    else:
                        ttk.Label(feat_box, text="No feature details found.").pack(anchor="w")
                elif kind == "details_err":
                    loading, msg = payload
                    loading.configure(text=msg)
                elif kind == "compare":
                    query, results = payload
                    self._render_comparison(query, results)
                    ok = sum(1 for e in results.values() if e.get("products"))
                    self.status.set(f"Compared '{query}' across {len(results)} platform(s); {ok} with results.")
                    self._busy(False)
                elif kind == "cart":
                    review = payload
                    self._busy(False)
                    self.status.set(
                        f"Added to cart — {review.item_count} item(s) now in cart. No order placed."
                    )
                    messagebox.showinfo("Added to Cart", render_cart(review))
                elif kind == "status":
                    self.status.set(str(payload))
                elif kind == "login_all_done":
                    self._busy(False)
                    summary = "\n".join(payload)
                    self.status.set("Finished logging in. Enter an item to compare.")
                    messagebox.showinfo("Log in to platforms", f"Done:\n\n{summary}")
                elif kind == "error":
                    ttk.Label(self.cards, text=str(payload), wraplength=600,
                              foreground="#a00").pack(anchor="w", padx=4, pady=4)
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
