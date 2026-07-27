"""Discover open Kalshi KX{ASSET}15M markets."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from kalshibot.client import get_client, load_response

DEFAULT_ASSETS = ("BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "HYPE")

_TARGET_RE = re.compile(
    r"(?:target\s*price|price\s*to\s*beat)\s*:\s*\$?\s*([\d,]+(?:\.\d+)?)",
    re.I,
)


def series_ticker(asset: str) -> str:
    return f"KX{asset.strip().upper()}15M"


def assets_from_env() -> list[str]:
    raw = (os.getenv("CRYPTO15M_ASSETS") or ",".join(DEFAULT_ASSETS)).strip()
    return [a.strip().upper() for a in raw.split(",") if a.strip()]


def _parse_dollars(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_time(raw: Any) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def price_to_beat(market: dict) -> float | None:
    """Window open / price-to-beat from floor_strike or subtitle."""
    strike = market.get("floor_strike")
    if strike is not None:
        try:
            return float(strike)
        except (TypeError, ValueError):
            pass
    for key in ("yes_sub_title", "subtitle", "title", "no_sub_title"):
        blob = market.get(key) or ""
        m = _TARGET_RE.search(str(blob))
        if m:
            return _parse_dollars(m.group(1))
    return None


@dataclass
class Crypto15mMarket:
    asset: str
    series: str
    ticker: str
    event_ticker: str
    title: str
    price_to_beat: float
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    yes_ask_size: float | None
    close_time: datetime | None
    open_time: datetime | None
    volume: float | None
    raw: dict

    @property
    def seconds_to_close(self) -> float | None:
        if self.close_time is None:
            return None
        return (self.close_time - datetime.now(timezone.utc)).total_seconds()


def _market_from_api(asset: str, market: dict) -> Crypto15mMarket | None:
    beat = price_to_beat(market)
    if beat is None or beat <= 0:
        return None
    ticker = market.get("ticker")
    if not ticker:
        return None
    status = (market.get("status") or "").lower()
    if status not in {"open", "active", ""}:
        return None
    return Crypto15mMarket(
        asset=asset.upper(),
        series=series_ticker(asset),
        ticker=str(ticker),
        event_ticker=str(market.get("event_ticker") or ""),
        title=str(market.get("title") or ""),
        price_to_beat=beat,
        yes_bid=_parse_dollars(market.get("yes_bid_dollars")),
        yes_ask=_parse_dollars(market.get("yes_ask_dollars")),
        no_bid=_parse_dollars(market.get("no_bid_dollars")),
        no_ask=_parse_dollars(market.get("no_ask_dollars")),
        yes_ask_size=_parse_dollars(market.get("yes_ask_size_fp")),
        close_time=_parse_time(market.get("close_time")),
        open_time=_parse_time(market.get("open_time")),
        volume=_parse_dollars(
            market.get("volume_24h_fp") or market.get("volume_fp")
        ),
        raw=market,
    )


def fetch_open_markets(
    assets: list[str] | None = None,
    *,
    client=None,
    limit_per_series: int = 20,
) -> list[Crypto15mMarket]:
    """Return open 15m markets that already have a price-to-beat."""
    if client is None:
        client = get_client()
    assets = assets or assets_from_env()
    out: list[Crypto15mMarket] = []
    for asset in assets:
        series = series_ticker(asset)
        cursor = None
        fetched = 0
        while fetched < limit_per_series:
            kwargs: dict[str, Any] = {
                "series_ticker": series,
                "status": "open",
                "limit": min(100, limit_per_series - fetched),
            }
            if cursor:
                kwargs["cursor"] = cursor
            try:
                data = load_response(
                    client.get_markets_without_preload_content(**kwargs)
                )
            except Exception:
                # Some SDK versions want status=active
                kwargs["status"] = "active"
                try:
                    data = load_response(
                        client.get_markets_without_preload_content(**kwargs)
                    )
                except Exception as exc:
                    print(f"[{series}] market fetch failed: {exc}", flush=True)
                    break
            markets = data.get("markets") or []
            if not markets:
                break
            for m in markets:
                parsed = _market_from_api(asset, m)
                if parsed is not None:
                    out.append(parsed)
            fetched += len(markets)
            cursor = data.get("cursor")
            if not cursor:
                break
    # Prefer soonest close; drop already-closed windows
    now = datetime.now(timezone.utc)
    live = [
        m
        for m in out
        if m.close_time is None or m.close_time > now
    ]
    live.sort(key=lambda m: (m.close_time or now, m.asset, m.ticker))
    return live


def nearest_per_asset(markets: list[Crypto15mMarket]) -> list[Crypto15mMarket]:
    """Keep the soonest open window per asset (typical live book)."""
    best: dict[str, Crypto15mMarket] = {}
    for m in markets:
        prev = best.get(m.asset)
        if prev is None:
            best[m.asset] = m
            continue
        if m.close_time and prev.close_time and m.close_time < prev.close_time:
            best[m.asset] = m
    return list(best.values())
