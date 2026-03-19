"""
Crypto Watchlist Fetcher — CCXT edition
Fetches all trading pairs from major exchanges and generates TradingView-compatible watchlist files.
Exchanges: Binance, Bybit, OKX, Bitget, Kraken, KuCoin
"""

import ccxt
import os
from collections import defaultdict
from datetime import datetime

# ── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = "watchlists"

# ── Quote categorisation ──────────────────────────────────────────────────────
USDT_VARIANTS = {"USDT", "TUSD", "FDUSD"}
USDC_VARIANTS = {"USDC", "DAI", "BUSD"}
FIAT_QUOTES   = {"USD", "EUR", "GBP", "AUD", "TRY"}
CRYPTO_QUOTES = {"BTC", "ETH", "BNB", "OKB", "HT", "KCS"}

def categorise_quote(quote: str) -> str:
    q = quote.upper().strip()
    if q in USDT_VARIANTS: return "usdt"
    if q in USDC_VARIANTS: return "usdc"
    if q in FIAT_QUOTES:   return q.lower()
    if q in CRYPTO_QUOTES: return q.lower()
    return "other"

# ── TradingView exchange prefixes ─────────────────────────────────────────────
TV_PREFIX = {
    "binance": "BINANCE",
    "bybit":   "BYBIT",
    "okx":     "OKX",
    "bitget":  "BITGET",
    "kraken":  "KRAKEN",
    "kucoin":  "KUCOIN",
}

# ── File helpers ──────────────────────────────────────────────────────────────
def write_watchlist(exchange: str, market: str, quote_cat: str, symbols: list):
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

def tv_symbol(exchange: str, base: str, quote: str, raw_symbol: str = None) -> str:
    """Build a TradingView-compatible symbol string."""
    prefix = TV_PREFIX.get(exchange, exchange.upper())
    # Use raw symbol if provided (for futures/perps with special naming)
    if raw_symbol:
        # Remove / and : separators, keep alphanumeric + _ .
        clean = raw_symbol.replace("/", "").replace(":", "").replace("-", "")
        return f"{prefix}:{clean}"
    return f"{prefix}:{base}{quote}"

# ── Generic market fetcher ────────────────────────────────────────────────────
def load_markets(exchange_id: str, options: dict = None) -> dict | None:
    """Instantiate a CCXT exchange and load its markets."""
    try:
        exchange_class = getattr(ccxt, exchange_id)
        config = {
            "enableRateLimit": True,
            "options": options or {},
        }
        exchange = exchange_class(config)
        markets = exchange.load_markets()
        print(f"  📡  {exchange_id}: {len(markets)} markets loaded")
        return markets
    except Exception as e:
        print(f"  ⚠️  Failed to load {exchange_id}: {e}")
        return None

# ── Market type helpers ───────────────────────────────────────────────────────
def is_active(m: dict) -> bool:
    return m.get("active", True)  # default True if not specified

def market_type(m: dict) -> str:
    """Return normalised market type string."""
    t = m.get("type", "spot")
    if m.get("linear")  and m.get("swap"):   return "perp_linear"
    if m.get("inverse") and m.get("swap"):   return "perp_inverse"
    if m.get("linear")  and m.get("future"): return "futures_linear"
    if m.get("inverse") and m.get("future"): return "futures_inverse"
    if m.get("option"):                       return "option"
    if t == "spot":                           return "spot"
    if t == "swap":
        return "perp_linear" if m.get("linear") else "perp_inverse"
    if t == "future":
        return "futures_linear" if m.get("linear") else "futures_inverse"
    return t

