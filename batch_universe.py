"""Run a walk-forward signal stream over a MULTI-stock CSV (stock_id column),
with a selectable scenario weigher. Resumable per stock.

    python batch_universe.py data\\prices_anonymized.csv --weigher ollama ^
        --model qwen2.5:14b-instruct --stocks 1-50 --step 12M --start 1962-01-01

Splits the multi-stock file into per-ticker CSVs under <out>/_stocks/ (once),
then writes <out>/S<id>/signals_<weigher>.jsonl for each stock. Re-running
resumes where it left off. Point aggregate_tester.py at <out> to score it.
"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
import pandas as pd
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from ewt.export.signal import build_signal_record


def make_weigher(name, model):
    if name == "deterministic":
        from ewt.weigh.deterministic import DeterministicWeigher; return DeterministicWeigher()
    if name == "fake":
        from ewt.weigh.fake import FakeWeigher; return FakeWeigher()
    if name == "ollama":
        from ewt.weigh.ollama import OllamaWeigher; return OllamaWeigher(model=model)
    raise SystemExit(f"unknown weigher: {name}")


def parse_stocks(spec):
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def split_stocks(multi_csv, stock_ids, split_dir):
    split_dir.mkdir(parents=True, exist_ok=True)
    need = [s for s in stock_ids if not (split_dir / f"{s}.csv").exists()]
    if not need:
        return
    df = pd.read_csv(multi_csv)
    for sid in need:
        s = df[df["stock_id"] == sid][["date", "open", "high", "low", "close", "volume"]].sort_values("date")
        if len(s):
            s.to_csv(split_dir / f"{sid}.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="multi-stock CSV with a stock_id column")
    ap.add_argument("--weigher", default="deterministic", choices=["deterministic", "ollama", "fake"])
    ap.add_argument("--model", default="qwen2.5:14b-instruct")
    ap.add_argument("--stocks", default="1-50")
    ap.add_argument("--start", default="1962-01-01")
    ap.add_argument("--step", default="12M")
    ap.add_argument("--out", default="records/universe")
    args = ap.parse_args()

    out = Path(args.out); split_dir = out / "_stocks"
    ids = parse_stocks(args.stocks)
    split_stocks(args.csv, ids, split_dir)
    weigher = make_weigher(args.weigher, args.model)

    total = 0
    for sid in ids:
        csv = split_dir / f"{sid}.csv"
        if not csv.exists():
            continue
        sdir = out / f"S{sid}"; sdir.mkdir(parents=True, exist_ok=True)
        path = sdir / f"signals_{args.weigher}.jsonl"
        done = set()
        if path.exists():
            for line in open(path):
                if line.strip():
                    done.add(json.loads(line)["data"]["as_of"])
        start = args.start
        with open(path, "a") as fh:
            for b in iter_as_of(str(csv), start=start, step=args.step):
                ao = str(b.as_of.date())
                if ao in done:
                    continue
                a, n = analyze_nested(b)
                rec = build_signal_record(b, a, n, ticker=f"S{sid}", source=f"{sid}.csv", weigher=weigher)
                fh.write(json.dumps(rec, separators=(",", ":")) + "\n"); total += 1
        print(f"stock {sid}: {path}")
    print(json.dumps({"weigher": args.weigher, "stocks": len(ids), "new_records": total}, indent=2))


if __name__ == "__main__":
    main()
