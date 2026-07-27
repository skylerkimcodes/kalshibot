#!/usr/bin/env python3
"""Verify Kalshi API credentials by fetching account balance."""

from __future__ import annotations

import sys

from kalshibot.client import get_client


def main() -> int:
    try:
        client = get_client()
        balance = client.get_balance()
    except Exception as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 1

    cents = getattr(balance, "balance", None)
    if cents is None and isinstance(balance, dict):
        cents = balance.get("balance", 0)

    dollars = (cents or 0) / 100
    print("Connected to Kalshi API.")
    print(f"Balance: ${dollars:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