# ════════════════════════════════════════════════════════════════════════════
# BINANCE
# ════════════════════════════════════════════════════════════════════════════
def fetch_binance():
    print("\n📥 BINANCE")

    # CCXT fetches binance.com with proper headers — no geo-block issues
    markets = load_markets("binance", options={
        "defaultType": "spot",
        "fetchMarkets": ["spot", "linear", "inverse"],
    })
    if not markets:
        return

    buckets = defaultdict(lambda: defaultdict(list))

    for symbol, m in markets.items():
        if not is_active(m):
            continue
        base  = m.get("base", "")
        quote = m.get("quote", "")
        settle= m.get("settle", quote)
        mtype = market_type(m)
        qcat  = categorise_quote(quote)

        # Build TV symbol — CCXT uses BASE/QUOTE:SETTLE format
        raw = m.get("id", symbol)
        tvsym = tv_symbol("binance", base, quote, raw)

        if mtype == "spot":
            buckets["spot"][qcat].append(tvsym)
        elif mtype == "perp_linear":
            buckets["perp_usdtm"][categorise_quote(settle)].append(tvsym)
        elif mtype == "perp_inverse":
            # Coin-M: categorise by base asset (settlement coin)
            buckets["perp_coinm"][base.lower()].append(tvsym)
        elif mtype == "futures_linear":
            buckets["futures_usdtm"][categorise_quote(settle)].append(tvsym)
        elif mtype == "futures_inverse":
            buckets["futures_coinm"][base.lower()].append(tvsym)

    for mkt, cats in buckets.items():
        for cat, syms in cats.items():
            write_watchlist("binance", mkt, cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# BYBIT
# ════════════════════════════════════════════════════════════════════════════
def fetch_bybit():
    print("\n📥 BYBIT")

    markets = load_markets("bybit", options={
        "fetchMarkets": ["spot", "linear", "inverse", "option"],
    })
    if not markets:
        return

    buckets = defaultdict(lambda: defaultdict(list))

    for symbol, m in markets.items():
        if not is_active(m):
            continue
        base   = m.get("base", "")
        quote  = m.get("quote", "")
        settle = m.get("settle", quote)
        mtype  = market_type(m)
        raw    = m.get("id", symbol)
        tvsym  = tv_symbol("bybit", base, quote, raw)

        if mtype == "spot":
            buckets["spot"][categorise_quote(quote)].append(tvsym)
        elif mtype == "perp_linear":
            buckets["perp_linear"][categorise_quote(settle)].append(tvsym)
        elif mtype == "perp_inverse":
            buckets["perp_inverse"][base.lower()].append(tvsym)
        elif mtype == "futures_linear":
            buckets["futures_linear"][categorise_quote(settle)].append(tvsym)
        elif mtype == "futures_inverse":
            buckets["futures_inverse"][base.lower()].append(tvsym)
        elif mtype == "option":
            buckets["options"][categorise_quote(settle)].append(tvsym)

    for mkt, cats in buckets.items():
        for cat, syms in cats.items():
            write_watchlist("bybit", mkt, cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# OKX
# ════════════════════════════════════════════════════════════════════════════
def fetch_okx():
    print("\n📥 OKX")

    markets = load_markets("okx")
    if not markets:
        return

    buckets = defaultdict(lambda: defaultdict(list))

    for symbol, m in markets.items():
        if not is_active(m):
            continue
        base   = m.get("base", "")
        quote  = m.get("quote", "")
        settle = m.get("settle", quote)
        mtype  = market_type(m)
        raw    = m.get("id", symbol)
        tvsym  = tv_symbol("okx", base, quote, raw)

        if mtype == "spot":
            buckets["spot"][categorise_quote(quote)].append(tvsym)
        elif mtype == "perp_linear":
            buckets["perp_linear"][categorise_quote(settle)].append(tvsym)
        elif mtype == "perp_inverse":
            buckets["perp_inverse"][base.lower()].append(tvsym)
        elif mtype == "futures_linear":
            buckets["futures_linear"][categorise_quote(settle)].append(tvsym)
        elif mtype == "futures_inverse":
            buckets["futures_inverse"][base.lower()].append(tvsym)
        elif mtype == "option":
            buckets["options"][categorise_quote(settle)].append(tvsym)

    for mkt, cats in buckets.items():
        for cat, syms in cats.items():
            write_watchlist("okx", mkt, cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# BITGET
# ════════════════════════════════════════════════════════════════════════════
def fetch_bitget():
    print("\n📥 BITGET")

    markets = load_markets("bitget")
    if not markets:
        return

    buckets = defaultdict(lambda: defaultdict(list))

    for symbol, m in markets.items():
        if not is_active(m):
            continue
        base   = m.get("base", "")
        quote  = m.get("quote", "")
        settle = m.get("settle", quote)
        mtype  = market_type(m)
        raw    = m.get("id", symbol)
        tvsym  = tv_symbol("bitget", base, quote, raw)

        if mtype == "spot":
            buckets["spot"][categorise_quote(quote)].append(tvsym)
        elif mtype == "perp_linear":
            buckets["perp_linear"][categorise_quote(settle)].append(tvsym)
        elif mtype == "perp_inverse":
            buckets["perp_inverse"][base.lower()].append(tvsym)
        elif mtype in ("futures_linear", "futures_inverse"):
            buckets[mtype][categorise_quote(settle)].append(tvsym)

    for mkt, cats in buckets.items():
        for cat, syms in cats.items():
            write_watchlist("bitget", mkt, cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# KRAKEN
# ════════════════════════════════════════════════════════════════════════════
def fetch_kraken():
    print("\n📥 KRAKEN")

    markets = load_markets("kraken")
    if not markets:
        return

    buckets = defaultdict(lambda: defaultdict(list))

    for symbol, m in markets.items():
        if not is_active(m):
            continue
        base  = m.get("base", "")
        quote = m.get("quote", "")
        mtype = market_type(m)
        raw   = m.get("id", symbol)
        tvsym = tv_symbol("kraken", base, quote, raw)
        qcat  = categorise_quote(quote)

        if mtype == "spot":
            buckets["spot"][qcat].append(tvsym)
        elif mtype in ("perp_linear", "perp_inverse"):
            buckets["perp"][qcat].append(tvsym)
        elif mtype in ("futures_linear", "futures_inverse"):
            buckets["futures"][qcat].append(tvsym)

    for mkt, cats in buckets.items():
        for cat, syms in cats.items():
            write_watchlist("kraken", mkt, cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# KUCOIN
# ════════════════════════════════════════════════════════════════════════════
def fetch_kucoin():
    print("\n📥 KUCOIN")

    # KuCoin spot
    markets_spot = load_markets("kucoin")
    if markets_spot:
        buckets = defaultdict(list)
        for symbol, m in markets_spot.items():
            if not is_active(m) or market_type(m) != "spot":
                continue
            base  = m.get("base", "")
            quote = m.get("quote", "")
            raw   = m.get("id", symbol)
            tvsym = tv_symbol("kucoin", base, quote, raw)
            buckets[categorise_quote(quote)].append(tvsym)
        for cat, syms in buckets.items():
            write_watchlist("kucoin", "spot", cat, syms)

    # KuCoin Futures (separate exchange instance)
    markets_fut = load_markets("kucoinfutures")
    if markets_fut:
        perp_b  = defaultdict(list)
        dated_b = defaultdict(list)
        for symbol, m in markets_fut.items():
            if not is_active(m):
                continue
            base   = m.get("base", "")
            quote  = m.get("quote", "")
            settle = m.get("settle", quote)
            raw    = m.get("id", symbol)
            tvsym  = tv_symbol("kucoin", base, quote, raw)
            cat    = categorise_quote(settle)
            mtype  = market_type(m)
            if "perp" in mtype or m.get("swap"):
                perp_b[cat].append(tvsym)
            else:
                dated_b[cat].append(tvsym)
        for cat, syms in perp_b.items():
            write_watchlist("kucoin", "perp", cat, syms)
        for cat, syms in dated_b.items():
            write_watchlist("kucoin", "futures", cat, syms)


# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════
def print_summary():
    total_files = total_syms = 0
    print("\n" + "═" * 60)
    print("📊  SUMMARY")
    print("═" * 60)
    for exchange in sorted(os.listdir(OUTPUT_DIR)):
        exc_path = os.path.join(OUTPUT_DIR, exchange)
        if not os.path.isdir(exc_path):
            continue
        ef = es = 0
        for root, _, files in os.walk(exc_path):
            for f in files:
                if f.endswith(".txt"):
                    with open(os.path.join(root, f)) as fh:
                        lines = [l.strip() for l in fh if l.strip()]
                    ef += 1
                    es += len(lines)
        print(f"  {exchange.upper():<12}  {ef:>3} files   {es:>6} symbols")
        total_files += ef
        total_syms  += es
    print("─" * 60)
    print(f"  {'TOTAL':<12}  {total_files:>3} files   {total_syms:>6} symbols")
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
