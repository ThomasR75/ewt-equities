# Running the LLM (Ollama) weigher arm + filling the paper

Everything below is PowerShell, run from the project folder with the venv active.
The Ollama weigher only **re-weights** the engine's existing candidate scenarios
(temperature 0, responses cached) — the mechanical engine and the deterministic
baseline are unchanged. This keeps it a fair, reproducible test.

## 0. One-time: Ollama + model

```powershell
ollama pull qwen2.5:14b-instruct    # ~9 GB, fits the 5070 Ti; leave Ollama running (localhost:11434)
```

## 1. Run BOTH weighers through the same pipeline (apples-to-apples)

Both write into `records\universe\S<id>\signals_<weigher>.jsonl`. Same engine,
same walk-forward, same universe — only the scenario weighting differs.

```powershell
# deterministic reference (fast) — establishes the comparison baseline in this dir
python batch_universe.py data\prices_anonymized.csv --weigher deterministic `
    --stocks 1-50 --start 1962-01-01 --step 12M --out records\universe

# LLM arm (resumable — safe to Ctrl-C and re-run; cache skips seen inputs)
python batch_universe.py data\prices_anonymized.csv --weigher ollama `
    --model qwen2.5:14b-instruct --stocks 1-50 --start 1962-01-01 --step 12M --out records\universe
```

Smoke-test first if you want: swap `--stocks 1-50` for `--stocks 1-5`. The full
run makes a few thousand LLM calls the first time (roughly 1–2 h on the 5070 Ti
with the 14b model; the 7b model is ~2× faster). Re-runs are instant from cache.

## 2. Score each arm (Wilson + bootstrap + random-direction null + calibration)

```powershell
python aggregate_tester.py records\universe --weigher deterministic
python aggregate_tester.py records\universe --weigher ollama
```

## 3. Fill the paper from the `--weigher ollama` printout

Edit `paper\build_paper.py`:

1. Set `LLM_DONE = True`.
2. Fill the `LLM` dict from the ollama `aggregate_tester.py` output. Mapping:

| aggregate_tester line                              | LLM dict key   | example value                       |
|----------------------------------------------------|----------------|-------------------------------------|
| `win rate X%  Wilson95 [...]`                      | `win`          | `"21.4%"`                           |
| `expectancy +X R  bootstrap95 [lo, hi] (p ...)`    | `exp`, `boot`  | `exp="+0.05 R"`, `boot="[-0.30, +0.42], p=0.71"` |
| `calibration by grade:  A: n=.. win ..% meanR ..`  | `A`            | `"18% win, -0.10 R (n=12)"`         |
| `  B: n=.. win ..% meanR ..`                       | `B`            | `"23% win, +0.02 R (n=41)"`         |
| compare A meanR vs B meanR                          | `A_beats_B`    | `"Yes"` if A meanR > B meanR else `"No"` |
| does win rate rise across the 3 confidence buckets? | `calibrated`   | `"Yes"` if monotonic up else `"No"` |

3. Rebuild:

```powershell
python paper\build_paper.py
```

Section 7's table (Deterministic vs LLM) then renders automatically, and the
pre-registered success criteria in §6 are the checklist: expectancy CI clearing
zero, grade A > B, monotonic confidence→win, and the engine escaping the
random-direction null.

## What to expect (and why)

Given §5.2, the structural features carry no out-of-sample directional signal
beyond market drift, and the LLM sees the **same** anonymized features. So unless
it extracts something the gradient-boosted tree provably could not, expect the
LLM arm to land near the deterministic arm — a null result that localizes the
bottleneck in the wave-count/features, not the weighting model. That is itself
the registered, publishable outcome; run it to confirm rather than assume.
