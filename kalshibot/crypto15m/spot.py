"""Live crypto spot mids from public exchange REST (no API key)."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

# Binance USDT pairs; HYPE may be missing on some venues.
BINANCE_SYMBOL = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
    "DOGE": "DOGEUSDT",
    "BNB": "BNBUSDT",
    "HYPE": "HYPEUSDT",
}

COINBASE_PRODUCT = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
}

HEADERS = {
    "User-Agent": "kalshibot-crypto15m/1.0",
    "Accept": "application/json",
}

_cache: dict[str, tuple[float, float]] = {}
_CACHE_TTL = 1.5


@dataclass
class SpotQuote:
    asset: str
    mid: float
    source: str
    ts: float


def _binance_mid(asset: str, *, host: str = "https://api.binance.com") -> float | None:
    symbol = BINANCE_SYMBOL.get(asset.upper())
    if not symbol:
        return None
    resp = requests.get(
        f"{host}/api/v3/ticker/bookTicker",
        params={"symbol": symbol},
        headers=HEADERS,
        timeout=8,
    )
    if resp.status_code >= 400:
        return None
    data = resp.json()
    bid = float(data["bidPrice"])
    ask = float(data["askPrice"])
    if bid <= 0 or ask <= 0:
        return None
    return (bid + ask) / 2.0


def _coinbase_mid(asset: str) -> float | None:
    product = COINBASE_PRODUCT.get(asset.upper())
    if not product:
        return None
    resp = requests.get(
        f"https://api.exchange.coinbase.com/products/{product}/ticker",
        headers=HEADERS,
        timeout=8,
    )
    if resp.status_code >= 400:
        return None
    data = resp.json()
    bid = float(data.get("bid") or 0)
    ask = float(data.get("ask") or 0)
    if bid <= 0 or ask <= 0:
        last = float(data.get("price") or 0)
        return last if last > 0 else None
    return (bid + ask) / 2.0


def _kraken_mid(asset: str) -> float | None:
    # Kraken pair names
    pairs = {
        "BTC": "XBTUSD",
        "ETH": "ETHUSD",
        "SOL": "SOLUSD",
        "XRP": "XRPUSD",
        "DOGE": "DOGEUSD",
        "BNB": "BNBUSD",
    }
    pair = pairs.get(asset.upper())
    if not pair:
        return None
    resp = requests.get(
        "https://api.kraken.com/0/public/Ticker",
        params={"pair": pair},
        headers=HEADERS,
        timeout=8,
    )
    if resp.status_code >= 400:
        return None
    result = (resp.json() or {}).get("result") or {}
    if not result:
        return None
    book = next(iter(result.values()))
    bid = float((book.get("b") or [0])[0])
    ask = float((book.get("a") or [0])[0])
    if bid <= 0 or ask <= 0:
        return None
    return (bid + ask) / 2.0


def fetch_spot(asset: str, *, use_cache: bool = True) -> SpotQuote | None:
    """Best-effort mid: Binance → Binance.US → Coinbase → Kraken."""
    key = asset.upper()
    now = time.time()
    if use_cache and key in _cache:
        mid, ts = _cache[key]
        if now - ts < _CACHE_TTL:
            return SpotQuote(asset=key, mid=mid, source="cache", ts=ts)

    errors: list[str] = []
    sources = (
        ("binance", lambda: _binance_mid(key)),
        ("binance.us", lambda: _binance_mid(key, host="https://api.binance.us")),
        ("coinbase", lambda: _coinbase_mid(key)),
        ("kraken", lambda: _kraken_mid(key)),
    )
    for name, fn in sources:
        try:
            mid = fn()
        except Exception as exc:
            errors.append(f"{name}:{exc}")
            continue
        if mid is None or mid <= 0:
            errors.append(f"{name}:empty")
            continue
        _cache[key] = (mid, now)
        return SpotQuote(asset=key, mid=mid, source=name, ts=now)

    if errors:
        print(f"[spot {key}] failed ({'; '.join(errors[:3])})", flush=True)
    return None


def fetch_spots(assets: list[str]) -> dict[str, SpotQuote]:
    out: dict[str, SpotQuote] = {}
    for asset in assets:
        q = fetch_spot(asset)
        if q is not None:
            out[asset.upper()] = q
    return out
