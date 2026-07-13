"""Append extra instruments to the existing universe (prices_live.csv + mapping.json).

Adds the requested names to whatever universe you already fetched, with new
stock_ids continuing from the current max. Idempotent — skips any ticker already
present. After running, re-fit:  python -m calib.precompute   (both engines).

    python -m calib.add_tickers                       # default extra set
    python -m calib.add_tickers --years 20
    python -m calib.add_tickers --tickers "BABA,USDJPY=X:USDJPY:USD/JPY"

Default extra set: BABA (Alibaba), USDJPY=X (FX), 4419.T (Finatext, Tokyo).
Note: USDJPY / 4419.T get the equity engine settings unless you view them under
the ATR/deterministic engine — see engine_config.py.
"""
from __future__ import annotations
import os, sys, csv, json, time, argparse, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV = os.path.join(ROOT, "records/live/prices_live.csv")
MAP = os.path.join(ROOT, "records/live/mapping.json")

# (yahoo_symbol, display_ticker, name)
DEFAULT_EXTRAS = [
    ("BABA", "BABA", "Alibaba Group"),
    ("USDJPY=X", "USDJPY", "USD / Japanese Yen"),
    ("4419.T", "FINATEXT", "Finatext Holdings"),
]


def _yf_rows(yahoo, years, sleep):
    import yfinance as yf
    kw = dict(auto_adjust=False)
    if years:
        kw["start"] = (datetime.date.today() - datetime.timedelta(days=365 * years + 5)).isoformat()
    else:
        kw["period"] = "max"
    df = yf.Ticker(yahoo).history(**kw)
    if df is None or df.empty:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    out = []
    for ts, r in df.iterrows():
        try:
            o, h, l, c = float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"])
            v = float(r.get("Volume", 0) or 0)
        except (ValueError, KeyError, TypeError):
            continue
        if min(o, h, l, c) <= 0:
            continue
        out.append((ts.strftime("%Y-%m-%d"), o, h, l, c, v))
    time.sleep(sleep)
    return out


def _parse_tickers(arg):
    out = []
    for tok in arg.split(","):
        parts = tok.split(":")
        yahoo = parts[0].strip()
        disp = parts[1].strip() if len(parts) > 1 else yahoo.replace("=X", "").replace(".", "_")
        name = parts[2].strip() if len(parts) > 2 else disp
        out.append((yahoo, disp, name))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", help='comma list "YAHOO[:DISPLAY[:NAME]]"; default set if omitted')
    ap.add_argument("--years", type=int, default=25)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--min-bars", type=int, default=300)
    args = ap.parse_args()

    extras = _parse_tickers(args.tickers) if args.tickers else DEFAULT_EXTRAS
    mapping = json.load(open(MAP))
    have = {m["ticker"] for m in mapping} | {m.get("yahoo") for m in mapping}
    next_id = max((m["stock_id"] for m in mapping), default=0) + 1

    added = 0
    with open(CSV, "a", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        for yahoo, disp, name in extras:
            if disp in have or yahoo in have:
                print(f"  skip {disp} (already present)"); continue
            try:
                rows = _yf_rows(yahoo, args.years or None, args.sleep)
            except Exception as e:
                print(f"  {disp}: error {e}"); continue
            if not rows or len(rows) < args.min_bars:
                print(f"  {disp}: {0 if not rows else len(rows)} bars, skip"); continue
            for (d, o, h, l, c, v) in rows:
                w.writerow([next_id, d, o, h, l, c, v])
            mapping.append({"stock_id": next_id, "ticker": disp, "yahoo": yahoo,
                            "name": name, "sector": ""})
            print(f"  added {disp} ({yahoo}) as stock_id {next_id}: {len(rows)} bars")
            next_id += 1; added += 1

    json.dump(mapping, open(MAP, "w"), indent=2)
    print(f"\nadded {added} instruments. Now: python -m calib.precompute   "
          f"(and python -m calib.fetch_fundamentals --resume)")


if __name__ == "__main__":
    main()
