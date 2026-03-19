"""
Crypto Watchlist Fetcher
Fetches all trading pairs from major exchanges and generates TradingView-compatible watchlist files.
Exchanges: Binance, Bybit, OKX, Bitget, Kraken, KuCoin
"""

import requests
import os
import json
from collections import defaultdict
from datetime import datetime

# ── Output directory ────────────────────────────────────────────────────────
OUTPUT_DIR = "watchlists"

# ── Quote categorisation ─────────────────────────────────────────────────────
USDT_VARIANTS  = {"USDT", "TUSD", "FDUSD"}
USDC_VARIANTS  = {"USDC", "DAI", "BUSD"}
FIAT_QUOTES    = {"USD", "EUR", "GBP", "AUD", "TRY"}
CRYPTO_QUOTES  = {"BTC", "ETH", "BNB", "OKB", "HT", "KCS"}

def categorise_quote(quote: str) -> str:
    q = quote.upper().strip()
    if q in USDT_VARIANTS:  return "usdt"
    if q in USDC_VARIANTS:  return "usdc"
    if q in FIAT_QUOTES:    return q.lower()
    if q in CRYPTO_QUOTES:  return q.lower()
    return "other"

# ── File helpers ─────────────────────────────────────────────────────────────
def write_watchlist(exchange: str, market: str, quote_cat: str, symbols: list[str]):
    """Write a sorted, deduplicated watchlist .txt file."""
    if not symbols:
        return
    folder = os.path.join(OUTPUT_DIR, exchange, market)
    os.makedirs(folder, exist_ok=True)
    filename = f"{exchange}_{market}_{quote_cat}.txt".lower().replace(" ", "_")
    filepath = os.path.join(folder, filename)
    with open(filepath, "w") as f:
        for sym in sorted(set(symbols)):
            f.write(sym + "\n")
    print(f"  ✅  {filepath}  ({len(set(symbols))} symbols)")

def build_tv_symbol(exchange_prefix: str, raw: str) -> str:
    """Return a TradingView-ready symbol string."""
    return f"{exchange_prefix}:{raw}"

def get_json(url: str, params: dict = None, headers: dict = None):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ⚠️  GET {url} failed: {e}")
        return None

