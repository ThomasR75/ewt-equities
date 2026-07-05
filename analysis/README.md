# Analysis — reproducing the paper's statistics and figures

Run from the repo root with the venv active. Generated `records/` are git-ignored;
regenerate them first (see the repo README "Reproduce the results").

| Script | Reproduces | Command |
|---|---|---|
| `paper_stats.py` | §4 & §7: expectancy, Wilson/bootstrap/block-bootstrap, drift control, grade A>B (permutation + split-half), Brier/ECE, cost sensitivity | `python analysis/paper_stats.py records/universe_monthly` |
| `gbt_feature_test.py` | §5.2: held-out GBT AUC decomposition (drift vs wave structure) | `python analysis/gbt_feature_test.py data/prices_anonymized.csv --atr-k 4` |
| `count_diagnostics.py` | Count-subjectivity: % of reads whose valid counts disagree on direction; renders the two-competing-counts figure | `python analysis/count_diagnostics.py data/prices_anonymized.csv` |

§5.1 (disjoint-ticker sensitivity test) uses `sweep_sensitivity.py` on ticker
subsets: pick k on one ticker half (`--stocks 2-50:even` conceptually — run on even
ids), then score the chosen k once on the odd ids. See EXPERIMENT.md.

All scripts are deterministic (fixed seeds) except where they depend on a
generated `records/` directory.
