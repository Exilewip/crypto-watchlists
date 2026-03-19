"""
generate_index.py
Reads all generated watchlist .txt files and produces docs/index.html
for GitHub Pages deployment.
"""

import os
from collections import defaultdict
from datetime import datetime, timezone

WATCHLISTS_DIR = "watchlists"
DOCS_DIR       = "docs"

EXCHANGE_META = {
    "binance": {"label": "Binance",  "color": "#F0B90B", "emoji": "🟡"},
    "bybit":   {"label": "Bybit",    "color": "#F7A600", "emoji": "🟠"},
    "okx":     {"label": "OKX",      "color": "#FFFFFF", "emoji": "⚪"},
    "bitget":  {"label": "Bitget",   "color": "#00C5CE", "emoji": "🔵"},
    "kraken":  {"label": "Kraken",   "color": "#5741D9", "emoji": "🟣"},
    "kucoin":  {"label": "KuCoin",   "color": "#23AF91", "emoji": "🟢"},
}

MARKET_LABELS = {
    "spot":              "Spot",
    "perp_usdtm":        "Perp USDT-M",
    "perp_usdtm_perp":   "Perp USDT-M",
    "perp_coinm":        "Perp Coin-M",
    "perp_coinm_perp":   "Perp Coin-M",
    "futures_usdtm":     "Futures USDT-M",
    "futures_coinm":     "Futures Coin-M",
    "perp_linear":       "Perp Linear",
    "perp_linear_perp":  "Perp Linear",
    "perp_linear_dated": "Futures Linear",
    "perp_inverse":      "Perp Inverse",
    "perp_inverse_perp": "Perp Inverse",
    "perp_inverse_dated":"Futures Inverse",
    "perp":              "Perpetuals",
    "futures":           "Futures",
    "options":           "Options",
    "perp_demo":         "Perp Demo",
    "perp_future":       "Perp Future",
    "perp_linear_linear":"Perp Linear",
    "perp_future_linear":"Futures Linear",
    "perp_future_inverse":"Futures Inverse",
}

QUOTE_LABELS = {
    "usdt":  "USDT",
    "usdc":  "USDC",
    "btc":   "BTC",
    "eth":   "ETH",
    "bnb":   "BNB",
    "okb":   "OKB",
    "usd":   "USD",
    "eur":   "EUR",
    "gbp":   "GBP",
    "aud":   "AUD",
    "try":   "TRY",
    "other": "Other",
}

def scan_watchlists():
    """Returns {exchange: {market: [(quote_cat, filepath, count)]}}"""
    tree = defaultdict(lambda: defaultdict(list))
    if not os.path.isdir(WATCHLISTS_DIR):
        return tree
    for exchange in sorted(os.listdir(WATCHLISTS_DIR)):
        exc_path = os.path.join(WATCHLISTS_DIR, exchange)
        if not os.path.isdir(exc_path):
            continue
        for market in sorted(os.listdir(exc_path)):
            mkt_path = os.path.join(exc_path, market)
            if not os.path.isdir(mkt_path):
                continue
            for fname in sorted(os.listdir(mkt_path)):
                if not fname.endswith(".txt"):
                    continue
                fpath = os.path.join(mkt_path, fname)
                with open(fpath) as f:
                    count = sum(1 for l in f if l.strip())
                # Extract quote category from filename
                # pattern: exchange_market_quote.txt
                parts = fname.replace(".txt", "").split("_")
                quote_cat = parts[-1] if parts else "other"
                rel_path  = fpath.replace("\\", "/")
                tree[exchange][market].append((quote_cat, rel_path, count))
    return tree

def market_label(market: str) -> str:
    return MARKET_LABELS.get(market, market.replace("_", " ").title())

def quote_label(q: str) -> str:
    return QUOTE_LABELS.get(q.lower(), q.upper())

