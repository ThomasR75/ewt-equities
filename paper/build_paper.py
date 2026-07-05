from __future__ import annotations
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

OUT = Path(__file__).with_name("EWT_reliability_paper.pdf")
MODEL = "qwen2.5:7b-instruct"

def styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("TitleBig", parent=ss["Title"], fontSize=17, leading=21))
    ss.add(ParagraphStyle("Auth", parent=ss["Normal"], alignment=1, textColor=colors.grey))
    ss.add(ParagraphStyle("H", parent=ss["Heading2"], spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1f2937")))
    ss.add(ParagraphStyle("Body", parent=ss["BodyText"], fontSize=9.3, leading=13.5, alignment=4, spaceAfter=6))
    ss.add(ParagraphStyle("Abs", parent=ss["BodyText"], fontSize=9.3, leading=13.5, alignment=4, leftIndent=14, rightIndent=14, textColor=colors.HexColor("#374151")))
    ss.add(ParagraphStyle("Ref", parent=ss["BodyText"], fontSize=8.2, leading=11, spaceAfter=3, leftIndent=12, firstLineIndent=-12))
    ss.add(ParagraphStyle("Cell", parent=ss["BodyText"], fontSize=8.2, leading=10, spaceAfter=0))
    ss.add(ParagraphStyle("CellH", parent=ss["BodyText"], fontSize=8.2, leading=10, textColor=colors.white, fontName="Helvetica-Bold"))
    return ss

def P(t, s, st="Body"): return Paragraph(t, s[st])

def kv(rows, s, header, widths=(4.2, 6.3, 6.3)):
    data = [[Paragraph(str(c), s["CellH"]) for c in header]] + \
           [[Paragraph(str(c), s["Cell"]) for c in row] for row in rows]
    t = Table(data, colWidths=[w * cm for w in widths], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6f8")])]))
    return t

def build():
    s = styles(); e = []
    e.append(P("A Reproducible, Pre-Registered Test of Mechanical Elliott-Wave Signals, and Whether a Local-LLM Scenario Weigher Improves Calibration", s, "TitleBig"))
    e.append(Spacer(1, 3)); e.append(P("Thomas &middot; Elliott Wave RCT project", s, "Auth"))
    e.append(P("Working paper &mdash; deterministic and local-LLM arms complete, with statistics", s, "Auth"))
    e.append(Spacer(1, 9))

    e.append(P("Abstract", s, "H"))
    e.append(P("We build a deterministic, point-in-time Elliott-Wave (EW) signal generator and an independent reliability tester that share one set of outcome rules, and ask (1) whether the mechanical engine yields a tradeable, calibrated edge, and (2) whether a local-LLM scenario weigher improves it. On an anonymized 50-instrument panel (1962&ndash;2026; 588k daily bars), a monthly-cadence walk-forward produced 442 out-of-sample setups: 22.6% win rate (Wilson 95% CI 19.0&ndash;26.8%) and &minus;0.01R expectancy (bootstrap 95% CI &minus;0.17 to +0.15; p&asymp;0.83) &mdash; a precise zero. (A smaller annual run had shown +0.35R; 6.5&times; the sample dissolved it, i.e. it was drift/noise.) The result is market drift, not wave skill: long setups profit (+0.36R), shorts lose (&minus;0.50R), an all-long book matches the engine, and against buy-and-hold the engine's alpha is significantly negative (&minus;6.06R, 95% CI &minus;6.94 to &minus;5.26). Two controls confirm this is not a mechanization artifact: tuning the most powerful parameter created an edge that vanished once both the parameter and the instruments were held out (p=0.59), and a gradient-boosted weigher's apparent skill was entirely the direction sign (drift), wave-structure features at chance (AUC 0.53). One positive survives, under the LLM weigher: its grade-A setups beat grade-B by ~0.5R (label-permutation p=0.001; +8pp win rate, p=0.04) &mdash; absent under the deterministic grade (p=0.11), robust to stock clustering, running against a reward/risk confound, and partially surviving drift adjustment (p=0.07); but it is relative ranking, not edge (overall expectancy is zero, grade-A still loses to buy-and-hold, and it is uneven across ticker halves). Confidence is poorly calibrated as a probability (Brier worse than base rate; ECE&asymp;0.35; systematic overconfidence) though it discriminates. We report a reproducible null on profitability, with a fragile but real LLM ranking signal that warrants more data.", s, "Abs"))

    e.append(P("1. Introduction", s, "H"))
    e.append(P("EW analysis is popular but hard to automate objectively; critics cite its subjectivity and the ease of fitting counts in hindsight [1,2]. We sidestep the 'one true count' by emitting ranked candidate counts with confidence, and ask the only questions that matter for use: are the signals reliable out-of-sample, is the confidence calibrated, and does the engine beat the trivial benchmark of simply holding the market? A strict generator/tester split keeps the measured system from measuring itself.", s))

    e.append(P("2. Related work &mdash; how prior work ranks EW", s, "H"))
    e.append(P("The academic mainstream is skeptical of technical analysis in general and EW in particular. Lo, Mamaysky &amp; Wang [3] built the reference automated framework &mdash; kernel-regression pattern recognition on U.S. stocks 1962&ndash;1996 &mdash; and found only modest incremental information in some patterns. Sullivan, Timmermann &amp; White [4], applying White's Reality Check bootstrap to ~100 years of the DJIA (extending Brock, Lakonishok &amp; LeBaron [5]), found that once data-snooping across the rule universe is corrected, out-of-sample profitability largely vanishes. EW-specific studies are fewer and mixed: D'Angelo &amp; Grimaldi [6] report accurate EUR/USD forecasts, and regional studies [7,8] claim support &mdash; but these are largely in-sample, single-market, or analyst-discretion fits. The recurring critique is the same two problems: subjectivity of the count and data-snooping / hindsight.", s))
    e.append(P("<b>What we replicate.</b> A multi-decade, multi-stock U.S. panel overlapping Lo et al.'s era and design philosophy, with the out-of-sample + bootstrap discipline of [4]. We attack the two standard critiques directly: subjectivity &rarr; a fully deterministic, golden-record-hashed engine; data-snooping/hindsight &rarr; anonymized instruments (no names/dates/prices reach the analyst or LLM), a hard no-lookahead boundary, a disjoint-selection test of our main parameter (&sect;5.1), and pre-registration of the LLM arm.", s))
    e.append(P("<b>What we do not (yet) replicate.</b> We test tradeable setups, not Lo et al.'s conditional-return-distribution estimand. We do not yet run White's Reality Check / Hansen's SPA across a full rule universe [4]. And unlike the positive regional EW studies [6&ndash;8], we forbid in-sample fitting and analyst-chosen counts &mdash; which plausibly explains why our out-of-sample result is weaker than their in-sample claims.", s))

    e.append(P("3. Methods", s, "H"))
    e.append(P("<b>3.1 Data.</b> 50 anonymized instruments (stock_id only), 588,427 daily OHLCV bars, 1962&ndash;2026, positive prices, no gaps.", s))
    e.append(P("<b>3.2 Engine.</b> Log-aware ZigZag pivots &rarr; bounded, beam-pruned, bidirectional sweep over motive (impulse, diagonals) and corrective (zigzag, flat, triangle) structures &rarr; scale-aware cardinal rules (W2&lt;W1; W3 not shortest; W4 overlap) + guideline scores (Fibonacci bands, alternation, equality, volume) &rarr; three-degree nesting (daily &sub; weekly &sub; monthly) &rarr; weighted scenarios + residual bucket &rarr; R/R-gated setup. Large moves judged on log scale.", s))
    e.append(P("<b>3.3 Setup construction.</b> Entry/stop anchored to the completion pivot; reward/risk on log scale; degree-scaled invalidation, stop, and evaluation horizon; stable ids to de-duplicate one structure re-seen across bars.", s))
    e.append(P("<b>3.4 No-lookahead &amp; determinism.</b> A signal at T uses only bars &le; T (as_of clamp + tripwire test); deterministic, golden-record hashed; frozen JSON carries data hash + engine version.", s))
    e.append(P("<b>3.5 Tester &amp; statistics.</b> An independent scorer resolves each setup against the continuation (won/lost/invalidated/expired; stop-first tie-break) and reports: win rate (Wilson 95%); expectancy in R (bootstrap 95%, and block-bootstrap by instrument for clustering); a random-direction permutation null; a drift benchmark (buy-and-hold from entry, and every setup forced long); calibration by grade and confidence, a Brier score and expected calibration error (ECE) against realized wins; a label-permutation test of any grade effect with a disjoint-ticker (split-half) replication; and transaction-cost sensitivity.", s))

    e.append(P("4. Results &mdash; deterministic engine", s, "H"))
    e.append(P("27,644 point-in-time signal records across the 50 instruments (monthly walk-forward, full history) yielded 442 distinct setups. A smaller annual run gave 68 setups at +0.35R; that positive dissolved to zero under 6.5&times; the sample and is reported here as the drift artifact it was.", s))
    e.append(kv([
        ["Win rate", "22.6%", "Wilson95 [19.0, 26.8]%"],
        ["Expectancy (raw)", "-0.01 R/trade", "boot95 [-0.17, +0.15]; block-boot by stock [-0.25, +0.25]; p=0.83"],
        ["Random-direction null", "-0.11 R", "5-95% [-0.21, -0.01]; p(eng&ge;rand)=0.06 (drift, see below)"],
        ["Grade A / Grade B", "23% win, +0.16 R (n=115)", "23% win, -0.07 R (n=327)"],
        ["A beats B? / calibrated?", "No (perm p=0.11, n.s.)", "No (Brier worse than base rate)"],
    ], s, ["Metric", "Value", "Inference"]))
    e.append(Spacer(1, 5))
    e.append(P("<b>Drift control (the decisive test).</b> The direction-randomizing null does not randomize market drift, so a mostly-long book in a rising market beats it by construction. Benchmarking against simply holding the market removes the illusion:", s))
    e.append(kv([
        ["Long setups", "n=249, +0.36 R", "all the profit is here"],
        ["Short setups", "n=193, -0.50 R", "they lose"],
        ["Force every setup long", "+0.32 R", "matches the engine (-0.01R)"],
        ["Buy-and-hold from entry", "+6.05 R", "the actual drift"],
        ["Engine alpha vs buy-and-hold", "-6.06 R", "boot95 [-6.94, -5.26]"],
    ], s, ["Benchmark", "Mean R", "Reading"]))
    e.append(Spacer(1, 5))
    e.append(P("<b>Reading.</b> Expectancy is a precise zero and the engine loses to buy-and-hold by &minus;6.06R: profit comes only from long setups, the short calls lose, and an all-long book matches the engine, so its directional choices add nothing over drift. The deterministic grade hints at calibration (A +0.16R vs B &minus;0.07R) but the separation is not significant (label-permutation p=0.11; block-bootstrap CI by stock includes zero; identical A/B win rates) and reverses after drift adjustment &mdash; so the engine's own grade carries no reliable ranking skill. Net: no wave-counting edge and no significant calibration from the deterministic engine; whether the weighting layer adds ranking information is tested in &sect;7.", s))

    e.append(P("5. Robustness: can tuning or a learned weigher create an edge?", s, "H"))
    e.append(P("<b>5.1 The pivot-sensitivity switch.</b> The engine's highest-leverage free parameter is the pivot reversal threshold. We replaced the fixed-percentage threshold with a structural one &mdash; threshold = ln(1 + k&middot;ATR/close) on each timeframe's own bars &mdash; so a single coefficient k adapts sensitivity to each instrument's volatility, and asked whether tuning k manufactures an edge (direction scored against a geometry-matched random-side null). Selecting k by looking at a window makes that window glow: k=5 beat its null at p&asymp;0.03 and even replicated on a time-held-out split (p&asymp;0.02). The decisive test holds out both the parameter and the instruments &mdash; one random half of the tickers chose k (it picked k=4), the other half was scored once:", s))
    e.append(kv([
        ["k=5, selected on this window", "28", "obs +0.640 / null +0.041 (p=0.029)"],
        ["k=5, time-held-out (pre-2015)", "52", "obs +0.777 / null +0.231 (p=0.018)"],
        ["k=4, parameter + names held out", "20", "obs +0.072 / null +0.153 (p=0.591)"],
    ], s, ["Held-out test", "n", "Expectancy vs random-side null (R)"]))
    e.append(Spacer(1, 4))
    e.append(P("On the fully held-out half the observed expectancy falls below the geometry null (p=0.59) &mdash; no edge. The 'best' k is unstable (k=4 on one half, k=5 on the panel holdout) and the obs-vs-null gap collapses once selection is forbidden &mdash; reproducing, inside our own pipeline, the central finding of [4].", s))
    e.append(P("<b>5.2 A learned (gradient-boosted) weigher.</b> We built a supervised table (one row per candidate scenario: the anonymized structural features of &sect;3.2 plus its implied direction; label = whether that direction matched the sign of the forward 252-day return), trained a histogram GBT (depth 3, isotonic-calibrated) on one random half of the instruments, and evaluated once on the other.", s))
    e.append(kv([
        ["GBT, all features", "0.674", "apparently predictive"],
        ["Implied-direction sign alone", "0.675", "explains all of it (drift)"],
        ["GBT, structure only (no direction)", "0.529", "wave features &asymp; chance"],
        ["GBT, structure only, long setups", "0.467", "no separation within a side"],
    ], s, ["Held-out predictor", "AUC", "Reading"]))
    e.append(Spacer(1, 4))
    e.append(P("AUC 0.674 is not wave skill: the identical AUC (0.675) comes from the direction sign alone, because over 252-day windows the panel drifts up (P(correct | long)=0.70 vs 0.35 for short). Removing direction, wave structure alone gives AUC 0.529 (0.467 within long setups) &mdash; chance (label-shuffled null 0.502). The structural features carry no out-of-sample directional information beyond drift; a learned weigher over them can only follow drift, which &sect;4 already shows loses to buy-and-hold.", s))

    e.append(P("6. LLM scenario weigher &mdash; pre-registration", s, "H"))
    e.append(P("A drop-in weigher (local model via Ollama, " + MODEL + ", temperature 0, responses cached) re-weights the engine's existing candidate scenarios (and may change lead direction and confidence), leaving pivots/rules/structure/setup untouched. Controls: determinism (temp 0 + cache); no leakage (the model sees only anonymized relative features &mdash; structure, degree, leg proportions, Fibonacci fit, price position); identical universe, tester, horizon. Pre-registered success: expectancy CI clearing zero, grade A &gt; B, monotonic confidence&ndash;win relationship, and the engine escaping the drift benchmark.", s))

    e.append(P("7. Results &mdash; LLM weigher", s, "H"))
    e.append(kv([
        ["Setups resolved", "442", "466"],
        ["Win rate", "22.6%", "22.7%"],
        ["Expectancy", "-0.01 R [-0.17, +0.15]", "+0.01 R [-0.14, +0.18], p=0.89"],
        ["Grade A / B (meanR)", "+0.16 (n=115) / -0.07 (n=327)", "+0.32 (n=155) / -0.14 (n=311)"],
        ["Grade A &gt; B?", "No (perm p=0.11)", "Yes (perm p=0.001)"],
    ], s, ["Metric", "Deterministic", "LLM (" + MODEL + ")"]))
    e.append(Spacer(1, 5))
    e.append(P("<b>The grade signal.</b> The LLM weigher's grade separation is the one result that survives scrutiny. Grade-A setups beat grade-B by ~0.5R (label-permutation p=0.001); the gap survives block-bootstrapping by stock (95% CI [+0.12, +1.01]) and appears in the win rate too (27.0% vs 19.1%, +8pp, p=0.04) &mdash; which runs against a reward/risk confound, since grade-A setups carry higher R:R (3.0 vs 2.4) and should therefore win less, not more. It partially survives drift adjustment (gap +1.19R after subtracting each setup's buy-and-hold return, p=0.07). The same test on the deterministic grade is null (p=0.11). So the LLM adds genuine relative ranking information, not merely concentrated drift.", s))
    e.append(P("<b>Split-half replication.</b> Splitting the 50 tickers into disjoint halves, the grade A&gt;B expectancy gap holds on both (even +0.71R, p=0.001; odd +0.42R, p=0.05), but the win-rate edge concentrates in one half (even +15pp, p=0.005; odd +2pp, p=0.46). So the effect is directionally reproducible but uneven &mdash; a real but fragile signal, not yet a stable, generalizable edge.", s))
    e.append(P("<b>Calibration (Brier / ECE).</b> As a probability the confidence is poorly calibrated: Brier 0.33 (LLM) and 0.31 (deterministic), both worse than a base-rate forecast (~0.17&ndash;0.18); ECE&asymp;0.35&ndash;0.39. It is systematically overconfident &mdash; the top bucket states ~82% but wins ~30%:", s))
    e.append(kv([
        ["70&ndash;100%", "0.82", "0.31", "162"],
        ["50&ndash;70%", "0.58", "0.18", "132"],
        ["30&ndash;50%", "0.41", "0.15", "142"],
        ["0&ndash;30%", "0.27", "0.00", "13"],
    ], s, ["Confidence bucket", "Stated", "Actual win", "n"], widths=(4.5, 4.0, 4.0, 4.3)))
    e.append(Spacer(1, 4))
    e.append(P("Win rate rises with confidence (discrimination), but the levels are far above realized wins (miscalibration). Part of this is structural &mdash; the confidence expresses belief in the count's direction, scored here against a high-R:R win bar &mdash; but a user should treat the percentages as an ordering, not a probability. <b>Verdict.</b> The LLM weigher does not create an edge (expectancy zero; grade-A still loses to buy-and-hold), but it does carry a real, if fragile, ranking signal the deterministic engine lacks &mdash; the study's one positive, pending more data to confirm it is not a large-sample fluke.", s))

    e.append(P("8. Toward greater statistical power (future work)", s, "H"))
    e.append(P("The open question is now the LLM ranking signal, not the profitability null. Concrete steps: (a) finer (weekly) cadence and a universe beyond these 50 names &mdash; more setups to confirm or kill the grade-A effect, which is uneven across ticker halves; (b) tag the model in every record (currently only the weigher name is stored) so the LLM arm is provably a single model; (c) recalibrate confidence to a true win-probability (isotonic on a training fold) and re-measure Brier/ECE; (d) White's Reality Check / Hansen's SPA across configurations to bound data-snooping [4]; (e) a volatility-matched random-entry benchmark and transaction-cost curves (partially implemented). Pre-registration (done for the LLM arm) constrains researcher degrees of freedom.", s))

    e.append(P("9. Limitations", s, "H"))
    e.append(P("Monthly cadence still misses sub-monthly setups (a weekly run is the next step); finer cadence also produces clustered, semi-redundant setups, so raw n overstates independent information and the block-bootstrap-by-stock interval is the honest one. One engine family with un-tuned secondary parameters (beam width, R/R floor, horizon scaling); frictionless, point-in-time; one anonymized 50-instrument universe; a single local LLM at temperature 0. The grade-A finding is not multiple-testing corrected across the several metrics examined. Research artifact, not trading advice.", s))

    e.append(P("10. Conclusion", s, "H"))
    e.append(P("A reproducible, pre-registered harness gives a precise answer on this universe: the mechanical engine has no statistically detectable out-of-sample edge and no wave-counting skill. Expectancy is a precise zero on 442 monthly setups (a smaller annual run's +0.35R dissolved under 6.5&times; the data), and the engine underperforms buy-and-hold by &minus;6.06R. The deterministic grade shows no significant calibration (p=0.11); tuning the most powerful parameter produced an edge that vanished once parameter and instruments were both held out; and a gradient-boosted weigher's skill was drift, not structure. The one positive is the local-LLM weigher's grade separation (A&gt;B, p=0.001) &mdash; robust to clustering, running against a reward/risk confound, partially surviving drift adjustment &mdash; but it is relative ranking, not edge (expectancy zero; grade-A still loses to buy-and-hold) and it is uneven across ticker halves, so it warrants more data before any claim. The bottleneck is the information in the wave-count features, not the weighting model &mdash; reproducing, inside our own pipeline, the data-snooping and no-edge cautions of the technical-analysis literature [3,4].", s))

    e.append(P("References", s, "H"))
    for r in [
        "[1] Frost, A. J. &amp; Prechter, R. R. Elliott Wave Principle: Key to Market Behavior. New Classics Library (1978; 10th ed. 2005).",
        "[2] EW subjectivity/critique summarized in [3,4].",
        "[3] Lo, A. W., Mamaysky, H. &amp; Wang, J. (2000). Foundations of Technical Analysis. Journal of Finance 55(4), 1705&ndash;1765.",
        "[4] Sullivan, R., Timmermann, A. &amp; White, H. (1999). Data-Snooping, Technical Trading Rule Performance, and the Bootstrap. Journal of Finance 54(5), 1647&ndash;1691.",
        "[5] Brock, W., Lakonishok, J. &amp; LeBaron, B. (1992). Simple Technical Trading Rules and the Stochastic Properties of Stock Returns. Journal of Finance 47(5), 1731&ndash;1764.",
        "[6] D'Angelo, E. &amp; Grimaldi, G. (2017). The Effectiveness of the Elliott Waves Theory to Forecast Financial Markets. International Business Research 10(6), 1&ndash;18.",
        "[7] Chendroyaperumal, C. &amp; Karthikeyan, B. Empirical Verification of Elliott Wave Theory in the Indian Stock Market. SSRN 1887789.",
        "[8] Exploring the Elliott Wave Principle to interpret metal commodity price cycles. Resources Policy (Elsevier), 2018.",
    ]:
        e.append(P(r, s, "Ref"))
    e.append(Spacer(1, 6))
    e.append(P("Artifacts: engine ewt/; testers tester.py, aggregate_tester.py; disjoint-selection sweep_sensitivity.py (--pivot-mode atr); weigher ewt/weigh/; runners batch_universe.py, weighed_walkforward.py; protocol EXPERIMENT.md, RUN_LLM_ARM.md.", s))

    SimpleDocTemplate(str(OUT), pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.7 * cm, rightMargin=1.7 * cm, title="EWT reliability paper", author="Thomas").build(e)
    print("wrote", OUT)

if __name__ == "__main__":
    build()
