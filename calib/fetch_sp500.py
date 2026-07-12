"""Fetch daily price history for the full S&P 500.

Two sources (Stooq default; yfinance fallback — Stooq has a low daily request
quota and can block non-browser clients):

    python -m calib.fetch_sp500 --limit 20                 # quick test (Stooq)
    python -m calib.fetch_sp500 --years 30                 # full run (Stooq)
    python -m calib.fetch_sp500 --source yfinance --years 30   # if Stooq blocks
    python -m calib.fetch_sp500 --source zip --zip d_us_txt.zip  # Stooq BULK (recommended for 500)

Bulk is best for the full universe: download the US daily package once from
https://stooq.com/db/h/  (e.g. d_us_txt.zip) in your browser, then point --zip
at the .zip (or its extracted folder). No per-request quota.

Writes:
    records/live/prices_live.csv   (stock_id,date,open,high,low,close,volume)
    records/live/mapping.json      ([{stock_id,ticker,name,sector}])

Constituents: Wikipedia if lxml/bs4 available, else bundled
calib/sp500_constituents.csv. Raw Stooq CSVs cache under calib/raw_stooq/ so
re-runs are resumable. If Stooq returns its "exceeded the daily hits limit"
page, wait a day or switch to --source yfinance.
"""
from __future__ import annotations
import os, sys, csv, json, time, random, argparse
import zipfile, io
import urllib.request, urllib.error, http.cookiejar

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "raw_stooq")
FALLBACK = os.path.join(HERE, "sp500_constituents.csv")
OUT_CSV = os.path.join(ROOT, "records/live/prices_live.csv")
OUT_MAP = os.path.join(ROOT, "records/live/mapping.json")
WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/csv,text/plain,*/*",
           "Accept-Language": "en-US,en;q=0.9", "Connection": "keep-alive"}

# one cookie-aware opener for the whole run (Stooq sets a cookie on first hit)
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
_DIAG_LEFT = 3  # print raw body for the first few failures


def stooq_symbol(ticker: str) -> str:
    return ticker.strip().lower().replace(".", "-").replace("/", "-") + ".us"


def load_constituents():
    try:
        import pandas as pd
        for flavor in ("lxml", "bs4"):
            try:
                tbl = pd.read_html(WIKI, flavor=flavor)[0]
                break
            except Exception:
                tbl = None
        if tbl is not None:
            cols = {c.lower(): c for c in tbl.columns}
            sym = cols.get("symbol"); nm = cols.get("security") or cols.get("company")
            sec = cols.get("gics sector") or cols.get("sector")
            rows = [(str(r[sym]).strip(), str(r[nm]).strip(), str(r[sec]).strip() if sec else "")
                    for _, r in tbl.iterrows()]
            if len(rows) > 400:
                print(f"constituents: {len(rows)} from Wikipedia")
                return rows
    except Exception as e:
        print(f"Wikipedia fetch failed ({e}); using bundled fallback")
    rows = []
    with open(FALLBACK, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((r["ticker"], r.get("name", ""), r.get("sector", "")))
    print(f"constituents: {len(rows)} from {FALLBACK}")
    return rows


class RateLimit(Exception):
    pass


def _stooq_download(ticker: str, sleep: float) -> str | None:
    """Return path to a cached valid CSV, or None. Raises RateLimit on quota."""
    global _DIAG_LEFT
    os.makedirs(RAW, exist_ok=True)
    cache = os.path.join(RAW, f"{ticker.replace('/', '-')}.csv")
    if os.path.exists(cache) and os.path.getsize(cache) > 200:
        return cache
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol(ticker)}&i=d"
    body = ""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with _OPENER.open(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "replace").strip()
            if body[:5] == "Date," and len(body) > 200:
                open(cache, "w", encoding="utf-8").write(body)
                time.sleep(sleep + random.uniform(0, 0.2))
                return cache
            low = body.lower()
            if "limit" in low or "przekro" in low or "exceed" in low:
                raise RateLimit(body[:120])
            time.sleep(sleep * 2)
        except (urllib.error.URLError, TimeoutError):
            time.sleep(sleep * 2 * (attempt + 1))
    if _DIAG_LEFT > 0 and body:
        _DIAG_LEFT -= 1
        print(f"      [stooq raw for {ticker}]: {body[:160]!r}")
    return None


def _stooq_rows(ticker, years, sleep):
    cache = _stooq_download(ticker, sleep)
    return _parse_csv(cache, years) if cache else None


def _yf_rows(ticker, years, sleep):
    import yfinance as yf
    import datetime as dt
    yt = ticker.strip().replace(".", "-").replace("/", "-")   # Yahoo: BRK.B -> BRK-B
    kw = dict(auto_adjust=False)
    if years:
        kw["start"] = (dt.date.today() - dt.timedelta(days=365 * years + 5)).isoformat()
    else:
        kw["period"] = "max"
    # Ticker.history() gives clean single-level columns (download() may return a MultiIndex)
    df = yf.Ticker(yt).history(**kw)
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


def _parse_csv(cache: str, years: int | None):
    import datetime as dt
    cutoff = None
    if years:
        cutoff = (dt.date.today() - dt.timedelta(days=365 * years + 5)).isoformat()
    rows = []
    with open(cache, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = r.get("Date")
            if not d or (cutoff and d < cutoff):
                continue
            try:
                o, h, l, c = float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"])
                v = float(r.get("Volume") or 0)
            except (ValueError, KeyError):
                continue
            if min(o, h, l, c) <= 0:
                continue
            rows.append((d, o, h, l, c, v))
    return rows



class ZipReader:
    """Reads Stooq's bulk US daily package (.zip or extracted dir).

    Bulk files are named e.g. `aapl.us.txt` with header
    <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
    and DATE as YYYYMMDD.
    """
    def __init__(self, path):
        self.zip = None
        self.index = {}   # 'aapl.us.txt' -> member/name
        if path.lower().endswith(".zip"):
            self.zip = zipfile.ZipFile(path)
            names = self.zip.namelist()
        else:
            names = []
            for root, _, files in os.walk(path):
                for fn in files:
                    names.append(os.path.join(root, fn))
        for n in names:
            base = os.path.basename(n).lower()
            if base.endswith(".us.txt"):
                self.index[base] = n
        print(f"bulk index: {len(self.index)} US tickers from {path}")

    def _open(self, name):
        if self.zip is not None:
            return io.TextIOWrapper(self.zip.open(name), encoding="utf-8", errors="replace")
        return open(name, encoding="utf-8", errors="replace")

    def rows(self, ticker, years, sleep):
        import datetime as dt
        key = ticker.strip().lower().replace(".", "-").replace("/", "-") + ".us.txt"
        name = self.index.get(key)
        if not name:
            return None
        cutoff = None
        if years:
            cutoff = (dt.date.today() - dt.timedelta(days=365 * years + 5)).strftime("%Y%m%d")
        out = []
        with self._open(name) as f:
            rd = csv.reader(f)
            header = next(rd, None)
            if not header:
                return None
            cols = {h.strip("<>").upper(): i for i, h in enumerate(header)}
            di, oi, hi, li, ci, vi = (cols.get("DATE"), cols.get("OPEN"), cols.get("HIGH"),
                                      cols.get("LOW"), cols.get("CLOSE"), cols.get("VOL"))
            if None in (di, oi, hi, li, ci):
                return None
            for r in rd:
                try:
                    d = r[di]
                    if cutoff and d < cutoff:
                        continue
                    o, h, l, c = float(r[oi]), float(r[hi]), float(r[li]), float(r[ci])
                    v = float(r[vi]) if vi is not None and vi < len(r) and r[vi] else 0.0
                except (ValueError, IndexError):
                    continue
                if min(o, h, l, c) <= 0:
                    continue
                iso = f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
                out.append((iso, o, h, l, c, v))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["stooq", "yfinance", "zip"], default="stooq")
    ap.add_argument("--zip", help="path to Stooq bulk .zip or extracted folder (for --source zip)")
    ap.add_argument("--years", type=int, default=30, help="history to keep (0 = all)")
    ap.add_argument("--limit", type=int, default=0, help="only first N tickers (testing)")
    ap.add_argument("--sleep", type=float, default=0.5, help="polite delay between requests")
    ap.add_argument("--min-bars", type=int, default=300)
    args = ap.parse_args()

    if args.source == "zip":
        if not args.zip:
            sys.exit("--source zip requires --zip <path to Stooq bulk .zip or folder>")
        get_rows = ZipReader(args.zip).rows
    elif args.source == "yfinance":
        get_rows = _yf_rows
    else:
        get_rows = _stooq_rows
    cons = load_constituents()
    if args.limit:
        cons = cons[:args.limit]
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

    mapping, sid, ok, skip = [], 0, 0, 0
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["stock_id", "date", "open", "high", "low", "close", "volume"])
        for i, (ticker, name, sector) in enumerate(cons, 1):
            try:
                rows = get_rows(ticker, args.years or None, args.sleep)
            except RateLimit as e:
                print(f"\nStooq daily request limit hit ({e}). Wait a day, or re-run with "
                      f"--source yfinance. Progress so far kept ({ok} stocks).")
                break
            except Exception as e:
                print(f"  [{i}/{len(cons)}] {ticker}: error {e}"); skip += 1; continue
            if not rows or len(rows) < args.min_bars:
                print(f"  [{i}/{len(cons)}] {ticker}: {0 if not rows else len(rows)} bars, skip"); skip += 1; continue
            sid += 1
            for (d, o, h, l, c, v) in rows:
                w.writerow([sid, d, o, h, l, c, v])
            mapping.append({"stock_id": sid, "ticker": ticker, "name": name, "sector": sector})
            ok += 1
            if i % 25 == 0 or i == len(cons):
                print(f"  [{i}/{len(cons)}] {ticker}: {len(rows)} bars  (ok={ok} skip={skip})")
    json.dump(mapping, open(OUT_MAP, "w"), indent=2)
    print(f"\nwrote {OUT_CSV} and {OUT_MAP}: {ok} stocks ({skip} skipped)")
    if ok:
        print("next:  python -m calib.precompute   (or the dashboard's Run-fit button)")


if __name__ == "__main__":
    main()
