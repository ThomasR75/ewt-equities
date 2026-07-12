"""Fetch per-stock fundamentals from yfinance -> records/live/fundamentals.json.

A separate layer from the wave fit: refresh it any time without re-fitting.
Per ticker it records trailing & forward P/E, price/book, EPS, market cap, and
dividend yield for the trailing year, the prior year (from the dividend
history) and forward (from the declared rate).

    python -m calib.fetch_fundamentals               # all names in mapping.json
    python -m calib.fetch_fundamentals --limit 20    # quick test
    python -m calib.fetch_fundamentals --resume      # skip ones already fetched

Output:
    records/live/fundamentals.json
    {"as_of": "YYYY-MM-DD", "updated": iso, "n": N,
     "data": {"<stock_id>": {pe, pe_fwd, pb, eps, eps_fwd, mktcap, price,
                             dy_ttm, dy_prev, dy_fwd, div_ttm, div_prev}}}
"""
from __future__ import annotations
import os, sys, json, time, argparse, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAP = os.path.join(ROOT, "records/live/mapping.json")
OUT = os.path.join(ROOT, "records/live/fundamentals.json")


def yahoo_sym(t: str) -> str:
    return t.strip().replace(".", "-").replace("/", "-")


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        import math
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def fetch_one(ticker: str) -> dict | None:
    import yfinance as yf
    import pandas as pd
    t = yf.Ticker(yahoo_sym(ticker))
    try:
        info = t.get_info() or {}
    except Exception:
        try:
            info = t.info or {}
        except Exception:
            info = {}
    price = _num(info.get("currentPrice") or info.get("regularMarketPrice")
                 or info.get("previousClose"))

    # dividend history -> trailing-year and prior-year sums
    div_ttm = div_prev = None
    try:
        divs = t.dividends
        if divs is not None and len(divs):
            idx = divs.index
            try:
                idx = idx.tz_localize(None)
            except (TypeError, AttributeError):
                pass
            s = pd.Series(divs.values, index=pd.to_datetime(idx))
            now = pd.Timestamp.today().normalize()
            y1 = now - pd.Timedelta(days=365)
            y2 = now - pd.Timedelta(days=730)
            div_ttm = float(s[(s.index > y1) & (s.index <= now)].sum())
            div_prev = float(s[(s.index > y2) & (s.index <= y1)].sum())
    except Exception:
        pass

    dy = lambda d: round(d / price * 100, 2) if (d is not None and price) else None
    div_rate = _num(info.get("dividendRate"))
    rec = {
        "pe": _num(info.get("trailingPE")),
        "pe_fwd": _num(info.get("forwardPE")),
        "pb": _num(info.get("priceToBook")),
        "eps": _num(info.get("trailingEps")),
        "eps_fwd": _num(info.get("forwardEps")),
        "mktcap": _num(info.get("marketCap")),
        "price": price,
        "div_ttm": round(div_ttm, 4) if div_ttm is not None else None,
        "div_prev": round(div_prev, 4) if div_prev is not None else None,
        "dy_ttm": dy(div_ttm),
        "dy_prev": dy(div_prev),
        "dy_fwd": round(div_rate / price * 100, 2) if (div_rate and price) else None,
    }
    if all(v is None for k, v in rec.items() if k != "price"):
        return None
    return rec


def fetch_all(on_step=None, resume=False, sleep=0.3, ids=None):
    """Fetch fundamentals for every stock in the mapping. Writes OUT; returns data."""
    mapping = json.load(open(MAP))
    if ids is not None:
        ids = set(int(i) for i in ids)
        mapping = [m for m in mapping if m["stock_id"] in ids]
    data = {}
    if resume and os.path.exists(OUT):
        try:
            data = json.load(open(OUT)).get("data", {})
        except Exception:
            data = {}
    total = len(mapping)
    for i, m in enumerate(mapping, 1):
        sid = str(m["stock_id"])
        if resume and sid in data:
            if on_step:
                on_step(i, total)
            continue
        try:
            rec = fetch_one(m["ticker"])
            if rec is not None:
                data[sid] = rec
        except Exception as e:
            print(f"  {m['ticker']}: {e}")
        time.sleep(sleep)
        if on_step:
            on_step(i, total)
        if i % 50 == 0:
            _write(data)
    _write(data)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--resume", action="store_true", help="keep existing entries, only fetch missing")
    args = ap.parse_args()

    ids = None
    if args.limit:
        ids = [m["stock_id"] for m in json.load(open(MAP))[:args.limit]]
    def step(i, total):
        if i % 25 == 0 or i == total:
            print(f"  [{i}/{total}] fetched")
    data = fetch_all(on_step=step, resume=args.resume, sleep=args.sleep, ids=ids)
    print(f"\nwrote {OUT}: {len(data)} stocks with fundamentals")


def _write(data):
    payload = {"as_of": datetime.date.today().isoformat(),
               "updated": datetime.datetime.now().isoformat(timespec="seconds"),
               "n": len(data), "data": data}
    json.dump(payload, open(OUT, "w"))


if __name__ == "__main__":
    main()
