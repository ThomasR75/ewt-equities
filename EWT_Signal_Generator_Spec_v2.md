# Elliott Wave Signal Generator — Design Spec (v2)
**Status:** blueprint to build against · **Scope locked:** full 3-degree nested report **with charts**, mechanical/deterministic core, auto-enumerator engine, daily-CSV-in, **plus a frozen machine-readable export for a separate reliability-tester project.**

This document is the build target. It defines module layout, data schemas, the fork-vs-write map, the rule engine, the pruning strategy, the **Project-1 ↔ tester boundary**, and the build sequence. It is deliberately concrete: schemas list fields, components list signatures. Where a decision is still open it is flagged in §17.

### What changed from v1 → v2
1. **Full informative output is kept** — charts, scenario table, trade plan, "one level that matters," in-report scorecard all ship in v1. Nothing in §14 is cut.
2. **LLM seams stay deferred.** Every interpretive seam (`LabelingEngine`, `ScenarioWeigher`, `NarrativeWriter`) ships as a **deterministic placeholder**. No model calls, no network, in the shipped generator.
3. **New `export/` layer + frozen `SignalRecord` JSON** — the contract a separate project consumes to judge reliability. See **§5 (schema)** and **§15 (boundary & handoff)**.
4. **No-lookahead is now an invariant**, with an optional **walk-forward** run mode so the tester can get a time-series of historical signals from one CSV. See **§15.3–15.4**.
5. **Scorecard role clarified** — in Project 1 it is *point-in-time status display inside the report* (reads only bars ≤ as_of); it is **not** the reliability judge. The tester is authoritative for reliability. Shared outcome definitions live in **§18** so both agree.
6. **Determinism guarantee** — same input bytes + same `engine_version` ⇒ byte-identical `SignalRecord`. No wall-clock, no RNG, no network in the core.

---

## 1. Purpose & guiding principle
Reproduce the analysis style in the reference reports: a per-ticker Elliott Wave read across three nested degrees, expressed as weighted scenarios plus a graded, R/R-gated trade setup with a frozen scorecard — **and** emit, alongside the human report, a self-contained signal record that a separate tester project can score against the continuation of the price series.

**Core principle (non-negotiable):** the engine never claims *the* count. It surfaces **ranked candidate counts with confidence**, exactly as the scenarios-with-weights format already does. This is the only intellectually honest output — automated wave counting is inherently subjective. Ambiguity must degrade gracefully into a low-conviction read (weight flows to the residual "no clean structure" bucket), never a false-confident one.

**Second principle:** every price comparison is **scale-aware**. Each leg carries both arithmetic and log magnitude; each rule declares which scale it validates on. Multi-decade moves are judged on log. This single discipline is what the human reviewer kept catching in the reference reports.

**Third principle (v2):** **point-in-time integrity.** A signal generated as of date `T` is a pure function of bars with timestamp ≤ `T` and the pinned `engine_version`. This is what makes the separate reliability study valid; it is enforced, not assumed (§15.3).

---

## 2. What v1 produces (report anatomy → component)
| Report element | Produced by | Deterministic in v1? |
|---|---|---|
| Header (`TICKER — Co (init/update, date, price)`) | `report.assemble` | Yes |
| Headline thesis | `narrative` (template) | Template stub; LLM later |
| Prior calls / scorecard (in-report status) | `scorecard` | Yes (point-in-time, ≤ as_of) |
| 3 nested charts (monthly/weekly/daily) | `render` | Yes (given counts) |
| Scenarios table (path, weight, key levels, invalidation) | `scenario` | Levels/invalidation: yes. Weights: from scores |
| Trade-plan table (ID, grade, dir, entry, stop, T1/T2, R/R) | `setup` + `grade` | Yes |
| "The one level that matters next" | `levels.pivot_level` | Yes (highest-confluence bull/bear pivot) |
| **Machine-readable `SignalRecord` (JSON)** | **`export.signal`** | **Yes (the tester contract)** |
| **Per-ticker append-only `signals.jsonl`** | **`export.log`** | **Yes** |
| Fundamentals overlay | out of scope for v1 | No (optional later, web-sourced) |

