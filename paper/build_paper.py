from __future__ import annotations
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)

OUT = Path(__file__).with_name("EWT_reliability_paper.pdf")

DET = {"reads":"2,306","setups":"68","win":"26.5%","wilson":"[17.4, 38.0]%","exp":"+0.35 R",
       "boot":"[-0.10, +0.83]","p0":"0.15","null_mean":"-0.10","null_ci":"[-0.37, +0.18]",
       "p_dir":"0.00","anti":"-0.54","A":"26% win, +0.40 R (n=19)","B":"27% win, +0.33 R (n=49)",
       "A_beats_B":"No (A~B, n=19)","calibrated":"No"}
DRIFT = {"long":"n=46, +0.89 R","short":"n=22, -0.79 R","alllong":"+0.63 R",
         "bh":"+6.51 R","alpha":"-6.16 R","alpha_ci":"[-7.97, -4.46]"}
LLM_DONE = True
LLM = {"model":"qwen2.5:14b-instruct","win":"25.7%","exp":"+0.31 R","boot":"boot95 [-0.15, +0.80], p=0.18",
       "A":"19% win, +0.08 R (n=26)","B":"30% win, +0.45 R (n=44)","A_beats_B":"No (A<B)","calibrated":"No"}
DISCUSSION_LLM = ("The LLM weigher did not improve the engine: expectancy edged down (+0.31R vs +0.35R, CI still "
  "spanning zero) and its confidence signal degraded &mdash; grade-A (high-confidence) setups returned +0.08R "
  "against +0.45R for grade B, and its top confidence bucket underperformed its lower one. Seeing the same "
  "anonymized structural features that carried no out-of-sample directional signal for the gradient-boosted tree "
  "(&sect;5.2), it reshuffled confidence on noise rather than adding information. This is the pre-registered null "
  "outcome, and it localizes the bottleneck in the wave-count/features, not the weighting model.")

def styles():
    ss=getSampleStyleSheet()
    ss.add(ParagraphStyle("TitleBig",parent=ss["Title"],fontSize=17,leading=21))
    ss.add(ParagraphStyle("Auth",parent=ss["Normal"],alignment=1,textColor=colors.grey))
    ss.add(ParagraphStyle("H",parent=ss["Heading2"],spaceBefore=10,spaceAfter=4,textColor=colors.HexColor("#1f2937")))
    ss.add(ParagraphStyle("Body",parent=ss["BodyText"],fontSize=9.3,leading=13.5,alignment=4,spaceAfter=6))
    ss.add(ParagraphStyle("Abs",parent=ss["BodyText"],fontSize=9.3,leading=13.5,alignment=4,leftIndent=14,rightIndent=14,textColor=colors.HexColor("#374151")))
    ss.add(ParagraphStyle("Ref",parent=ss["BodyText"],fontSize=8.2,leading=11,spaceAfter=3,leftIndent=12,firstLineIndent=-12))
    return ss

def P(t,s,st="Body"): return Paragraph(t,s[st])