# ════════════════════════════════════════════════════════════════════════════
# BINANCE
# ════════════════════════════════════════════════════════════════════════════
def fetch_binance():
    print("\n📥 BINANCE")

    # ── Spot ────────────────────────────────────────────────────────────────
    data = get_json("https://api.binance.com/api/v3/exchangeInfo")
    if data:
        buckets = defaultdict(list)
        for s in data["symbols"]:
            if s["status"] != "TRADING":
                continue
            quote_cat = categorise_quote(s["quoteAsset"])
            tv_sym = build_tv_symbol("BINANCE", s["symbol"])
            buckets[quote_cat].append(tv_sym)
        for cat, syms in buckets.items():
            write_watchlist("binance", "spot", cat, syms)

    # ── USDT-M Futures (linear perps + dated) ───────────────────────────────
    data = get_json("https://fapi.binance.com/fapi/v1/exchangeInfo")
    if data:
        perp_buckets  = defaultdict(list)
        dated_buckets = defaultdict(list)
        for s in data["symbols"]:
            if s["status"] != "TRADING":
                continue
            quote_cat   = categorise_quote(s["quoteAsset"])
            tv_sym      = build_tv_symbol("BINANCE", s["symbol"])
            c_type      = s.get("contractType", "")
            if c_type == "PERPETUAL":
                perp_buckets[quote_cat].append(tv_sym)
            elif c_type in ("CURRENT_QUARTER", "NEXT_QUARTER", "CURRENT_MONTH", "NEXT_MONTH"):
                dated_buckets[quote_cat].append(tv_sym)
        for cat, syms in perp_buckets.items():
            write_watchlist("binance", "perp_usdtm", cat, syms)
        for cat, syms in dated_buckets.items():
            write_watchlist("binance", "futures_usdtm", cat, syms)

    # ── Coin-M (inverse — settled in base asset) ────────────────────────────
    data = get_json("https://dapi.binance.com/dapi/v1/exchangeInfo")
    if data:
        perp_buckets  = defaultdict(list)
        dated_buckets = defaultdict(list)
        for s in data["symbols"]:
            if s["contractStatus"] != "TRADING":
                continue
            # Coin-M: categorise by BASE asset (settlement coin)
            base_cat = s["baseAsset"].upper()
            tv_sym   = build_tv_symbol("BINANCE", s["symbol"])
            c_type   = s.get("contractType", "")
            if c_type == "PERPETUAL":
                perp_buckets[base_cat.lower()].append(tv_sym)
            else:
                dated_buckets[base_cat.lower()].append(tv_sym)
        for cat, syms in perp_buckets.items():
            write_watchlist("binance", "perp_coinm", cat, syms)
        for cat, syms in dated_buckets.items():
            write_watchlist("binance", "futures_coinm", cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# BYBIT
# ════════════════════════════════════════════════════════════════════════════
def fetch_bybit():
    print("\n📥 BYBIT")
    BASE = "https://api.bybit.com/v5/market/instruments-info"

    category_map = {
        "spot":    ("spot",    "spot"),
        "linear":  ("linear",  "perp_linear"),   # USDT/USDC perps + dated
        "inverse": ("inverse", "perp_inverse"),   # coin-margined
        "option":  ("option",  "options"),
    }

    for cat_param, (_, market_label) in category_map.items():
        cursor = None
        all_symbols = []
        while True:
            params = {"category": cat_param, "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            data = get_json(BASE, params=params)
            if not data or data.get("retCode") != 0:
                break
            items = data["result"].get("list", [])
            all_symbols.extend(items)
            cursor = data["result"].get("nextPageCursor")
            if not cursor:
                break

        buckets       = defaultdict(list)
        perp_buckets  = defaultdict(list)
        dated_buckets = defaultdict(list)

        for s in all_symbols:
            status = s.get("status", s.get("lotSizeFilter", {}).get("status", ""))
            # Bybit uses "Trading" for active
            if s.get("status", "Trading") not in ("Trading", ""):
                pass  # include all for now; Bybit status field varies

            symbol = s.get("symbol", "")
            tv_sym = build_tv_symbol("BYBIT", symbol)

            if cat_param == "spot":
                quote = s.get("quoteCoin", "")
                buckets[categorise_quote(quote)].append(tv_sym)

            elif cat_param == "linear":
                quote    = s.get("settleCoin", s.get("quoteCoin", "USDT"))
                c_type   = s.get("contractType", "LinearPerpetual")
                cat_name = categorise_quote(quote)
                if "Perpetual" in c_type:
                    perp_buckets[cat_name].append(tv_sym)
                else:
                    dated_buckets[cat_name].append(tv_sym)

            elif cat_param == "inverse":
                base     = s.get("baseCoin", "BTC")
                c_type   = s.get("contractType", "InversePerpetual")
                cat_name = base.lower()
                if "Perpetual" in c_type:
                    perp_buckets[cat_name].append(tv_sym)
                else:
                    dated_buckets[cat_name].append(tv_sym)

            elif cat_param == "option":
                settle = s.get("settleCoin", "USDC")
                buckets[categorise_quote(settle)].append(tv_sym)

        for cat, syms in buckets.items():
            write_watchlist("bybit", market_label, cat, syms)
        for cat, syms in perp_buckets.items():
            write_watchlist("bybit", f"{market_label}_perp", cat, syms)
        for cat, syms in dated_buckets.items():
            write_watchlist("bybit", f"{market_label}_dated", cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# OKX
# ════════════════════════════════════════════════════════════════════════════
def fetch_okx():
    print("\n📥 OKX")
    BASE = "https://www.okx.com/api/v5/public/instruments"

    inst_types = {
        "SPOT":    "spot",
        "SWAP":    "perp",      # perpetuals
        "FUTURES": "futures",   # dated
        "OPTION":  "options",
    }

    for inst_type, market_label in inst_types.items():
        data = get_json(BASE, params={"instType": inst_type})
        if not data or data.get("code") != "0":
            continue

        buckets = defaultdict(list)
        for s in data["data"]:
            if s.get("state") != "live":
                continue

            inst_id  = s["instId"]   # e.g. BTC-USDT-SWAP
            tv_sym   = build_tv_symbol("OKX", inst_id.replace("-", ""))

            if inst_type == "SPOT":
                quote = s.get("quoteCcy", "")
                buckets[categorise_quote(quote)].append(tv_sym)

            elif inst_type in ("SWAP", "FUTURES"):
                settle   = s.get("settleCcy", "")
                ct_type  = s.get("ctType", "linear")   # linear / inverse
                sub_cat  = categorise_quote(settle) if ct_type == "linear" else s.get("ctValCcy", settle).lower()
                label    = f"{market_label}_{ct_type}"
                buckets[sub_cat].append(build_tv_symbol("OKX", inst_id.replace("-", "")))
                # Override bucket key with full label
                buckets[f"{sub_cat}|{label}"].append(build_tv_symbol("OKX", inst_id.replace("-", "")))

            elif inst_type == "OPTION":
                settle = s.get("settleCcy", "")
                buckets[categorise_quote(settle)].append(tv_sym)

        # For SWAP/FUTURES we stored both simple and labeled; write labeled
        if inst_type in ("SWAP", "FUTURES"):
            label_buckets = defaultdict(list)
            for key, syms in buckets.items():
                if "|" in key:
                    sub_cat, label = key.split("|", 1)
                    label_buckets[(label, sub_cat)].extend(syms)
            for (label, sub_cat), syms in label_buckets.items():
                write_watchlist("okx", label, sub_cat, syms)
        else:
            for cat, syms in buckets.items():
                if "|" not in cat:
                    write_watchlist("okx", market_label, cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# BITGET
# ════════════════════════════════════════════════════════════════════════════
def fetch_bitget():
    print("\n📥 BITGET")

    # ── Spot ────────────────────────────────────────────────────────────────
    data = get_json("https://api.bitget.com/api/v2/spot/public/symbols")
    if data and data.get("code") == "00000":
        buckets = defaultdict(list)
        for s in data["data"]:
            if s.get("status") != "online":
                continue
            quote = s.get("quoteCoin", "")
            tv_sym = build_tv_symbol("BITGET", s["symbol"])
            buckets[categorise_quote(quote)].append(tv_sym)
        for cat, syms in buckets.items():
            write_watchlist("bitget", "spot", cat, syms)

    # ── Futures (mix) ────────────────────────────────────────────────────────
    product_types = {
        "usdt-futures":  ("perp_linear", "usdt"),
        "usdc-futures":  ("perp_linear", "usdc"),
        "coin-futures":  ("perp_coinm",  None),      # base asset varies
        "susdt-futures": ("perp_demo",   "usdt"),     # demo/simulated — optional
    }

    for product_type, (market_label, forced_cat) in product_types.items():
        data = get_json(
            "https://api.bitget.com/api/v2/mix/market/contracts",
            params={"productType": product_type}
        )
        if not data or data.get("code") != "00000":
            continue
        buckets = defaultdict(list)
        for s in data["data"]:
            if s.get("symbolStatus") not in ("normal", ""):
                continue
            tv_sym = build_tv_symbol("BITGET", s["symbol"])
            if forced_cat:
                cat = forced_cat
            else:
                # coin-margined: categorise by base/settle coin
                settle = s.get("settleCoin", s.get("baseCoin", "BTC"))
                cat    = settle.lower()
            buckets[cat].append(tv_sym)
        for cat, syms in buckets.items():
            write_watchlist("bitget", market_label, cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# KRAKEN
# ════════════════════════════════════════════════════════════════════════════
def fetch_kraken():
    print("\n📥 KRAKEN")

    # ── Spot ────────────────────────────────────────────────────────────────
    data = get_json("https://api.kraken.com/0/public/AssetPairs")
    if data and not data.get("error"):
        buckets = defaultdict(list)
        for pair_name, s in data["result"].items():
            if s.get("status") != "online":
                continue
            # Use wsname for cleaner symbol e.g. XBT/USD
            wsname = s.get("wsname", pair_name)
            # Build TV symbol — Kraken uses KRAKEN prefix on TradingView
            tv_sym = build_tv_symbol("KRAKEN", wsname.replace("/", ""))
            quote  = s.get("quote", "")
            # Kraken uses Z prefix for fiat (ZUSD, ZEUR) and X for crypto (XXBT)
            clean_quote = quote.lstrip("XZ")
            # Map XBT → BTC
            if clean_quote == "XBT": clean_quote = "BTC"
            buckets[categorise_quote(clean_quote)].append(tv_sym)
        for cat, syms in buckets.items():
            write_watchlist("kraken", "spot", cat, syms)

    # ── Kraken Futures ───────────────────────────────────────────────────────
    data = get_json("https://futures.kraken.com/derivatives/api/v3/instruments")
    if data and data.get("result") == "success":
        perp_buckets  = defaultdict(list)
        dated_buckets = defaultdict(list)
        for s in data.get("instruments", []):
            if not s.get("tradeable"):
                continue
            symbol  = s.get("symbol", "")
            tv_sym  = build_tv_symbol("KRAKEN", symbol.upper())
            quote   = s.get("marginCurrency", "USD")
            cat     = categorise_quote(quote)
            f_type  = s.get("type", "")
            if "perpetual" in f_type.lower() or symbol.startswith("PF_"):
                perp_buckets[cat].append(tv_sym)
            else:
                dated_buckets[cat].append(tv_sym)
        for cat, syms in perp_buckets.items():
            write_watchlist("kraken", "perp", cat, syms)
        for cat, syms in dated_buckets.items():
            write_watchlist("kraken", "futures", cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# KUCOIN
# ════════════════════════════════════════════════════════════════════════════
def fetch_kucoin():
    print("\n📥 KUCOIN")

    # ── Spot ────────────────────────────────────────────────────────────────
    data = get_json("https://api.kucoin.com/api/v1/symbols")
    if data and data.get("code") == "200000":
        buckets = defaultdict(list)
        for s in data["data"]:
            if not s.get("enableTrading"):
                continue
            quote  = s.get("quoteCurrency", "")
            tv_sym = build_tv_symbol("KUCOIN", s["symbol"].replace("-", ""))
            buckets[categorise_quote(quote)].append(tv_sym)
        for cat, syms in buckets.items():
            write_watchlist("kucoin", "spot", cat, syms)

    # ── KuCoin Futures ───────────────────────────────────────────────────────
    data = get_json("https://api-futures.kucoin.com/api/v1/contracts/active")
    if data and data.get("code") == "200000":
        perp_buckets  = defaultdict(list)
        dated_buckets = defaultdict(list)
        for s in data["data"]:
            if s.get("status") != "Open":
                continue
            settle  = s.get("settleCurrency", "USDT")
            symbol  = s.get("symbol", "")
            tv_sym  = build_tv_symbol("KUCOIN", symbol)
            cat     = categorise_quote(settle)
            # KuCoin: expireDate is None for perps
            if s.get("expireDate") is None:
                perp_buckets[cat].append(tv_sym)
            else:
                dated_buckets[cat].append(tv_sym)
        for cat, syms in perp_buckets.items():
            write_watchlist("kucoin", "perp", cat, syms)
        for cat, syms in dated_buckets.items():
            write_watchlist("kucoin", "futures", cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════
def print_summary():
    total_files   = 0
    total_symbols = 0
    print("\n" + "═" * 60)
    print("📊  SUMMARY")
    print("═" * 60)
    for exchange in sorted(os.listdir(OUTPUT_DIR)):
        exc_path = os.path.join(OUTPUT_DIR, exchange)
        if not os.path.isdir(exc_path):
            continue
        exc_files = 0
        exc_syms  = 0
        for root, _, files in os.walk(exc_path):
            for f in files:
                if f.endswith(".txt"):
                    fpath = os.path.join(root, f)
                    with open(fpath) as fh:
                        lines = [l.strip() for l in fh if l.strip()]
                    exc_files  += 1
                    exc_syms   += len(lines)
        print(f"  {exchange.upper():<10}  {exc_files:>3} files   {exc_syms:>5} symbols")
        total_files   += exc_files
        total_symbols += exc_syms
    print("─" * 60)
    print(f"  {'TOTAL':<10}  {total_files:>3} files   {total_symbols:>5} symbols")
    print("═" * 60)


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"🚀  Starting watchlist fetch — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    fetch_binance()
    fetch_bybit()
    fetch_okx()
    fetch_bitget()
    fetch_kraken()
    fetch_kucoin()

    print_summary()
    print(f"\n✅  All watchlists saved to ./{OUTPUT_DIR}/")