Two output *channels*, same run: **(a)** the human report (`report.md` + PNG charts) and **(b)** the frozen `SignalRecord` JSON. Channel (b) is the only thing the tester reads.

---

## 3. Pipeline
```
CSV(daily)
  → ingest        load, validate, adjust → Bars(daily)        [assert no bar ts > as_of]
  → resample      → Bars(weekly), Bars(monthly)   [lin + log cols, is_partial flag]
  → pivots        per timeframe, degree-tuned sensitivity → PivotSeries
  → enumerate     skip-tuple sweep, multi-anchor, bidirectional → raw WavePatterns
  → classify      match to structure grammar → Count candidates
  → rules         cardinal filters (hard) + guideline scores (soft) → RuleReport
  → prune         beam search, top-M per (anchor,degree,type)
  → nest          reconcile daily ⊂ weekly ⊂ monthly → ranked Count triples
  → fib           projections + retraces (correct scale) → FibLevel, ConfluenceZone
  → scenarios     top-N counts → Scenario[] + residual bucket, weighted
  → setup         entry/stop/targets → R/R → grade → "is it a setup?" gate
  → scorecard     load prior, re-evaluate status vs bars ≤ as_of, persist (frozen levels)
  → review        adversarial re-check (scale, extremes, R/R floor, weight sanity)
  → render        3 charts + report scaffold
  → assemble      final human report
  → export        SignalRecord JSON + append signals.jsonl   ← tester handoff
```
A single run produces the report **and** the export. In `--walk-forward` mode the loop runs once per step over history, emitting JSON each step (reports/charts optional per step — see §15.4).

---

## 4. Module layout
```
ewt/
  io/
    ingest.py          # CSV → Bars; schema validation, split/div adjust, as_of clamp
    resample.py        # daily → weekly/monthly; lin+log; is_partial (built only from ≤ as_of)
    walkforward.py     # WRITE (v2): iterate as_of over history, no-lookahead slicing
  pivots/
    monowave.py        # FORK (adapt): atomic swing detection
    series.py          # PivotSeries container, multi-scale
  enumerate/
    options.py         # FORK: WaveOptionsGenerator (skip-tuple + prune + dedup)
    sweep.py           # WRITE: multi-anchor, bidirectional orchestration
  structure/
    pattern.py         # FORK (adapt): WavePattern container + check_rule dispatch
    count.py           # WRITE: Count, structure classification
    grammar.py         # WRITE: production rules (impulse/zigzag/flat/triangle/diagonal)
  rules/
    base.py            # WRITE: Rule ABC, scale-aware
    cardinal.py        # WRITE: the 3 inviolable rules (port logic, lin+log)
    guidelines.py      # WRITE: alternation, channeling, equality, fib bands, volume
    fib.py             # PORT (taew): per-wave fibonacci checks
  degree/
    nesting.py         # WRITE: cross-timeframe consistency + reconciliation
  levels/
    fibonacci.py       # WRITE: projections, retraces, scale-aware
    confluence.py      # WRITE: clustering of levels into zones
    pivot_level.py     # WRITE: "one level that matters" selector
  signal/
    scenario.py        # WRITE: scenario synthesis + weighting (deterministic placeholder)
    setup.py           # WRITE: entry/stop/targets, R/R, setup gate
    grade.py           # WRITE: grading rubric
    scorecard.py       # WRITE: SQLite persistence, frozen state machine (in-report status)
  outcome/
    rules.py           # WRITE (v2): canonical outcome-resolution logic (§18), pure, shared spec
  review/
    adversarial.py     # WRITE: second-pass sanity checks (deterministic)
  render/
    charts.py          # WRITE: mplfinance annotated charts + zoom inset
    report.py          # WRITE: scaffold assembly
    narrative.py       # WRITE: template fill (LLM swap-in later, off by default)
  export/
    signal.py          # WRITE (v2): Count/Scenario/Setup → SignalRecord JSON
    log.py             # WRITE (v2): append-only signals.jsonl per ticker
    schema.py          # WRITE (v2): versioned schema + validation
  engine.py            # WRITE: orchestration; stamps engine_version, data_hash
  cli.py               # entrypoint: analyze <ticker> <csv> [--walk-forward ...] [--no-report]
```

