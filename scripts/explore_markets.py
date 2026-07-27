#!/usr/bin/env python3
"""List open Kalshi events/markets with live bid/ask."""

from __future__ import annotations

import json
import sys

from kalshibot.client import get_client, load_response


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    client = get_client()

    data = load_response(
        client.get_events_without_preload_content(
            limit=limit,
            status="open",
            with_nested_markets=True,
        )
    )
    events = data.get("events") or []

    print(f"Open events: {len(events)}\n")
    first_ticker = None

    for event in events:
        et = event.get("event_ticker")
        title = event.get("title") or ""
        markets = event.get("markets") or []
        print(f"{et}  ({len(markets)} markets)")
        print(f"  {title}")

        for market in markets[:5]:
            ticker = market.get("ticker")
            if first_ticker is None:
                first_ticker = ticker
            label = (
                market.get("yes_sub_title")
                or market.get("subtitle")
                or market.get("title")
                or ""
            )
            bid = market.get("yes_bid_dollars")
            ask = market.get("yes_ask_dollars")
            vol = market.get("volume_24h_fp") or market.get("volume_fp") or "0"
            print(f"    {ticker}")
            print(f"      {label[:70]}")
            print(f"      YES bid/ask ${bid}/${ask}  vol={vol}")
        if len(markets) > 5:
            print(f"    … {len(markets) - 5} more")
        print()

    if first_ticker:
        book = load_response(
            client.get_market_orderbook_without_preload_content(
                ticker=first_ticker
            )
        )
        print(f"Order book: {first_ticker}")
        print(json.dumps(book, indent=2)[:1500])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