def generate_html(tree: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Count totals
    total_files = sum(len(files) for exc in tree.values() for files in exc.values())
    total_syms  = sum(c for exc in tree.values() for files in exc.values() for _, _, c in files)

    cards_html = ""
    for exchange, markets in tree.items():
        meta   = EXCHANGE_META.get(exchange, {"label": exchange.title(), "color": "#888", "emoji": "🔘"})
        total_exc_files = sum(len(f) for f in markets.values())
        total_exc_syms  = sum(c for files in markets.values() for _, _, c in files)

        markets_html = ""
        for market, files in markets.items():
            badges_html = ""
            for quote_cat, rel_path, count in files:
                dl_url = rel_path   # relative path works on GitHub Pages
                ql     = quote_label(quote_cat)
                badges_html += f"""
                <a href="{dl_url}" download class="badge" title="Download {ql} watchlist ({count} symbols)">
                  <span class="badge-quote">{ql}</span>
                  <span class="badge-count">{count}</span>
                  <span class="badge-dl">↓</span>
                </a>"""

            markets_html += f"""
            <div class="market">
              <div class="market-name">{market_label(market)}</div>
              <div class="badges">{badges_html}</div>
            </div>"""

        cards_html += f"""
        <div class="card">
          <div class="card-header" style="border-left: 4px solid {meta['color']}">
            <span class="card-emoji">{meta['emoji']}</span>
            <span class="card-title">{meta['label']}</span>
            <span class="card-stats">{total_exc_files} lists · {total_exc_syms:,} symbols</span>
          </div>
          <div class="card-body">{markets_html}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Crypto Watchlists for TradingView</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:        #0a0a0f;
      --surface:   #111118;
      --border:    #1e1e2e;
      --text:      #e2e2f0;
      --muted:     #6b6b8a;
      --accent:    #7c6af7;
      --accent2:   #f7c96a;
      --radius:    10px;
    }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      min-height: 100vh;
      padding: 0 0 80px;
    }}

    /* ── Hero ── */
    .hero {{
      padding: 64px 24px 48px;
      text-align: center;
      background: radial-gradient(ellipse 80% 60% at 50% 0%, #1a1040 0%, transparent 70%);
      border-bottom: 1px solid var(--border);
    }}
    .hero-eyebrow {{
      font-family: 'Space Mono', monospace;
      font-size: 11px;
      letter-spacing: 3px;
      color: var(--accent);
      text-transform: uppercase;
      margin-bottom: 16px;
    }}
    .hero h1 {{
      font-size: clamp(28px, 5vw, 52px);
      font-weight: 600;
      line-height: 1.1;
      margin-bottom: 16px;
    }}
    .hero h1 em {{
      font-style: normal;
      color: var(--accent2);
    }}
    .hero-sub {{
      color: var(--muted);
      font-size: 16px;
      max-width: 520px;
      margin: 0 auto 32px;
      line-height: 1.6;
    }}
    .hero-stats {{
      display: inline-flex;
      gap: 32px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 50px;
      padding: 12px 28px;
      font-family: 'Space Mono', monospace;
      font-size: 13px;
    }}
    .hero-stats span {{ color: var(--accent2); }}

    /* ── How to use ── */
    .howto {{
      max-width: 860px;
      margin: 40px auto;
      padding: 0 24px;
    }}
    .howto-steps {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
    }}
    .step {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
    }}
    .step-num {{
      font-family: 'Space Mono', monospace;
      font-size: 11px;
      color: var(--accent);
      margin-bottom: 8px;
    }}
    .step p {{ font-size: 14px; color: var(--muted); line-height: 1.5; }}
    .step strong {{ color: var(--text); }}

    /* ── Grid ── */
    .grid {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 24px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
    }}

    /* ── Card ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
    }}
    .card-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 16px 20px;
      background: #0d0d14;
    }}
    .card-emoji  {{ font-size: 18px; }}
    .card-title  {{ font-weight: 600; font-size: 17px; flex: 1; }}
    .card-stats  {{ font-family: 'Space Mono', monospace; font-size: 10px; color: var(--muted); }}

    .card-body {{ padding: 12px 16px; display: flex; flex-direction: column; gap: 12px; }}

    .market-name {{
      font-family: 'Space Mono', monospace;
      font-size: 10px;
      letter-spacing: 1px;
      color: var(--muted);
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 8px; }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: #16161f;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 13px;
      text-decoration: none;
      color: var(--text);
      transition: all .15s ease;
      cursor: pointer;
    }}
    .badge:hover {{
      border-color: var(--accent);
      background: #1c1a30;
      transform: translateY(-1px);
    }}
    .badge-quote {{ font-weight: 600; }}
    .badge-count {{
      font-family: 'Space Mono', monospace;
      font-size: 11px;
      color: var(--muted);
    }}
    .badge-dl {{ color: var(--accent2); font-size: 12px; }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      margin-top: 60px;
      font-family: 'Space Mono', monospace;
      font-size: 11px;
      color: var(--muted);
    }}
    .updated {{ color: var(--accent); }}
  </style>
</head>
<body>

<div class="hero">
  <div class="hero-eyebrow">Free · Updated daily · TradingView ready</div>
  <h1>Crypto Watchlists<br>for <em>TradingView</em></h1>
  <p class="hero-sub">Download ready-to-import watchlists for every major exchange — Spot, Perpetuals, Futures, Coin-M — sorted by quote currency.</p>
  <div class="hero-stats">
    {total_files} watchlists &nbsp;·&nbsp; <span>{total_syms:,}</span> symbols &nbsp;·&nbsp; 6 exchanges
  </div>
</div>

<div class="howto">
  <div class="howto-steps">
    <div class="step">
      <div class="step-num">01 — DOWNLOAD</div>
      <p><strong>Click any badge</strong> below to download the <strong>.txt</strong> watchlist file you need.</p>
    </div>
    <div class="step">
      <div class="step-num">02 — IMPORT</div>
      <p>In TradingView, open the <strong>Watchlist panel</strong>, click ··· → <strong>Import watchlist</strong>.</p>
    </div>
    <div class="step">
      <div class="step-num">03 — TRADE</div>
      <p>Your watchlist is instantly populated with all <strong>active symbols</strong> from that exchange.</p>
    </div>
  </div>
</div>

<div class="grid">
  {cards_html}
</div>

<div class="footer">
  <p>Updated automatically every day at 02:00 UTC &nbsp;·&nbsp; <span class="updated">Last run: {now}</span></p>
  <p style="margin-top:8px">Data sourced from official public exchange APIs · Not financial advice</p>
</div>

</body>
</html>"""


if __name__ == "__main__":
    os.makedirs(DOCS_DIR, exist_ok=True)
    tree = scan_watchlists()
    html = generate_html(tree)
    out  = os.path.join(DOCS_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    total = sum(len(files) for exc in tree.values() for files in exc.values())
    print(f"✅  index.html généré → {out}  ({total} watchlists référencées)")