---

## 5. Core data schemas
Plain dataclasses. These are the contracts between stages; the seam between mechanical and deferred runs through `Count`. The seam between **Project 1 and the tester** runs through `SignalRecord`.
```
Bars
  tf: "D"|"W"|"M"
  df: DataFrame[open, high, low, close, volume,
                log_open, log_high, log_low, log_close]
  index: DatetimeIndex
  is_partial: bool          # last bar still forming at as_of
  as_of: Timestamp          # v2: every Bars knows its cutoff; nothing past it exists

Pivot
  idx, ts, price, log_price, kind: "H"|"L", prominence

PivotSeries
  tf, pivots: list[Pivot]   # strictly alternating H/L

Leg                         # directed move between two pivots — the unit rules see
  start, end: Pivot; dir: +1|-1
  mag_lin, mag_log: float; bars: int
  def retrace_of(other, scale) -> float
  def ext_of(other, scale)    -> float

Count                       # one labeling hypothesis  ← MECHANICAL/DEFERRED SEAM
  tf
  structure: "impulse"|"leading_diag"|"ending_diag"
           | "zigzag"|"flat"|"triangle"|"combination"
  degree: "Subminuette"...."Supercycle"
  legs: list[Leg]; labels: list[str]
  score: float              # guideline fit 0..1
  rule_report: RuleReport

RuleReport
  cardinal_pass: bool
  cardinal_detail: dict[str,bool]
  guideline_scores: dict[str,float]
  scale_used: dict[str,"lin"|"log"]

FibLevel
  ratio, kind: "retrace"|"projection", scale, anchor_legs, price, label

ConfluenceZone
  lo, hi, members: list[FibLevel], significance

Scenario
  rank, path, weight              # 0..1, scenarios sum to 1 incl. residual
  key_levels: list[float]; invalidation: str
  primary_count: Count|None       # None for residual "no clean structure"

Setup
  id: str                         # TICKER-YYYYMMDD-N
  grade: "A+"|"A"|"B"|None        # None = "not a setup"
  direction: "long"|"short"
  entry, entry_type: "limit"|"stop"|"market"
  stop, t1, t2, rr
  invalidation_level: float; invalidation_rule: str
  status: "untriggered"|"active"|"won"|"lost"|"invalidated"|"expired"
  frozen: dict                    # entry/stop/targets/grade — immutable after issue
  issued: date; horizon_bars: int

ScorecardRow                      # persisted; one per issued setup (in-report status)
  id, ticker, issued, frozen(json), status, resolved, pnl_r
```

### 5.1 SignalRecord — the tester contract (v2)
The frozen, self-contained JSON emitted every run. Self-describing: a tester needs nothing but this file plus the continuation bars to score the call.
```
SignalRecord
  schema_version: int               # bump on any breaking field change
  engine_version: str               # git describe / semver of the generator
  generated_at: iso8601             # wall clock, FYI only — NOT used in logic

  data:
    ticker: str
    source: str                     # filename / provider id
    data_hash: str                  # sha256 of the exact bars ≤ as_of used
    timeframe_base: "D"
    as_of: date                     # last bar used (decision time)
    as_of_is_partial: bool
    first_bar: date; bar_count: int
    last_price: float

  signal: "long"|"short"|"none"
  grade: "A+"|"A"|"B"|null
  confidence_pct: float             # weight of the lead scenario — "the %"

  setup:                            # null when signal == "none"
    id; direction; entry; entry_type; stop; t1; t2; rr
    invalidation_level; invalidation_rule
    horizon_bars; issued

  scenarios: [                      # full distribution, sums to 1.0 incl residual
    { rank, path, weight, key_levels, invalidation, is_residual } ]

  pivot_level: float                # "the one level that matters next"

  counts: [                         # audit/replay: the labeling behind the call
    { tf, structure, degree, labels,
      pivots: [{ts, price, kind}], score, scale_used } ]

  artifacts:                        # human-output cross-refs (tester may ignore)
    report: "records/<TICKER>/<as_of>/report.md"
    charts: ["...-monthly.png","...-weekly.png","...-daily.png"]
```
`data_hash` + `engine_version` are mandatory: a reliability number is meaningless unless you can say *which generator* on *exactly which input* produced each signal. Two runs with matching `data_hash` and `engine_version` MUST yield byte-identical records (minus `generated_at`).

