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
    render_cart,
    SessionExpired,
    ShopAgentError,
    get_product,
    list_shops,
    search,
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
        self.shop_labels = {s.label: s.name for s in self.shops}

        root.title("Online Shop Price Checker")
        root.minsize(720, 540)

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
        self.top_var = tk.IntVar(value=4)
        ttk.Spinbox(opts, from_=1, to=10, width=4, textvariable=self.top_var).pack(
            side="left", padx=(4, 16)
        )
        self.show_browser = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Show browser window", variable=self.show_browser).pack(side="left")

        # Row 3: buttons
        btns = ttk.Frame(main)
        btns.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.check_btn = ttk.Button(btns, text="Check Price", command=self.start_check)
        self.check_btn.pack(side="left")
        self.login_btn = ttk.Button(btns, text="Log in", command=self.start_login)
        self.login_btn.pack(side="left", padx=(8, 0))
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
        self.canvas.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.scrollbar.grid(row=4, column=2, sticky="ns", pady=(10, 0))
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
        if shop and shop_has_session(shop):
            self.status.set(f"{label}: session found. Ready to check prices.")
        else:
            self.status.set(f"{label}: no session yet — click 'Log in' first.")

    def clear_results(self) -> None:
        for child in self.cards.winfo_children():
            child.destroy()
        self._images.clear()

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
        if not shop_has_session(shop):
            self.status.set(f"{self.shop_var.get()}: no session — click 'Log in' first.")
            return
        self.clear_results()
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
            self.queue.put(("result", (shop, query, products)))
        except (SessionExpired, BlockedBySite, ShopAgentError) as exc:
            self.queue.put(("error", str(exc)))
        except Exception as exc:
            self.queue.put(("error", f"Unexpected error: {exc}"))

    # ---- result rendering ----------------------------------------------
    def _add_card(self, shop: str, product) -> None:
        card = ttk.Frame(self.cards, padding=8, relief="solid", borderwidth=1)
        card.pack(fill="x", expand=True, padx=4, pady=4)
        card.columnconfigure(1, weight=1)

        thumb = ttk.Label(card)
        thumb.grid(row=0, column=0, rowspan=4, sticky="n", padx=(0, 10))
        self._load_thumb_async(thumb, product.image_url)

        ttk.Label(card, text=product.title, wraplength=440, justify="left",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w")
        ttk.Label(card, text=f"Price: {product.price or 'not shown'}").grid(
            row=1, column=1, sticky="w")
        if product.rating:
            ttk.Label(card, text=f"Rating: {product.rating}").grid(row=2, column=1, sticky="w")

        actions = ttk.Frame(card)
        actions.grid(row=3, column=1, sticky="w", pady=(6, 0))
        ttk.Button(actions, text="Details",
                   command=lambda p=product: self.open_details(shop, p)).pack(side="left")
        if product.url:
            ttk.Button(actions, text="Add to Cart",
                       command=lambda p=product: self.start_add_to_cart(shop, p)).pack(side="left", padx=(6, 0))
            ttk.Button(actions, text="Open in browser",
                       command=lambda u=product.url: webbrowser.open(u)).pack(side="left", padx=(6, 0))

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
                    shop, query, products = payload
                    if not products:
                        ttk.Label(self.cards, text=f"No results for '{query}'.").pack(anchor="w")
                    for product in products:
                        self._add_card(shop, product)
                    self.status.set(f"Done — {len(products)} result(s) for '{query}'.")
                    self._busy(False)
                elif kind == "thumb":
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
                elif kind == "cart":
                    review = payload
                    self._busy(False)
                    self.status.set(
                        f"Added to cart — {review.item_count} item(s) now in cart. No order placed."
                    )
                    messagebox.showinfo("Added to Cart", render_cart(review))
                elif kind == "login_done":
                    self._set_session_status()
                    self.status.set("Login saved. You can check prices now.")
                    self._busy(False)
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
