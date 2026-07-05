"""Walk-forward signal stream with a selectable scenario weigher.

    python weighed_walkforward.py <ticker> <csv> --weigher ollama --model qwen2.5:14b-instruct \
        --start 1990-01-01 --step 12M --out records/charts

--weigher: deterministic (default) | ollama | fake
Writes <out>/<TICKER>/signals_<weigher>.jsonl  (one frozen SignalRecord per line).
The Ollama weigher needs a local Ollama server + the model pulled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from ewt.export.signal import build_signal_record


def make_weigher(name: str, model: str):
    if name == "deterministic":
        from ewt.weigh.deterministic import DeterministicWeigher
        return DeterministicWeigher()
    if name == "fake":
        from ewt.weigh.fake import FakeWeigher
        return FakeWeigher()
    if name == "ollama":
        from ewt.weigh.ollama import OllamaWeigher
        return OllamaWeigher(model=model)
    raise SystemExit(f"unknown weigher: {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker"); ap.add_argument("csv")
    ap.add_argument("--weigher", default="deterministic",
                    choices=["deterministic", "ollama", "fake"])
    ap.add_argument("--model", default="qwen2.5:14b-instruct")
    ap.add_argument("--start", default="1990-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--step", default="12M")
    ap.add_argument("--out", default="records/charts")
    args = ap.parse_args()

    weigher = make_weigher(args.weigher, args.model)
    out = Path(args.out) / args.ticker
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"signals_{args.weigher}.jsonl"
    n = 0
    with open(path, "w") as fh:
        for b in iter_as_of(args.csv, start=args.start, end=args.end, step=args.step):
            a, nested = analyze_nested(b)
            rec = build_signal_record(b, a, nested, ticker=args.ticker,
                                      source=Path(args.csv).name, weigher=weigher)
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            n += 1
    print(json.dumps({"ticker": args.ticker, "weigher": args.weigher,
                      "records": n, "out": str(path)}, indent=2))


if __name__ == "__main__":
    main()