---

## 6. Fork vs write — where forked code is wrapped
Adopt the permissively-licensed enumeration/rule skeleton (ElliottWaveAnalyzer); write everything that makes the reports distinctive. Concrete placement:
- `pivots/monowave.py` — **fork & adapt** the MonoWave micro-trend logic; add `log_price` to every emitted pivot.
- `enumerate/options.py` — **fork** WaveOptionsGenerator (skip-tuple generation, illegal-combo prune, dedup-by-set). Used as-is.
- `structure/pattern.py` — **fork & adapt** WavePattern + `check_rule` dispatch; container only.
- `enumerate/sweep.py` — **write**, wraps the forked `find_impulsive_wave` in a **multi-anchor, bidirectional** loop and adds `find_corrective_wave` (the upstream stub). This is the critical fix: upstream scans one anchor, up-only.
- `rules/cardinal.py`, `rules/guidelines.py` — **write fresh**, porting the standard math onto scale-aware `Leg`s. Upstream rules are arithmetic-only — a latent bug for multi-decade charts.
- `rules/fib.py` — **port** taew's per-wave fibonacci-band checks (peer-reviewed reference) onto our legs.
- `degree/`, `levels/`, `signal/`, `outcome/`, `review/`, `render/`, `export/` — **write fresh**; no open-source analog exists.

Carry the upstream LICENSE for forked files; keep forked code isolated under its original-style API so it can be swapped without touching our layers.

---

## 7. Rule engine
### Cardinal rules (hard filters — port, scale-aware)
Applied to *partial* parses during enumeration so illegal branches die early.
1. **W2 retraces strictly < 100% of W1** — `w2.retrace_of(w1, scale) < 1.0` (a full retrace is itself invalidation, not a pass).
2. **W3 not shortest of {1,3,5}** — compare `mag` on declared scale; canonical check is percentage/log, with arithmetic as a near-always corroborator.
3. **W4 no overlap with W1 territory** — except diagonals, where overlap is *permitted* (this is precisely what distinguishes a diagonal from an impulse).

### Guidelines (soft scores 0..1)
Alternation (W2 vs W4 differ in form/depth/time), channeling, wave equality (W5≈W1 when W3 extends), fib bands (W2≈.5/.618, W3≈1.618×W1, retraces at .382/.5/.618), volume confirmation on W3. Each contributes to `Count.score`; the literature treats multi-timeframe + fib + volume as the primary subjectivity-reducers, so they are core, not polish.

### Rule object shape
```
class Rule(ABC):
    name: str
    kind: "cardinal"|"guideline"
    scale: "lin"|"log"|"auto"   # auto = log if span > threshold
    def check(self, count) -> bool | float
```

---

## 8. Pruning strategy (the make-or-break performance problem)
Naïve enumeration explodes: upstream `up_to=15` is already ~759k combos **per anchor, single degree, one pattern type**. Multiply by anchors × 3 degrees × ~6 pattern types and it is intractable. Controls, in order of impact:
1. **Cardinal rules as early termination** — reject partial parses mid-construction, not after.
2. **Eligible-pivot capping** — at each degree only the top-K pivots by `prominence` can be sub-wave boundaries.
3. **Beam search** — keep top-M partial counts by running score; drop the rest.
4. **Anchor restriction** — anchors only at significant local extrema, not every bar.
5. **Degree recursion cap** — exactly the 3 target degrees, no deeper.
6. **Memoization/dedup** — set-based, inherited from upstream (different skip-tuples → identical pattern).

K, M, and prominence thresholds are tunable config; defaults set empirically against the reference tickers in §16. **Walk-forward note:** total backtest cost ≈ per-run cost × number of steps, so the §8 budget is also the backtest budget — see §15.4 for the incremental-recompute mitigation.

---

