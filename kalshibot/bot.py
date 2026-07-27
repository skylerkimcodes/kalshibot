"""Crypto 15m spot-lag bot loop."""

from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv

from kalshibot.client import get_client, get_env_name
from kalshibot.crypto15m.edge import collect_plans
from kalshibot.crypto15m.orders import SessionRisk, execute_plan
from kalshibot.crypto15m.series import assets_from_env


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def run_once(
    *,
    dry_run: bool,
    risk: SessionRisk,
    min_edge: float | None,
    client,
) -> int:
    plans = collect_plans(client=client, min_edge=min_edge)
    if not plans:
        print("No +EV 15m plans this scan.", flush=True)
        return 0
    print(f"Found {len(plans)} plan(s):", flush=True)
    taken = 0
    for plan in plans:
        print(f"  {plan.label}", flush=True)
        print(f"    {plan.reason}", flush=True)
        if not risk.can_take(plan):
            print("    skip (risk / already traded)", flush=True)
            continue
        result = execute_plan(plan, dry_run=dry_run, risk=risk, client=client)
        if result.get("skipped"):
            print(f"    skip: {result.get('reason')}", flush=True)
            continue
        if dry_run:
            print(
                f"    DRY-RUN buy {plan.side} x{plan.contracts} @ {plan.ask:.4f}",
                flush=True,
            )
        else:
            print(
                f"    LIVE order id={result.get('order_id')} "
                f"fill={result.get('fill_count')} remaining={result.get('remaining_count')}",
                flush=True,
            )
        taken += 1
    return taken


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Kalshi crypto 15m Up/Down bot (spot-lag edge)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Send real orders (default is dry-run)",
    )
    parser.add_argument(
        "--loop",
        type=float,
        default=None,
        help="Seconds between scans (default: CRYPTO15M_LOOP_SECONDS or 5). 0 = once.",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=None,
        help="Min fair-ask edge (default: CRYPTO15M_MIN_EDGE or 0.04)",
    )
    parser.add_argument(
        "--allow-prod",
        action="store_true",
        help="Required together with --live when KALSHI_ENV=prod",
    )
    args = parser.parse_args(argv)

    env = get_env_name()
    dry_run = not args.live
    if args.live and env == "prod" and not args.allow_prod:
        print(
            "Refusing --live on prod without --allow-prod.",
            file=sys.stderr,
        )
        return 1

    loop = (
        args.loop
        if args.loop is not None
        else _env_float("CRYPTO15M_LOOP_SECONDS", 5.0)
    )
    min_edge = args.min_edge
    assets = assets_from_env()
    risk = SessionRisk.from_env()

    mode = "DRY-RUN" if dry_run else "LIVE"
    print(
        f"kalshibot crypto15m | env={env} | {mode} | assets={','.join(assets)}",
        flush=True,
    )
    client = get_client()

    if loop <= 0:
        run_once(dry_run=dry_run, risk=risk, min_edge=min_edge, client=client)
        return 0

    while True:
        try:
            run_once(dry_run=dry_run, risk=risk, min_edge=min_edge, client=client)
        except KeyboardInterrupt:
            print("Stopped.", flush=True)
            return 0
        except Exception as exc:
            print(f"Scan error: {exc}", flush=True)
        time.sleep(max(1.0, loop))


if __name__ == "__main__":
    raise SystemExit(main())
