# EW Calibration Platform

A local web app over the `ewt` engine to: tune the setup/grade calibration
factors live, browse the scan with historic technicals, run the wave **fitter**
from the browser, open a **zoomable** chart, score a calibration against the
reliability harness, and save factor **presets**. Universe-agnostic — works for
50 names or the full S&P 500.

## Quick start (current 50-name universe)

```bash
pip install -r requirements.txt          # flask (+ joblib, lightgbm for fitting)
python -m calib.precompute               # fit BOTH engines -> calib/states/*.pkl
python -m calib.app                      # http://127.0.0.1:5000
```

Viewing needs only flask (+pandas/numpy). **Running the fitter** (Run-fit button
or `precompute`) also needs `joblib` + `lightgbm` (the trained weigher). The
backtest needs the walk-forward cache (see below).

## Expand to the full S&P 500

`fetch_sp500.py` writes `records/live/prices_live.csv` (all names) +
`records/live/mapping.json` (ticker + company + sector). Constituents come from
Wikipedia (needs `lxml` or `bs4`; otherwise it uses the bundled
`calib/sp500_constituents.csv`, 503 names). Three data sources:

**Bulk ZIP (recommended for the full 500).** Stooq's per-request CSV endpoint
has a low daily quota, so for the whole universe download the US daily package
once from <https://stooq.com/db/h/> (e.g. `d_us_txt.zip`) in your browser, then:

```bash
python -m calib.fetch_sp500 --source zip --zip d_us_txt.zip --years 30
```

No quota, one file, fast. Works on the `.zip` or an extracted folder.

**Per-ticker Stooq (fine for small tests).** Uses a browser-like session and
caches raw CSVs under `calib/raw_stooq/`. If Stooq returns its "exceeded the
daily hits limit" page it stops and tells you; it also prints the raw response
for the first few failures so you can see what happened.

```bash
python -m calib.fetch_sp500 --limit 20          # quick test
```

**yfinance fallback.** If Stooq blocks you: `pip install yfinance`, then

```bash
python -m calib.fetch_sp500 --source yfinance --years 30
```

Symbols with dots map to Stooq's dash form (BRK.B → `brk-b.us`).

Then fit the universe — either from the command line or the dashboard:

```bash
python -m calib.precompute     # or click "Run fit ▶" in the app
```

Fitting is ~0.5 s/stock (~4–8 min for 500). The dashboard runs it as a
background job with a live progress count and reloads when done.

## Fundamentals (P/E, P/B, dividend yield)

A separate layer from the wave fit — refresh it any time without re-fitting.
Pulls per-stock trailing & forward P/E, price/book, EPS, market cap, and
dividend yield (trailing year, prior year, and forward) from yfinance:

```bash
python -m calib.fetch_fundamentals                # all names in the mapping
python -m calib.fetch_fundamentals --limit 20     # quick test
python -m calib.fetch_fundamentals --resume       # only fetch missing
```

This writes `records/live/fundamentals.json` (keyed by stock_id). Run it after
the universe exists (it reads `mapping.json`). In the dashboard, the table gains
sortable **P/E**, **P/B** and **Div%** columns and the detail panel shows the
full set (trailing/forward P/E and EPS, P/B, market cap, and dividend yield for
the last two years plus forward). The **Update fundamentals** button runs the
same fetch in the background and reloads — no wave re-fit. Needs `yfinance` in
the server env; the button disables itself and says so if it's missing.

## Engines (live toggle)

Two interchangeable reads of the same names, switchable from the **engine**
dropdown in the header (`calib/engine_config.py`):

- **GBT · log pivots** (`gbt_log`) — fixed-percentage pivots + the GBT-trained
  weigher. The canonical engine (needs joblib+lightgbm+sklearn to *fit*).
- **Deterministic · ATR pivots** (`atr_det`) — volatility-proportional ATR
  pivots + the deterministic weigher. Needs **no ML deps**; better suited to FX
  and low-vol names.