## 9. Multi-degree nesting
Enumerate independently per timeframe, then **reconcile triples** (monthly, weekly, daily): score each triple by how well degree boundaries align in time and price (a monthly Primary-[A] terminus should coincide, within tolerance, with a completed daily sub-structure). Output the top nested triples. This produces the "daily Minor 5 ⊂ weekly Primary [A] ⊂ monthly Cycle II" reads. No existing tool does this — it is core differentiated value.

**Known limitation:** resampling *up* caps monthly history at the daily file's start. Deep secular framing (e.g. SPX monthly to 1932) needs an optional long-range monthly file — a later input, flagged not silently wrong.

---

## 10. Scenario weighting (deterministic in v1)
Top-N nested triples → scenarios. Weight from normalized guideline scores, then renormalize with a **residual "no clean structure" bucket** that always exists and absorbs ambiguity (when top counts all score poorly, residual weight rises). Weights sum to 1.

v1 ships the **score-derived deterministic weigher only**. The `ScenarioWeigher` interface exists so a learned/LLM weigher can drop in later, but it is **off by default and not part of the shipped generator**. Honest expectation: deterministic weights will reproduce the top *counts* well but not the nuanced reference *splits* (e.g. 38/37/25). That is acceptable and intended — the tester (separate project) measures exactly how well-calibrated these weights are, which is the point.

---

## 11. Setup synthesis + grading
For the lead scenario, derive entry (limit/stop into structure), stop (beyond the invalidation pivot), targets (confluence zones), then:

**R/R gate:** if `rr < 2.0` → `grade=None` → **"not a setup."** This is a common, correct output. "A market short here is not a setup — R/R only ~0.8" must be reproducible.

**Grading rubric:**
- **A+/A** — premier wave position (e.g. entering W2 to ride W3) **and** structural confirmation present.
- **B** — same position but held back by: unconfirmed-complete adjacent structure, a live alternate scenario ≥~30%, or R/R at the 2:1 floor.
- **None** — fails the R/R gate or requires catching a knife with no confirmation.

Once issued, levels and grade are **frozen** (immutable). Subsequent runs only update `status`. The frozen block is copied verbatim into the `SignalRecord.setup` — the tester scores the levels the generator actually committed to, never a later revision.

---

## 12. Scorecard / frozen state (in-report status — NOT the reliability judge)
SQLite store. On each run: load prior setups for the ticker, re-evaluate `status` **against bars ≤ as_of only**, persist transitions. **Never mutate frozen levels.** First-look tickers skip scoring.

State machine: `untriggered → active → {won|lost|invalidated|expired}`; `untriggered → expired` if structure breaks before fill.

**Boundary (v2):** this scorecard exists to print "the prior short triggered, sits ~flat, stop intact" *inside the human report* at decision time. It is **not** the reliability evaluator and produces **no** aggregate statistics. The separate tester re-derives every outcome independently from frozen `SignalRecord`s + continuation bars and owns all calibration/hit-rate metrics. Both use the **same canonical outcome rules in §18** so a spot-check of the in-report status always agrees with the tester.

---

## 13. Adversarial review pass (deterministic)
A deterministic second pass that re-checks what the human reviewer caught: (a) was each retrace/projection computed on the correct scale for the move's span? (b) are wave extremes the true pivots, not approximate ones? (c) does any setup sit below the R/R floor? (d) do scenario weights sum to 1 and is the residual sane? Emits warnings and, where unambiguous, auto-corrects (e.g. recompute a flagged linear retrace on log). Warnings are also written into the `SignalRecord` (a `review_flags` array) so the tester can segment reliability by "clean vs flagged" calls. LLM critic is a later, off-by-default upgrade of this same interface.

---

## 14. Rendering (full output — kept in v1)
`mplfinance` candlesticks per degree with: circled wave labels at pivots, horizontal level lines (targets/invalidation/triggers) with right-aligned annotations, optional dashed channel lines, a volume panel, and the **zoom inset** on the active sub-structure (as in the reference daily charts). Output: `records/charts/<TICKER>/<as_of>-<tf>.png`. Report scaffold assembles header + scenario table + trade-plan table + "one level that matters." The report and the `SignalRecord` are produced in the same run from the same `Count`/`Scenario`/`Setup` objects, so they can never disagree.

