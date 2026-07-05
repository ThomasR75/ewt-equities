# Elliott Wave Theory — a reproducible reliability test

A deterministic, point-in-time **Elliott-Wave (EW) signal generator** plus an
independent **reliability tester** that share one set of outcome rules, built to
answer a single question honestly: *do mechanical Elliott-Wave signals carry any
out-of-sample edge, and does a learned or LLM scenario-weigher improve them?*

**Headline result (this universe): no.** The engine has no statistically
detectable out-of-sample edge and no wave-counting skill. Its mildly positive raw
expectancy is market drift, and it underperforms buy-and-hold. Neither tuning the
most powerful parameter, a gradient-boosted weigher, nor a local-LLM weigher
changed that. Full write-up: [`paper/EWT_reliability_paper.pdf`](paper/EWT_reliability_paper.pdf).

This repo is deliberately structured so anyone can inspect the data and reproduce
every number.

## Key findings

- **No edge.** 68 out-of-sample setups (50 instruments, 1962–2026, annual walk-forward):
  win 26.5% (Wilson 95% [17.4, 38.0]), expectancy +0.35R (bootstrap 95% [−0.10, +0.83], p≈0.15 — not significant).
- **It's drift, not skill.** All profit is long setups (+0.89R); shorts lose (−0.79R).
  Forcing every setup long beats the engine (+0.63R), and vs buy-and-hold the engine's
  alpha is **−6.16R** (95% [−7.97, −4.46]). A volatility-matched random-entry control
  (+0.45R) beats the engine's timing too.
- **Tuning is a mirage.** A sensitivity parameter that looked profitable on one hold-out
  collapsed once *both* the parameter and the instruments were held out (obs +0.07R vs a
  +0.15R null, p=0.59) — a live demonstration of data-snooping.
- **Weighers can't rescue it.** A gradient-boosted tree's apparent AUC (0.674) is entirely
  the direction sign (drift); wave-structure features alone are at chance (AUC 0.53). The
  local-LLM weigher slightly *worsened* calibration.
- **The subjectivity is structural.** ~40% of reads have valid counts that disagree on
  direction, and the eventually-correct one is not identifiable at signal time from any
  feature (selection AUC 0.536; picking by EW fit-quality = 54.7%, worse than "always long" 68%).

## Repository layout

```
ewt/                 the engine (pivots, rule engine, enumerator, degrees, scenarios, setup, render, export)
tester.py            resolve one signal stream against outcomes
aggregate_tester.py  universe scorer: Wilson + bootstrap + random-direction null + calibration
batch_universe.py    walk-forward signal stream over a multi-stock CSV, selectable weigher
weighed_walkforward.py   single-ticker stream with a selectable weigher
sweep_sensitivity.py     pivot-sensitivity sweep with train/holdout (log or structural ATR mode)
build_training_table.py  per-candidate feature table for the learned weigher
train_weigher.py         train GBT / logistic weigher (isotonic-calibrated)
tests/               pytest suite (engine determinism, golden record, no-lookahead tripwire)
data/                anonymized OHLCV data (see below)
paper/               the write-up (build_paper.py -> EWT_reliability_paper.pdf) + figures
EXPERIMENT.md        experimental protocol
OLLAMA_SETUP.md      local-LLM weigher setup
RUN_LLM_ARM.md       exact commands to run + score the LLM arm and update the paper
EWT_Signal_Generator_Spec_v2.md   full design spec
```

`records/` (generated signal streams, sweeps, caches) is **git-ignored** — it is
fully reproducible from `data/` + the code via the commands below.

## Data

- `data/prices_anonymized.csv` — 50 anonymized instruments (`stock_id` only), 588,427
  daily OHLCV bars, 1962–2026. Anonymization (no names/dates-as-labels/absolute context to
  the analyst or LLM) is a deliberate anti-leakage control.
- `data/Test1.csv`, `data/SAMPLE_daily.csv`, `data/FLAT_demo.csv` — single-series fixtures/demos.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
pytest -q                                          # engine determinism + no-lookahead guards
```

## Reproduce the results

```bash
# 1. Deterministic signal stream over all 50 instruments (annual walk-forward)
python batch_universe.py data/prices_anonymized.csv --weigher deterministic \
    --stocks 1-50 --start 1962-01-01 --step 12M --out records/universe

# 2. Score it (Wilson + bootstrap + random-direction null + calibration)
python aggregate_tester.py records/universe --weigher deterministic

# 3. Pivot-sensitivity disjoint test (structural ATR mode)
python sweep_sensitivity.py data/prices_anonymized.csv --stocks 1-50 \
    --pivot-mode atr --scales 4,5,6 --step 12M --cutoff 2015-01-01

# 4. Learned weigher: build table, train, evaluate
python build_training_table.py data/prices_anonymized.csv --stocks 1-50 --out records/train_table.csv
python train_weigher.py records/train_table.csv

# 5. Local-LLM weigher arm (needs Ollama) — see RUN_LLM_ARM.md
# 6. Rebuild the paper
python paper/build_paper.py
```

## Caveats

Research artifact, not trading advice. One mechanization of EW (not discretionary
practice); annual cadence; frictionless; underpowered sample (n=68). Conclusions are
for this universe and this engine family. See the paper's Limitations section.