def kv(rows,s,header):
    t=Table([header]+rows,hAlign="LEFT",colWidths=[5.6*cm,5.6*cm,5.6*cm])
    t.setStyle(TableStyle([("FONT",(0,0),(-1,-1),"Helvetica",8.3),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d1d5db")),
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f3f4f6")),
        ("FONT",(0,0),(-1,0),"Helvetica-Bold",8.3),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#fafafa")])]))
    return t

def build():
    s=styles(); e=[]
    e.append(P("A Reproducible, Pre-Registered Test of Mechanical Elliott-Wave Signals, and Whether a Local-LLM Scenario Weigher Improves Calibration",s,"TitleBig"))
    e.append(Spacer(1,3)); e.append(P("Thomas &middot; Elliott Wave RCT project",s,"Auth"))
    e.append(P("Working paper &mdash; deterministic and local-LLM arms complete, with statistics",s,"Auth"))
    e.append(Spacer(1,9))
    e.append(P("Abstract",s,"H"))
    e.append(P("We build a deterministic, point-in-time Elliott-Wave (EW) signal generator and an independent reliability tester sharing one set of outcome rules, and ask (1) whether the mechanical engine yields a tradeable, calibrated edge, and (2) whether a local LLM scenario weigher improves it. On an anonymized 50-instrument panel (1962&ndash;2026; 588k daily bars) the engine produced 68 distinct out-of-sample setups with a 26.5% win rate (Wilson 95% CI 17.4&ndash;38.0%) and +0.35R raw expectancy (bootstrap 95% CI &minus;0.10 to +0.83; p&asymp;0.15 &mdash; not significant). The result is market drift, not wave skill: all profit comes from long setups (+0.89R; the 22 short setups lose, &minus;0.79R), simply going long on every setup beats the engine (+0.63R), and against a buy-and-hold benchmark the engine's alpha is significantly negative (&minus;6.16R, 95% CI &minus;7.97 to &minus;4.46). Two further controls agree: tuning the engine's most powerful parameter created an edge that vanished once both the parameter and the instruments were held out (p=0.59), and a gradient-boosted weigher's apparent skill was entirely the direction sign (drift), with wave-structure features at chance (AUC 0.53). The local-LLM weigher did not help &mdash; expectancy edged down and grade calibration worsened. We report a reproducible null: no detectable wave-counting edge, and a mechanization that underperforms buy-and-hold.",s,"Abs"))
    e.append(P("1. Introduction",s,"H"))
    e.append(P("EW analysis is popular but hard to automate objectively; critics cite its subjectivity and the ease of fitting counts in hindsight [1,2]. We sidestep the 'one true count' by emitting ranked candidate counts with confidence, and we ask the only question that matters for use: are the signals reliable out-of-sample, is the confidence calibrated, and does the engine beat the trivial benchmark of simply holding the market? A strict generator/tester split keeps the measured system from measuring itself.",s))
    e.append(P("2. Related work &mdash; how prior work ranks EW",s,"H"))
    e.append(P("The academic mainstream is skeptical of technical analysis in general and EW in particular. Lo, Mamaysky &amp; Wang [3] built the reference automated framework &mdash; kernel-regression pattern recognition on U.S. stocks 1962&ndash;1996, comparing conditional vs. unconditional return distributions &mdash; and found only modest incremental information in some patterns. Sullivan, Timmermann &amp; White [4], applying White's Reality Check bootstrap to ~100 years of the DJIA (extending Brock, Lakonishok &amp; LeBaron [5]), found that once data-snooping across the rule universe is corrected, out-of-sample profitability largely vanishes. EW-specific studies are fewer and mixed: D'Angelo &amp; Grimaldi [6] report accurate EUR/USD forecasts 2009&ndash;2015, and regional studies (an Indian-market verification [7]; a metals cycle study [8]) claim support &mdash; but these are largely in-sample, single-market, or analyst-discretion fits. The recurring critique is the same two problems: subjectivity of the count and data-snooping / hindsight.",s))
    e.append(P("<b>What we replicate.</b> Our multi-decade, multi-stock U.S. panel (1962&ndash;2026) overlaps Lo et al.'s era and design philosophy (automate the subjective; test broadly), and we adopt the out-of-sample + bootstrap discipline of [4]. We attack the two standard critiques directly: subjectivity &rarr; a fully deterministic, reproducible engine (golden-record hashed); data-snooping/hindsight &rarr; anonymized instruments (no names/dates/prices reach the analyst or the LLM), a hard no-lookahead boundary, and pre-registration of the LLM arm.",s))
    e.append(P("<b>What we do not (yet) replicate.</b> We test tradeable setups, not Lo et al.'s conditional-return-distribution estimand, so results are not directly comparable to [3]. We now bound data-snooping across the pivot-sensitivity parameter with a disjoint-selection test (&sect;5.1) but do not yet run White's Reality Check / Hansen's SPA across a full rule universe [4]. And unlike the positive regional EW studies [6&ndash;8], we forbid in-sample fitting and analyst-chosen counts &mdash; which plausibly explains why our out-of-sample result is weaker than their in-sample claims.",s))
    e.append(P("3. Methods",s,"H"))
    e.append(P("<b>3.1 Data.</b> 50 anonymized instruments (stock_id only), 588,427 daily OHLCV bars, 1962&ndash;2026, positive prices, no gaps.",s))
    e.append(P("<b>3.2 Engine.</b> Log-aware ZigZag pivots &rarr; bounded, beam-pruned, bidirectional sweep over motive (impulse, diagonals) and corrective (zigzag, flat, triangle) structures &rarr; scale-aware cardinal rules (W2&lt;W1; W3 not shortest; W4 overlap) + guideline scores (Fibonacci bands, alternation, equality, volume) &rarr; three-degree nesting (daily &sub; weekly &sub; monthly) &rarr; weighted scenarios + residual bucket &rarr; R/R-gated setup. Large moves are judged on log scale.",s))
    e.append(P("<b>3.3 Setup construction.</b> Entry/stop anchored to the completion pivot; reward/risk on log scale; degree-scaled invalidation and stop; degree-scaled evaluation horizon; stable ids to de-duplicate one structure re-seen across bars.",s))
    e.append(P("<b>3.4 No-lookahead &amp; determinism.</b> A signal at T uses only bars &le; T (as_of clamp + tripwire test); deterministic, golden-record hashed; frozen JSON carries data hash + engine version.",s))
    e.append(P("<b>3.5 Tester &amp; statistics.</b> An independent scorer resolves each setup against the continuation (won/lost/invalidated/expired; stop-first tie-break) and reports, per arm: win rate with a Wilson 95% interval; expectancy in R with a bootstrap 95% interval and a two-sided test that mean&ne;0; a random-direction permutation null (each setup's direction flipped by a coin, geometry mirrored in log space) for directional skill; a drift benchmark (buy-and-hold from entry, and every setup forced long) to separate market drift from wave skill; and calibration by grade and confidence bucket.",s))
    e.append(P("4. Results &mdash; deterministic engine",s,"H"))
    e.append(P(DET["reads"]+" point-in-time signal records across the 50 instruments (annual walk-forward, full history) yielded "+DET["setups"]+" distinct setups (the engine declines the great majority of the time).",s))
    e.append(kv([["Win rate",DET["win"],"Wilson95 "+DET["wilson"]],
                 ["Expectancy (raw)",DET["exp"]+"/trade","boot95 "+DET["boot"]+", p="+DET["p0"]],
                 ["Random-direction null",DET["null_mean"],DET["null_ci"]+", p(eng&ge;rand)="+DET["p_dir"]],
                 ["Anti (flipped) portfolio",DET["anti"],"beats anti, but see drift control"],
                 ["Grade A / Grade B",DET["A"],DET["B"]],
                 ["A beats B? / calibrated?",DET["A_beats_B"],DET["calibrated"]]],
                s,["Metric","Value","Inference"]))
    e.append(Spacer(1,5))
    e.append(P("<b>Drift control (the decisive test).</b> Raw expectancy is mildly positive and beats the direction-randomizing null (p=0.00) &mdash; but that null randomizes side, not market drift, so a mostly-long book in a rising market beats it by construction. Decomposing by side and benchmarking against simply holding the market removes the illusion:",s))
    e.append(kv([["Long setups",DRIFT["long"],"all the profit is here"],
                 ["Short setups",DRIFT["short"],"they lose"],
                 ["Force every setup long",DRIFT["alllong"],"beats the engine's +0.35R"],
                 ["Buy-and-hold from entry",DRIFT["bh"],"the actual drift"],
                 ["Engine alpha vs buy-and-hold",DRIFT["alpha"],"boot95 "+DRIFT["alpha_ci"]]],
                s,["Benchmark","Mean R","Reading"]))
    e.append(Spacer(1,5))
    e.append(P("<b>Reading.</b> The engine's positive expectancy is market drift, not wave skill: profit comes only from long setups, the short calls lose, and going long on every signal (+0.63R) beats the engine's selective book (+0.35R) &mdash; its directional choices subtract value. Against buy-and-hold the alpha is significantly negative (&minus;6.16R). So the engine is a strictly worse way to be long than holding the market, and its bootstrap expectancy interval spans zero regardless. Grade and confidence do not track outcomes (A&asymp;B; buckets non-monotonic). Net: no detectable wave-counting edge or directional skill on this sample; any latent signal would have to come from the weighting layer &mdash; tested next.",s))
    e.append(P("5. Robustness: can tuning or a learned weigher create an edge?",s,"H"))
    e.append(P("<b>5.1 The pivot-sensitivity switch.</b> The engine's highest-leverage free parameter is the pivot reversal threshold. We replaced the fixed-percentage threshold with a structural one &mdash; threshold = ln(1 + k&middot;ATR/close), measured on each timeframe's own bars &mdash; so a single coefficient k adapts sensitivity to each instrument's volatility. We then asked whether tuning k manufactures an edge, scoring direction against a geometry-matched random-side null. Selecting k by looking at a window makes that window glow: k=5 beat its null at p&asymp;0.03 and even replicated on a time-held-out split (p&asymp;0.02). But the decisive test holds out both the parameter and the instruments &mdash; one random half of the tickers chose k (it picked k=4), the other half was scored once:",s))
    e.append(kv([["k=5, selected on this window","28","obs +0.640 / null +0.041 (p=0.029)"],
                 ["k=5, time-held-out (pre-2015)","52","obs +0.777 / null +0.231 (p=0.018)"],
                 ["k=4, parameter + names held out","20","obs +0.072 / null +0.153 (p=0.591)"]],
                s,["Held-out test","n","Expectancy vs random-side null (R)"]))
    e.append(Spacer(1,4))
    e.append(P("On the fully held-out half the observed expectancy falls below the geometry null (negative gap, p=0.59) &mdash; no edge. The 'best' k is unstable (k=4 on one half, k=5 on the panel holdout) and the obs-vs-null gap collapses from +0.60/+0.55 to &minus;0.08 once selection is forbidden. This reproduces, inside our own pipeline, the central finding of [4]: apparent profitability that survives a single hold-out can still vanish once selection across configurations is accounted for.",s))
    e.append(P("<b>5.2 A learned weigher over the same features.</b> We built a supervised table (one row per candidate scenario: the anonymized structural features of &sect;3.2 plus its implied direction; label = whether that direction matched the sign of the forward 252-day return), trained a histogram gradient-boosted tree (depth 3, isotonic-calibrated) on one random half of the instruments, and evaluated once on the other half.",s))
    e.append(kv([["GBT, all features","0.674","apparently predictive"],
                 ["Implied-direction sign alone","0.675","explains all of it (drift)"],
                 ["GBT, structure only (no direction)","0.529","wave features &asymp; chance"],
                 ["GBT, structure only, long setups","0.467","no separation within a side"]],
                s,["Held-out predictor","AUC","Reading"]))
    e.append(Spacer(1,4))
    e.append(P("Held-out AUC of 0.674 is not wave skill: the identical AUC (0.675) comes from the implied-direction sign alone, because over 252-day windows the panel drifts up (P(correct | long)=0.70 vs 0.35 for short). Remove direction and wave structure alone gives AUC 0.529 (0.467 within long setups) &mdash; chance (label-shuffled null 0.502). The structural features carry essentially no out-of-sample directional information beyond drift, so a learned weigher over them can only follow drift &mdash; which &sect;4's benchmark already shows loses to buy-and-hold. The weigher's ceiling is feature information, not model class.",s))
    e.append(P("6. LLM scenario weigher &mdash; pre-registration &amp; controls",s,"H"))
    e.append(P("A drop-in weigher (local model via Ollama) re-weights the engine's existing candidate scenarios (and may change lead direction and confidence), leaving pivots/rules/structure/setup untouched. Controls: determinism (temperature 0 + response cache); no leakage (model sees only anonymized relative features &mdash; structure, degree, leg proportions, Fibonacci fit, price position); identical universe, tester, horizon. Pre-registered success: expectancy CI clearing zero, grade A &gt; B, monotonic confidence&ndash;win relationship, and the engine escaping the drift benchmark. A null result localizes the bottleneck in wave-counting rather than weighting.",s))
    e.append(P("7. Results &mdash; LLM weigher",s,"H"))
    e.append(kv([["Setups resolved",DET["setups"],"70"],
                 ["Win rate",DET["win"],LLM["win"]],
                 ["Expectancy",DET["exp"]+" "+DET["boot"],LLM["exp"]+" "+LLM["boot"]],
                 ["Grade A / B",DET["A"]+" / "+DET["B"],LLM["A"]+" / "+LLM["B"]],
                 ["A beats B? / calibrated?",DET["A_beats_B"]+" / "+DET["calibrated"],LLM["A_beats_B"]+" / "+LLM["calibrated"]]],
                s,["Metric","Deterministic","LLM ("+LLM["model"]+")"]))
    e.append(Spacer(1,3)); e.append(P(DISCUSSION_LLM,s))
    e.append(P("8. Toward greater statistical power (future work)",s,"H"))
    e.append(P("The dominant limitation is sample size (68 setups). Concrete steps: (a) monthly cadence on all 50 instruments and a wider universe &mdash; hundreds of setups, tightening every interval; (b) block bootstrap by instrument to respect within-name clustering; (c) explicit benchmarks &mdash; buy-and-hold (implemented; the engine loses to it) and a volatility-matched random-entry control; (d) a formal calibration curve with Brier score / expected calibration error once n permits; (e) White's Reality Check or Hansen's SPA when comparing multiple engine/weigher configurations, to bound data-snooping [4]; (f) transaction-cost and slippage sensitivity. Pre-registration (done for the LLM arm) constrains researcher degrees of freedom.",s))
    e.append(P("9. Limitations",s,"H"))
    e.append(P("Underpowered sample; annual cadence misses short-lived setups; one engine family with un-tuned secondary parameters (beam width, R/R floor, horizon scaling); frictionless, point-in-time; a test of one mechanization of EW, not discretionary practice. Research artifact, not trading advice.",s))
    e.append(P("10. Conclusion",s,"H"))
    e.append(P("A reproducible, pre-registered harness gives a precise answer on this universe: the mechanical engine has no statistically detectable out-of-sample edge and no wave-counting skill. Its mildly positive raw expectancy is market drift &mdash; long setups profit, short setups lose, an all-long book beats the engine's selective one, and the engine underperforms buy-and-hold by a significant margin. Neither tuning the most powerful parameter (an apparent edge that vanished once parameter and instruments were both held out) nor a learned weigher (whose skill was drift, not structure) nor a local-LLM weigher (which slightly worsened calibration) changed this. The bottleneck is the information in the wave-count features, not the weighting model &mdash; reproducing, inside our own pipeline, the data-snooping and no-edge cautions of the technical-analysis literature [3,4].",s))
    e.append(P("References",s,"H"))
    for r in [
      "[1] Frost, A. J. &amp; Prechter, R. R. Elliott Wave Principle: Key to Market Behavior. New Classics Library (1978; 10th ed. 2005).",
      "[2] EW subjectivity/critique summarized in [3,4].",
      "[3] Lo, A. W., Mamaysky, H. &amp; Wang, J. (2000). Foundations of Technical Analysis. Journal of Finance 55(4), 1705&ndash;1765.",
      "[4] Sullivan, R., Timmermann, A. &amp; White, H. (1999). Data-Snooping, Technical Trading Rule Performance, and the Bootstrap. Journal of Finance 54(5), 1647&ndash;1691.",
      "[5] Brock, W., Lakonishok, J. &amp; LeBaron, B. (1992). Simple Technical Trading Rules and the Stochastic Properties of Stock Returns. Journal of Finance 47(5), 1731&ndash;1764.",
      "[6] D'Angelo, E. &amp; Grimaldi, G. (2017). The Effectiveness of the Elliott Waves Theory to Forecast Financial Markets: Evidence from the Currency Market. International Business Research 10(6), 1&ndash;18.",
      "[7] Chendroyaperumal, C. &amp; Karthikeyan, B. Empirical Verification of Elliott Wave Theory in the Indian Stock Market. SSRN working paper 1887789.",
      "[8] Exploring the Elliott Wave Principle to interpret metal commodity price cycles. Resources Policy (Elsevier), 2018.",
    ]:
        e.append(P(r,s,"Ref"))
    e.append(Spacer(1,6))
    e.append(P("Artifacts: engine ewt/; testers tester.py, aggregate_tester.py (Wilson/bootstrap/null); disjoint-selection sweep_sensitivity.py (--pivot-mode atr); weigher ewt/weigh/; runners batch_universe.py, weighed_walkforward.py; protocol EXPERIMENT.md, RUN_LLM_ARM.md.",s))
    SimpleDocTemplate(str(OUT),pagesize=A4,topMargin=1.5*cm,bottomMargin=1.5*cm,leftMargin=1.7*cm,rightMargin=1.7*cm,title="EWT reliability paper",author="Thomas").build(e)
    print("wrote",OUT)

if __name__=="__main__":
    build()
