# LLM scenario weigher — local Ollama setup

The engine can weigh its candidate Elliott-Wave scenarios with a local LLM
instead of the deterministic score. The weigher only **re-weights** the
scenarios the mechanical engine already found (and can change which one leads,
i.e. the direction and the confidence %). The deterministic engine is unchanged
and stays the default.

## Why this stays an honest test

- **Determinism:** the Ollama call uses `temperature=0` and every response is
  **cached** by a hash of the (model + input). A re-run is bit-for-bit, and the
  50-stock scan never re-calls the model for an input it has already seen.
- **No lookahead / no leakage:** the model is shown **only** anonymized, relative
  structural features (`ewt/weigh/features.py`) — structure type, degree, leg
  proportions, Fibonacci fit, where price sits as a %. **Never** the ticker,
  dates, or absolute prices. So it cannot recall what actually happened.

## 1. Install Ollama + pull a model

Install Ollama for Windows from https://ollama.com, then in a terminal:

```
ollama pull qwen2.5:14b-instruct      # ~9 GB, fits your 5070 Ti (16 GB), best pick
# faster fallbacks if you want:
# ollama pull qwen2.5:7b-instruct
# ollama pull llama3.1:8b-instruct
```

Leave Ollama running (it serves on http://localhost:11434).

## 2. Smoke-test the weigher on one stock

From the project folder, with the venv active:

```
python weighed_walkforward.py T1 data\Test1.csv --weigher ollama ^
    --model qwen2.5:14b-instruct --start 2000-01-01 --step 12M
```

That writes `records\charts\T1\signals_ollama.jsonl`. First run calls the model
(cached afterwards). Compare to the deterministic baseline:

```
python weighed_walkforward.py T1 data\Test1.csv --weigher deterministic --start 2000-01-01 --step 12M
```

## 3. Run the same 50-stock test, then score both

Re-run your 50-stock annual scan with `--weigher ollama` for each split stock
(or adapt the batch driver to pass the weigher), producing
`signals_ollama.jsonl` per stock. Then score with the tester exactly as before:

```
python tester.py records\charts\<TICKER>\signals_ollama.jsonl data\<stock>.csv
```

Aggregate across stocks and compare **win rate, expectancy, and calibration**
(does grade A finally beat grade B? does higher confidence finally mean higher
win rate?) against the deterministic results in `RESULTS_50stocks_FINAL.md`.
That head-to-head is the whole point: it tells you, objectively, whether the LLM
weigher adds calibration — or whether mechanical EWT lacks edge regardless.

## Knobs

- `--weigher {deterministic|ollama|fake}` — `fake` is an offline stand-in for tests.
- `--model <name>` — any Ollama model tag.
- Cache lives in `records/llm_cache/`. Delete it to force fresh model calls.
- Every signal record is tagged with `"weigher": "<name>"` for provenance.

## Honest expectation

The weigher re-weights existing scenarios; it can't conjure structure the engine
didn't find. It helps most where two scenarios genuinely compete on direction.
If the 50-stock calibration doesn't improve, that's a real result: it means the
bottleneck is the wave-counting itself, not the weighting — and that mechanical
EWT, as built, doesn't carry a tradeable edge on this universe.