---

## 15. Project boundary & tester handoff (v2 — core addition)

### 15.1 Two projects, one seam
- **Project 1 (this spec):** ingest a price series, produce the full human report **and** a frozen `SignalRecord`. Pure function of bars ≤ as_of. Knows nothing about the future and computes no reliability statistics.
- **Project 2 (separate tester):** consume `SignalRecord`s + the continuation of the series, resolve each call's outcome (§18), and compute reliability/calibration. Owns all forward-looking evaluation.

The seam is the `SignalRecord` JSON (§5.1) and the per-ticker append-only `signals.jsonl`. The tester imports nothing from Project 1 except, optionally, the shared `outcome/rules.py` definitions (§18) so the two never drift.

### 15.2 What the tester receives
1. `signals.jsonl` — one `SignalRecord` per line, in `as_of` order.
2. Each record's `data.data_hash`, `as_of`, and `source` — so the tester knows the exact input and can fetch/slice the **continuation** (bars after `as_of`).
3. The frozen `setup` block — the levels and grade actually committed to.

The tester is responsible for sourcing continuation bars; Project 1 only stamps what it used. With `data_hash` the tester can also verify the historical input wasn't silently revised (e.g. a vendor restatement).

### 15.3 No-lookahead invariant (enforced, not assumed)
For a run with cutoff `as_of`:
- `ingest` clamps/asserts: no bar with `ts > as_of` enters `Bars`.
- `resample` builds weekly/monthly bars **only** from daily bars ≤ as_of; the final derived bar is marked `is_partial` and carries `as_of`.
- `pivots`, `enumerate`, `rules`, `fib`, `scenarios`, `setup`, `scorecard` all read only `Bars` (≤ as_of). No stage may peek beyond `as_of`.
- Core is **pure**: no wall-clock branch, no RNG without a fixed seed, no network. `generated_at` is recorded for humans but never enters logic.
- A unit test asserts that truncating the input at `as_of` and running, vs running the full file with `--as-of as_of`, produces identical `SignalRecord`s (minus `generated_at`). This is the leakage tripwire.

### 15.4 Walk-forward export mode
`analyze --walk-forward --start DATE [--end DATE] --step {1d|1w|N} --no-report <ticker> <csv>`:
- For each step date `T` from `--start`, slice bars ≤ `T`, run the pipeline, append a `SignalRecord` to `signals.jsonl`.
- `--no-report` (default in walk-forward) skips charts/markdown for speed; a single full report is still produced for the final/explicit `as_of` on demand.
- **Cost mitigation:** enumeration is the expensive stage (§8). Between adjacent steps most pivots are unchanged, so cache pivot/enumeration results keyed by `(tf, last_confirmed_pivot_idx)` and only recompute the still-forming tail. Target: a multi-year daily walk-forward over one ticker completes in minutes, not hours.
- Output of one walk-forward run = exactly the historical signal stream the tester needs for that ticker.

### 15.5 Determinism contract
Same `csv` bytes + same `--as-of` + same `engine_version` ⇒ byte-identical `SignalRecord` (excluding `generated_at`). Guaranteed by purity (§15.3) and asserted in CI against golden records. This is what lets the tester attribute any change in reliability to a deliberate generator change, not noise.

---

## 16. Validation
Use the reference reports as ground-truth fixtures: SPX, ADBE, ORCL, BABA, USDJPY, 7974.T. For each, check the engine (a) surfaces the documented primary count among its top candidates, (b) reproduces the key levels within tolerance, (c) reproduces the setup grade and R/R gate decision, and (d) emits a schema-valid `SignalRecord`. These also calibrate the §8 pruning defaults. Matching *exactly* is not the bar — surfacing the right count in the top-N with sane levels is.

**Anti-overfit discipline:** the six reference tickers are used to *tune* pruning defaults, so they cannot also be the reliability sample. Reserve held-out tickers and held-out time windows for any reliability claim; the tuning set proves "the engine can see the right structure," the held-out set proves "the signals are worth trusting." Also note the reference reports are single-date snapshots — they validate structure recognition, not the time-series of signals the tester will score.

---

