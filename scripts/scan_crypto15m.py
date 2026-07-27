#!/usr/bin/env python3
"""One-shot scan of open Kalshi crypto 15m markets + spot-lag edges."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from kalshibot.client import get_client, get_env_name
from kalshibot.crypto15m.edge import collect_plans, fair_up_prob, plan_for_market
from kalshibot.crypto15m.series import assets_from_env, fetch_open_markets, nearest_per_asset
from kalshibot.crypto15m.spot import fetch_spots


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Scan Kalshi KX*15M spot-lag edges")
    parser.add_argument(
        "--all-windows",
        action="store_true",
        help="Show every open window, not just nearest per asset",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=0.0,
        help="Only print plans with edge >= this (default 0 = show board)",
    )
    args = parser.parse_args()

    env = get_env_name()
    assets = assets_from_env()
    client = get_client()
    markets = fetch_open_markets(assets, client=client)
    if not args.all_windows:
        markets = nearest_per_asset(markets)

    print(f"[{env}] Open 15m markets with price-to-beat: {len(markets)}")
    if not markets:
        return 0

    spots = fetch_spots(sorted({m.asset for m in markets}))
    print()
    print(
        f"{'ASSET':<6} {'TICKER':<28} {'BEAT':>12} {'SPOT':>12} "
        f"{'UP%':>6} {'YASK':>6} {'NASK':>6} {'LEFT':>6}"
    )
    for m in markets:
        spot = spots.get(m.asset)
        mid = spot.mid if spot else float("nan")
        src = spot.source if spot else "-"
        fair = fair_up_prob(mid, m.price_to_beat, m.asset) if spot else float("nan")
        left = m.seconds_to_close
        left_s = f"{left:.0f}s" if left is not None else "?"
        print(
            f"{m.asset:<6} {m.ticker:<28} {m.price_to_beat:>12.4g} "
            f"{mid:>12.4g} {100 * fair:>5.1f}% "
            f"{(m.yes_ask or 0):>6.2f} {(m.no_ask or 0):>6.2f} {left_s:>6}  [{src}]"
        )

    print()
    plans = []
    for m in markets:
        spot = spots.get(m.asset)
        if spot is None:
            continue
        plan = plan_for_market(m, spot, min_edge=args.min_edge)
        if plan is not None:
            plans.append(plan)
    plans.sort(key=lambda p: -p.edge)

    if not plans:
        print("No plans clearing min-edge.")
        # still show best near-misses via collect_plans with lower floor
        near = collect_plans(client=client, nearest_only=not args.all_windows, min_edge=0.0)
        near = [p for p in near if p.edge > 0][:5]
        if near:
            print("Closest positive edges:")
            for p in near:
                print(f"  {p.label}")
        return 0

    print(f"+EV plans (>= {args.min_edge:g}):")
    for p in plans:
        print(f"  {p.label}")
        print(f"    {p.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
