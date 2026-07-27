# kalshibot

Kalshi **crypto 15-minute** Up/Down bot (`KXBTC15M`, `KXETH15M`, …).

Edge: **spot-lag** — if live spot has already moved vs the window’s price-to-beat, buy Up (YES) or Down (NO) when Kalshi’s ask is still soft.

Default mode is **dry-run**. Pass `--live` to send orders.

## Layout

```text
kalshibot/
  client.py           # API auth
  bot.py              # scan loop
  crypto15m/
    series.py         # open KX{ASSET}15M discovery
    spot.py           # Binance / Coinbase mid
    edge.py           # spot-lag fair vs ask
    orders.py         # place order + session caps
scripts/
  connect.py
  scan_crypto15m.py
  place_order.py
  explore_markets.py
run_bot.sh / stop_bot.sh
```

## Setup

1. Create an API key at [demo.kalshi.co](https://demo.kalshi.co/account/profile) or [kalshi.com](https://kalshi.com/account/profile)
2. Save the PEM (e.g. `kalshi_demo_private_key.pem`)
3. Configure `.env`:

```bash
cp .env.example .env
```

```
KALSHI_API_KEY_ID=<your-key-id>
KALSHI_PRIVATE_KEY_PATH=./kalshi_demo_private_key.pem
KALSHI_ENV=demo
CRYPTO15M_ASSETS=BTC,ETH,SOL,XRP,DOGE,BNB,HYPE
CRYPTO15M_MIN_EDGE=0.04
CRYPTO15M_MAX_CONTRACTS=5
```

4. Install and verify:

```bash
pip3 install -r requirements.txt
PYTHONPATH=. python3 scripts/connect.py
PYTHONPATH=. python3 scripts/scan_crypto15m.py
```

## Run

```bash
./run_bot.sh                 # dry-run loop
./stop_bot.sh
tail -f logs/bot-*.log

./run_bot.sh --live          # live on demo
./run_bot.sh --live --allow-prod   # live on prod (requires KALSHI_ENV=prod)
```

One-shot:

```bash
PYTHONPATH=. python3 -m kalshibot --loop 0
PYTHONPATH=. python3 scripts/scan_crypto15m.py --min-edge 0.04
```

## Risk notes

- 15m crypto is noisy; spot (Binance/Coinbase) is a proxy for CF Benchmarks settlement.
- Session caps: `CRYPTO15M_MAX_SESSION_TRADES`, `CRYPTO15M_MAX_SPEND`.
- One trade per market ticker per session; IOC by default.
- No guaranteed edge — start dry-run, then tiny size.
