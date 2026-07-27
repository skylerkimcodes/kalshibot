"""Spot-lag edge: live spot vs Kalshi price-to-beat → Up/Down trade plans."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from kalshibot.crypto15m.series import Crypto15mMarket, fetch_open_markets, nearest_per_asset
from kalshibot.crypto15m.spot import SpotQuote, fetch_spots

# Typical 15m realized move scale (fraction) for z-score banding.
_SIGMA_15M = {
    "BTC": 0.0025,
    "ETH": 0.0035,
    "SOL": 0.0050,
    "XRP": 0.0045,
    "DOGE": 0.0060,
    "BNB": 0.0035,
    "HYPE": 0.0080,
}


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def fair_up_prob(spot: float, beat: float, asset: str) -> float:
    """
    Map (spot - beat) / sigma into a fair P(Up).

    Uses a logistic of z-score so small noise stays near 50% and clear
    moves push toward 0/1 without claiming certainty.
    """
    sigma = _SIGMA_15M.get(asset.upper(), 0.004) * beat
    sigma = max(sigma, beat * 1e-6, 1e-9)
    z = (spot - beat) / sigma
    # logistic; scale so |z|≈1 → ~73%
    return 1.0 / (1.0 + math.exp(-1.1 * z))


@dataclass
class TradePlan:
    market: Crypto15mMarket
    spot: float
    spot_source: str
    side: str  # yes=Up, no=Down
    fair: float
    ask: float
    edge: float
    move_bps: float
    seconds_left: float
    contracts: int
    reason: str

    @property
    def label(self) -> str:
        direction = "UP" if self.side == "yes" else "DOWN"
        return (
            f"{self.market.asset} {direction} {self.market.ticker} "
            f"ask={self.ask:.2f} fair={self.fair:.2f} edge={self.edge:+.3f} "
            f"spot={self.spot:.4g} beat={self.market.price_to_beat:.4g} "
            f"({self.move_bps:+.1f}bps, {self.seconds_left:.0f}s left)"
        )


def _pick_side(fair_up: float, market: Crypto15mMarket) -> tuple[str, float, float] | None:
    """Return (side, fair, ask) for the better +EV ask, or None."""
    yes_ask = market.yes_ask
    no_ask = market.no_ask
    # Illiquid / locked books
    candidates: list[tuple[str, float, float]] = []
    if yes_ask is not None and 0.01 < yes_ask < 0.99:
        candidates.append(("yes", fair_up, yes_ask))
    if no_ask is not None and 0.01 < no_ask < 0.99:
        candidates.append(("no", 1.0 - fair_up, no_ask))
    if not candidates:
        return None
    # Prefer highest edge
    best = max(candidates, key=lambda t: t[1] - t[2])
    return best


def plan_for_market(
    market: Crypto15mMarket,
    spot: SpotQuote,
    *,
    min_edge: float | None = None,
    min_seconds: float | None = None,
    max_contracts: int | None = None,
) -> TradePlan | None:
    min_edge = (
        min_edge
        if min_edge is not None
        else _env_float("CRYPTO15M_MIN_EDGE", 0.04)
    )
    min_seconds = (
        min_seconds
        if min_seconds is not None
        else _env_float("CRYPTO15M_MIN_SECONDS_LEFT", 75.0)
    )
    max_contracts = (
        max_contracts
        if max_contracts is not None
        else _env_int("CRYPTO15M_MAX_CONTRACTS", 5)
    )

    secs = market.seconds_to_close
    if secs is not None and secs < min_seconds:
        return None
    # Too early in a brand-new window with TBD strike already filtered;
    # also skip if window just opened and spot feed is stale relative — N/A.

    fair_up = fair_up_prob(spot.mid, market.price_to_beat, market.asset)
    picked = _pick_side(fair_up, market)
    if picked is None:
        return None
    side, fair, ask = picked
    edge = fair - ask
    if edge < min_edge:
        return None

    move_bps = 1e4 * (spot.mid - market.price_to_beat) / market.price_to_beat
    # Size: more edge → slightly more size, capped
    contracts = 1
    if edge >= min_edge + 0.03:
        contracts = min(max_contracts, 2)
    if edge >= min_edge + 0.06:
        contracts = min(max_contracts, max(3, max_contracts // 2))
    if edge >= min_edge + 0.10:
        contracts = max_contracts
    contracts = max(1, min(max_contracts, contracts))

    direction = "UP" if side == "yes" else "DOWN"
    reason = (
        f"spot-lag {direction}: spot {spot.mid:.4g} vs beat "
        f"{market.price_to_beat:.4g} ({move_bps:+.1f}bps) via {spot.source}"
    )
    return TradePlan(
        market=market,
        spot=spot.mid,
        spot_source=spot.source,
        side=side,
        fair=fair,
        ask=ask,
        edge=edge,
        move_bps=move_bps,
        seconds_left=secs if secs is not None else 9999.0,
        contracts=contracts,
        reason=reason,
    )


def collect_plans(
    *,
    assets: list[str] | None = None,
    client=None,
    nearest_only: bool = True,
    min_edge: float | None = None,
) -> list[TradePlan]:
    markets = fetch_open_markets(assets, client=client)
    if nearest_only:
        markets = nearest_per_asset(markets)
    if not markets:
        return []
    spots = fetch_spots(sorted({m.asset for m in markets}))
    plans: list[TradePlan] = []
    for m in markets:
        spot = spots.get(m.asset)
        if spot is None:
            continue
        plan = plan_for_market(m, spot, min_edge=min_edge)
        if plan is not None:
            plans.append(plan)
    plans.sort(key=lambda p: -p.edge)
    return plans
