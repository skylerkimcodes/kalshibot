#!/usr/bin/env python3
"""CLI: place a single Kalshi event-contract order."""

from __future__ import annotations

import argparse
import sys

from kalshibot.client import get_env_name
from kalshibot.crypto15m.orders import place_order


def main() -> int:
    parser = argparse.ArgumentParser(description="Place a Kalshi limit order")
    parser.add_argument("ticker")
    parser.add_argument("--side", choices=("yes", "no"), default="yes")
    parser.add_argument("--action", choices=("buy", "sell"), default="buy")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--price", required=True)
    parser.add_argument(
        "--tif",
        default="good_till_canceled",
        choices=("good_till_canceled", "immediate_or_cancel", "fill_or_kill"),
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--allow-prod",
        action="store_true",
        help="Required with --live when KALSHI_ENV=prod",
    )
    args = parser.parse_args()

    env = get_env_name()
    if args.live and env == "prod" and not args.allow_prod:
        print("Refusing --live on prod without --allow-prod.", file=sys.stderr)
        return 1

    try:
        result = place_order(
            ticker=args.ticker,
            side=args.side,
            action=args.action,
            count=args.count,
            price=args.price,
            time_in_force=args.tif,
            dry_run=not args.live,
        )
    except Exception as exc:
        print(f"Order failed: {exc}", file=sys.stderr)
        return 1

    if not args.live:
        print(f"[{env}] DRY-RUN:")
        for k, v in result.items():
            print(f"  {k}: {v}")
        return 0

    print(
        f"[{env}] Order submitted: id={result.get('order_id')} "
        f"fill={result.get('fill_count')} remaining={result.get('remaining_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