## 17. Build sequence (milestones)
1. **M1 — Skeleton & data.** io (incl. as_of clamp) + pivots (forked) + Bars/Leg schemas. Output: pivots plotted on 3 timeframes.
2. **M2 — Impulse + diagonal end-to-end.** enumerate(forked) + sweep + cardinal/guideline rules + fib levels + single-degree charts. Tractable, well-supported.
3. **M3 — Corrective patterns.** zigzag/flat/triangle grammar + rules. **The core value gap; where every existing tool quits.** Budget the most time here.
4. **M4 — Degree nesting.** triple reconciliation; full 3-degree report skeleton.
5. **M5 — Signal layer.** scenarios + setup + grade + R/R gate + scorecard.
6. **M6 — Render + assemble.** annotated charts w/ inset, full human report.
7. **M7 — Export + walk-forward + determinism.** `SignalRecord` schema, `signals.jsonl`, `--walk-forward`, no-lookahead tripwire test, golden-record CI. **This is the tester handoff; do not skip or defer.**
8. **M8 — Validate** against §16 fixtures; tune pruning; confirm schema-valid export on all six.

Interpretive engine (LLM-in-the-loop) is deferred per scope decision; M1–M8 ship with deterministic placeholders at every seam (`LabelingEngine`, `ScenarioWeigher`, `NarrativeWriter`), all off by default.

---

## 18. Outcome-resolution rules (canonical — shared by scorecard & tester)
Single source of truth for what a setup's outcome *means*, so the in-report scorecard (§12) and the separate tester (§15) never disagree. Implemented once in `outcome/rules.py` as pure functions over `(frozen_setup, bars)`.

Given a frozen setup and a sequence of bars after `issued`:
- **untriggered → active:** price reaches `entry` per `entry_type` (limit: trades through; stop: trades beyond; market: at issue).
- **active → invalidated:** `invalidation_rule` fires (e.g. daily close beyond `invalidation_level`) before any target. Distinct from a stop-out where relevant.
- **active → lost:** `stop` hit before `t1`.
- **active → won:** `t1` hit before `stop`/invalidation (T2 tracked as a secondary field; "won at T1" is the primary binary).
- **untriggered → expired:** `horizon_bars` elapse without a fill, or structure invalidates before fill.
- **active → expired:** `horizon_bars` elapse with neither target nor stop reached (resolved by mark-to-market, `pnl_r` from close).

Outcome fields the tester computes per record: `triggered (bool)`, `resolution ∈ {won,lost,invalidated,expired}`, `pnl_r`, `mfe_r`, `mae_r`, `bars_to_resolution`. Reliability then = calibration of `confidence_pct`/`grade` against realized `won`-rate and mean `pnl_r`, on held-out data.

**Tie-breaking (must be fixed once):** when a single bar's range spans both `stop` and `t1`, default to **stop-first (conservative)**; expose as a tester config so sensitivity can be checked. Project 1 does not decide this — it only emits levels — but the rule is defined here so both sides share it.

---

## 19. Open decisions
- **Pivot algorithm** — ATR-scaled ZigZag vs prominence-based vs the forked MonoWave skip model as the single source. Leaning: forked MonoWave for atomic swings, prominence for degree assignment. **Spike both in M1 against the reference charts before committing — everything downstream rests on this.**
- **Degree auto-assignment** — by absolute span, by recursion depth, or hybrid. Affects nesting tolerance.
- **Beam width M / eligible-K defaults** — set empirically in M8.
- **Scorecard / setup horizon** — fixed bar count vs scenario-invalidation-driven expiry. Whatever is chosen is written into `SignalRecord.setup.horizon_bars` so the tester inherits it.
- **Intrabar tie-break default** — stop-first is the proposed default (§18); confirm.
- **Long-range monthly input** — optional second CSV now, or defer until a deep-secular ticker needs it.
- **Walk-forward step granularity** — every bar (max resolution, max cost) vs weekly cadence (cheaper, coarser signal stream). Likely per-study config.

---
*End of spec. Next concrete step after sign-off: implement M1 (schemas + forked pivot layer + as_of clamp) so pivots render on all three timeframes and the no-lookahead slicing is in place from day one.*
