# Experiment protocol — is an Elliott Wave signal generator reliable, and does an LLM weigher help?

This is the running lab notebook for the project. It records the question, the
method, the exact commands, and the results as they come in. Paste new results
into the slots at the bottom; the PDF (`paper/EWT_reliability_paper.pdf`) is the
polished write-up built from the same numbers.

## Question

1. **Reliability:** Does the deterministic mechanical Elliott-Wave engine produce
   tradeable signals — i.e. positive expectancy and a *calibrated* confidence
   (higher % → higher win rate, grade A > grade B)?
2. **LLM weigher:** Does replacing the deterministic scenario weigher with a
   local LLM (Ollama) improve expectancy and/or calibration, holding everything
   else fixed?

## Design (why it's a fair test)

- **Two projects, one seam.** The generator emits a frozen `SignalRecord` per
  `as_of`; the separate tester scores it against the *continuation* using the
  shared outcome rules (`ewt/outcome/rules.py`). Neither can drift from the other.
- **No lookahead.** Every signal at date T is a pure function of bars ≤ T
  (enforced by the as_of clamp + a tripwire test). The LLM sees only anonymized,
  relative structural features (no ticker/date/price), so it cannot use
  training-data recall.
- **Determinism.** The generator is deterministic; the LLM weigher runs at
  temperature 0 with a response cache, so a re-run is reproducible.
- **Held-out discipline.** The 6 original reference tickers were used to sanity-
  check structure recognition; the 50-stock anonymized universe is the scoring
  sample. Only the LLM weigher differs between the two arms — same data, same
  counts, same setup logic, same tester.

## Data

- `data/prices_anonymized.csv` — 50 instruments (`stock_id` 1–50), 588,427 daily
  bars, 1962–2026, anonymized (no names), clean (0 non-positive, 0 NaN).

## Engine (deterministic core, LLM off by default)

Pivots → bounded beam sweep (impulse/diagonal + zigzag/flat/triangle) → cardinal
+ guideline rules (scale-aware, log for large moves) → 3-degree nesting →
weighted scenarios (+ residual) → R/R-gated, degree-scaled setup → frozen JSON.
Milestones M1–M7; 36 unit tests incl. no-lookahead, determinism, golden record.

Post-backtest fixes applied: structural anchored entry, **log-scale R/R**,
**degree-scaled stops**, **degree-scaled horizon**, stable setup ids (dedupe).

## Commands

Deterministic arm (instant):
```
python batch_universe.py data\prices_anonymized.csv --weigher deterministic \
    --stocks 1-50 --start 1962-01-01 --step 12M --out records\universe
python aggregate_tester.py records\universe --weigher deterministic
```

LLM arm (Ollama running; qwen2.5:14b-instruct pulled):
```
python batch_universe.py data\prices_anonymized.csv --weigher ollama \
    --model qwen2.5:14b-instruct --stocks 1-50 --start 1962-01-01 --step 12M --out records\universe
python aggregate_tester.py records\universe --weigher ollama
```

Both `batch_universe` runs are resumable (re-run to continue). Scoring uses a
degree-scaled horizon so Cycle-degree calls get years, not months, to resolve.

## Metrics compared

Win rate, expectancy (mean R/trade), total R, and **calibration**: win-rate by
grade (does A beat B?) and by confidence bucket (is higher % more reliable?).

---

## RESULTS

### Deterministic — 50-stock, annual, full history (RECORDED)

- Distinct setups: **53** · outcomes: won 8 / lost 23 / invalidated 14 / expired 8
- Win rate **15.1%** · expectancy **−0.16 R/trade** · total **−8.3 R**
- Grade A: 0% win, −0.72 R · Grade B: 19% win, −0.03 R  (**A worse than B**)
- Confidence buckets: flat/non-monotonic (no calibration)
- Verdict: **no edge, inverted calibration.** Mechanics sound; bottleneck is the
  wave-count/weighting (direction) layer.

(Earlier 10-stock monthly 2019–2026: 10 setups, 1 win, −0.28 R — consistent.)

### LLM weigher (Ollama, qwen2.5:14b-instruct) — 50-stock (TO RUN)

Paste `aggregate_tester.py --weigher ollama` output here:

```
<paste output>
```

Fill in:
| metric | deterministic | ollama |
|---|---|---|
| distinct setups | 53 | |
| win rate | 15.1% | |
| expectancy (R) | −0.16 | |
| grade A win% / R | 0% / −0.72 | |
| grade B win% / R | 19% / −0.03 | |
| A beats B? | no | |
| confidence calibrated? | no | |

### Interpretation (to write after the LLM run)

- If ollama expectancy ≥ ~0 and A>B and confidence monotonic → the weigher adds
  calibration; mechanical counts + LLM weighting is worth pursuing.
- If ollama ≈ deterministic → bottleneck is the wave-counting itself; better
  weighting of weak counts cannot manufacture edge. Conclude mechanical EWT (this
  form) lacks predictive edge on this universe.

## Notes / provenance

- Every record is tagged `"weigher"` and carries `data_hash` + `engine_version`.
- LLM cache: `records/llm_cache/` (delete to force fresh calls).
- Sensitivities worth a later pass: pivot algorithm (§ open), TOL_K / RR_FLOOR,
  cadence (monthly vs annual), horizon scaling constant.

## Sensitivity switch: log vs structural (ATR)

The swing-sensitivity knob has two modes (`build_pivots(..., pivot_mode=)`):

- `log` (default): fixed % reversal per timeframe (D 6% / W 12% / M 20%),
  multiplied by `pivot_scale`. A % threshold means different things at
  different price levels, so pivot density varies wildly across names.
- `atr` (structural): threshold = ln(1 + `atr_k`·ATR/close), ATR on each
  timeframe's own bars. A single dimensionless `atr_k` (default 4.0) yields a
  volatility- and degree-appropriate threshold automatically — data-determined,
  not hand-picked. Empirically this normalises pivot density: across 4 sample
  stocks daily-pivot count ranged 188–1501 under `log` (~8×) vs 120–370 under
  `atr` (~3×).

Sweep the structural coefficient with the same train/holdout discipline:

    python sweep_sensitivity.py data/prices_anonymized.csv --stocks 1-12 \
        --pivot-mode atr --scales 3,4,5,6 --step 12M --cutoff 2015-01-01

In `atr` mode `--scales` is interpreted as `atr_k` values. The same flag pair
(`--pivot-mode` / `--atr-k`) exists on `build_training_table.py`. Tune on the
train fold, lock, then read the holdout — an edge that survives only at one
hand-picked coefficient is not real.
