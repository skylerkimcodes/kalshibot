"""Order placement + session risk caps for crypto 15m."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

import requests

from kalshibot.client import HOSTS, get_client, get_env_name
from kalshibot.crypto15m.edge import TradePlan


def dollars_str(price: float | str) -> str:
    return f"{float(price):.4f}"


def count_str(count: int | float | str) -> str:
    return f"{float(count):.2f}"


def _book_side(side: str, action: str) -> str:
    if side == "yes":
        return "bid" if action == "buy" else "ask"
    return "ask" if action == "buy" else "bid"


def place_order(
    *,
    ticker: str,
    side: str,
    action: str = "buy",
    count: int,
    price: float | str,
    time_in_force: str = "immediate_or_cancel",
    dry_run: bool = True,
    client=None,
) -> dict:
    """Submit one limit order via Create Order V2."""
    side = side.lower()
    action = action.lower()
    if side not in {"yes", "no"}:
        raise ValueError("side must be 'yes' or 'no'")
    if action not in {"buy", "sell"}:
        raise ValueError("action must be 'buy' or 'sell'")
    if count < 1:
        raise ValueError("count must be >= 1")

    body = {
        "ticker": ticker,
        "client_order_id": str(uuid.uuid4()),
        "side": _book_side(side, action),
        "count": count_str(count),
        "price": dollars_str(price),
        "time_in_force": time_in_force,
        "self_trade_prevention_type": "taker_at_cross",
    }
    if dry_run:
        return {"dry_run": True, "legacy_side": side, "legacy_action": action, **body}

    if client is None:
        client = get_client()
    env = get_env_name()
    path = "/trade-api/v2/portfolio/events/orders"
    base = HOSTS[env].replace("/trade-api/v2", "")
    headers = client.kalshi_auth.create_auth_headers("POST", path)
    headers["Content-Type"] = "application/json"
    resp = requests.post(base + path, headers=headers, json=body, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Order failed ({resp.status_code}): {resp.text}")
    return resp.json()


@dataclass
class SessionRisk:
    max_trades: int = 20
    max_spend: float = 50.0
    traded_tickers: set[str] = field(default_factory=set)
    trades: int = 0
    spend: float = 0.0

    @classmethod
    def from_env(cls) -> "SessionRisk":
        return cls(
            max_trades=int(os.getenv("CRYPTO15M_MAX_SESSION_TRADES") or 20),
            max_spend=float(os.getenv("CRYPTO15M_MAX_SPEND") or 50),
        )

    def can_take(self, plan: TradePlan) -> bool:
        if plan.market.ticker in self.traded_tickers:
            return False
        if self.trades >= self.max_trades:
            return False
        cost = plan.ask * plan.contracts
        if self.spend + cost > self.max_spend + 1e-9:
            return False
        return True

    def record(self, plan: TradePlan) -> None:
        self.traded_tickers.add(plan.market.ticker)
        self.trades += 1
        self.spend += plan.ask * plan.contracts


def execute_plan(
    plan: TradePlan,
    *,
    dry_run: bool = True,
    risk: SessionRisk | None = None,
    client=None,
) -> dict:
    if risk is not None and not risk.can_take(plan):
        return {"skipped": True, "reason": "session risk / already traded ticker"}
    result = place_order(
        ticker=plan.market.ticker,
        side=plan.side,
        action="buy",
        count=plan.contracts,
        price=plan.ask,
        time_in_force="immediate_or_cancel",
        dry_run=dry_run,
        client=client,
    )
    if risk is not None and not result.get("skipped"):
        risk.record(plan)
    return result