Build them with `python -m calib.precompute` (both) or
`python -m calib.precompute --engine atr_det`. Each writes
`calib/states/<engine>.pkl`; the server loads all of them and every request
(`/api/data`, `/api/chart`, `/api/calibrate`) takes an `engine` parameter.
Switching the dropdown refetches that engine's read and re-applies your current
calibration factors instantly.

## EWT rules button

The **EWT rules** button opens a panel listing the rule engine exactly as coded
(`/api/rules` → `calib/rules_catalog.py`), built from the *live* constants in
`ewt/rules/*` so the descriptions can't drift: the three cardinal filters, the
impulse/diagonal split, the corrective structures (zigzag / flat family /
triangles) with their thresholds and fib target bands, and the seven weighted
guideline scores — plus the log-vs-arithmetic scale rule.

## Adding instruments

Append extra tickers to the universe without a full re-fetch:

```bash
python -m calib.add_tickers                 # BABA, USDJPY=X, 4419.T (Finatext)
python -m calib.add_tickers --tickers "NVDA,BABA:BABA:Alibaba"
python -m calib.precompute                  # re-fit both engines incl. the new ids
python -m calib.fetch_fundamentals --resume # fundamentals for the new equities
```

## Using the dashboard

- **Calibration factors** — sliders for the R/R gate, grade thresholds, entry/
  stop geometry, invalidation tolerance, chase filter and fib target ratios.
  Moving one re-derives setups/grades instantly (no wave re-fit).
- **Table** — sortable on everything, including the technicals: distance vs
  SMA 20/50/100/200 (above/below), Z-scores (20/50/100d), 52-week range
  position, RSI(14), 50-day slope, realised vol. MA and Z windows are
  selectable dropdowns.
- **Run fit ▶** — re-run the wave fitter for the whole universe. **Re-fit ⟳**
  (in the zoom view) re-fits just the selected stock.
- **Chart** — the panel shows a mini chart; **click it** to open a large
  **zoomable** overlay (uPlot): mouse-wheel to zoom, drag to pan, double-click
  to reset, with the wave pivots/labels and entry/stop/target lines drawn on
  top. Daily / Weekly / Monthly toggle in both the panel and the overlay.
- **Backtest ▶** — score the current factors on the walk-forward harness.
- **Presets** — Save as… / load / Delete; built-ins included.

Chart data is served per-stock on demand (`/api/chart/<id>`) so the initial
`/api/data` stays small even with 500 names.

## Backtest — score a calibration against the reliability harness

Build the walk-forward cache once (resumable, two workers), then the
**Backtest ▶** button scores the current factors against it, reusing the study
machinery (`ewt/outcome/rules.py` + `aggregate_tester.py`'s dedupe / pivot-span
horizon / Wilson & bootstrap CIs / random-direction null), shown vs the default
baseline.

```bash
python -m calib.backtest_precompute 1-25    # worker A   (concurrent)
python -m calib.backtest_precompute 26-50   # worker B
python -m calib.backtest_precompute --merge # -> calib/backtest_state.pkl
python -m calib.backtest                    # headless: score default config
```

For a 500-name universe the walk-forward is heavy; run it over a subset of
`stock_id`s or leave it to the 50-name study set. The default config reproduces
the recorded result — expectancy ≈ −0.17 R, CI spanning zero, A not beating B:
**no detectable edge.**

## Files

| File | Role |
|---|---|
| `fetch_sp500.py` | Stooq downloader → prices_live.csv + mapping.json |
| `technicals.py` | historic technical measures |
| `fitter.py` | shared wave-fit (build one record; fit one / whole universe) |
| `precompute.py` | batch-fit the universe → calib_state.pkl |
| `backtest_precompute.py` / `backtest.py` | walk-forward cache + scorer |
| `app.py` | Flask server (calibrate / chart / fit / backtest / presets) |
| `index.html` + `app.js` | dashboard UI + uPlot zoom overlay |

> Research tool, not trading advice. Calibration explores the threshold
> surface; it does not create edge. Tuning and scoring on the same history
> overstates any apparent edge — a real edge must survive out-of-sample.
