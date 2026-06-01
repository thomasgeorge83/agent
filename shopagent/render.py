"""Output formatting for products — text and JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List

from .models import Product


def render_text(products: List[Product], label: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if not products:
        return f"No results for {label!r} (checked {stamp})."
    lines = [f"Results for {label!r} — {stamp}", "-" * 56]
    for i, prod in enumerate(products, 1):
        title = (prod.title[:70] + "…") if len(prod.title) > 71 else prod.title
        lines.append(f"{i}. {title}")
        lines.append(f"   Price : {prod.price or 'not shown'}")
        if prod.rating:
            lines.append(f"   Rating: {prod.rating}")
        if prod.url:
            lines.append(f"   Link  : {prod.url}")
    return "\n".join(lines)


def render_json(products: List[Product]) -> str:
    return json.dumps([asdict(p) for p in products], indent=2, ensure_ascii=False)
