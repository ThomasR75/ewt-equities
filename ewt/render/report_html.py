"""Self-contained HTML report (single file, charts embedded as base64).

Same content as the markdown report (spec §2/§14), styled for reading and fully
portable: the three degree charts are inlined as data URIs, so the .html can be
opened or emailed without any accompanying image files.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path


def _img_data_uri(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _esc(x) -> str:
    return html.escape(str(x))


def _scenario_rows(scenarios: list[dict]) -> str:
    out = []
    for s in scenarios:
        cls = " class='residual'" if s.get("is_residual") else ""
        out.append(
            f"<tr{cls}><td>{s['rank']}</td><td>{_esc(s['path'])}</td>"
            f"<td class='num'>{s['weight']*100:.0f}%</td>"
            f"<td>{_esc(s.get('invalidation','') or '—')}</td></tr>"
        )
    return "".join(out)


def _trade_plan_html(rec: dict) -> str:
    s = rec["setup"]
    if s is None or rec["grade"] is None:
        reason = ("no directional structure" if s is None
                  else f"R/R {s['rr']} below the 2.0 floor")
        return f"<p class='nosetup'><b>No setup</b> — {_esc(reason)}. A read, not a trade.</p>"
    return (
        "<table><thead><tr><th>ID</th><th>Grade</th><th>Dir</th><th>Entry</th>"
        "<th>Stop</th><th>T1</th><th>T2</th><th>R/R</th></tr></thead><tbody>"
        f"<tr><td>{_esc(s['id'])}</td><td class='grade'>{_esc(s['grade'])}</td>"
        f"<td>{_esc(s['direction'])}</td>"
        f"<td class='num'>{s['entry']} ({_esc(s['entry_type'])})</td>"
        f"<td class='num'>{s['stop']}</td><td class='num'>{s['t1']}</td>"
        f"<td class='num'>{s['t2']}</td><td class='num'>{s['rr']}</td></tr></tbody></table>"
    )


def _scorecard_html(rows: list[dict]) -> str:
    if not rows:
        return "<p class='muted'>No prior setups — first record for this ticker.</p>"
    body = "".join(
        f"<tr><td>{_esc(r['id'])}</td><td>{_esc(r['issued'])}</td>"
        f"<td>{_esc(r['direction'])}</td><td>{_esc(r['grade'] or '—')}</td>"
        f"<td>{_esc(r['status'])}</td><td class='num'>{_esc(r['pnl_r'])}</td></tr>"
        for r in rows
    )
    return ("<table><thead><tr><th>ID</th><th>Issued</th><th>Dir</th><th>Grade</th>"
            f"<th>Status</th><th>PnL (R)</th></tr></thead><tbody>{body}</tbody></table>")


_CSS = """
:root{--fg:#1f2937;--muted:#6b7280;--line:#e5e7eb;--accent:#7c3aed;--bg:#ffffff}
*{box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
color:var(--fg);background:var(--bg);max-width:980px;margin:0 auto;padding:32px 24px;line-height:1.55}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.1rem;margin:1.8rem 0 .6rem;
border-bottom:1px solid var(--line);padding-bottom:.3rem}
.headline{background:#f9fafb;border-left:3px solid var(--accent);padding:12px 16px;border-radius:4px}
.nested{color:var(--muted);font-size:.92rem;margin-top:.4rem}
table{border-collapse:collapse;width:100%;font-size:.92rem;margin:.4rem 0}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{background:#f3f4f6;font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}
tr.residual{color:var(--muted);font-style:italic}
td.grade{font-weight:700;color:var(--accent)}
.pivot{font-size:1.05rem;font-weight:600}
.nosetup{background:#fff7ed;border-left:3px solid #f59e0b;padding:10px 14px;border-radius:4px}
.muted{color:var(--muted)}
.chart{margin:14px 0}.chart img{width:100%;border:1px solid var(--line);border-radius:6px}
.chart h3{margin:.4rem 0;font-size:.95rem;color:var(--muted)}
footer{margin-top:2rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--line);padding-top:.6rem}
.sig{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.85rem;font-weight:600}
.sig.none{background:#f3f4f6;color:#6b7280}.sig.long{background:#dcfce7;color:#166534}
.sig.short{background:#fee2e2;color:#991b1b}
"""


def build_report_html(ticker, rec, charts, scorecard_rows, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    d = rec["data"]
    nr = rec.get("nested_read")

    from .narrative import headline
    sig = rec["signal"]
    conf = rec["confidence_pct"]
    grade = rec["grade"] or "—"

    chart_html = ""
    names = {"M": "Monthly", "W": "Weekly", "D": "Daily"}
    for tf in ["M", "W", "D"]:
        uri = _img_data_uri(charts.get(tf, "")) if charts else None
        if uri:
            chart_html += f"<div class='chart'><h3>{names[tf]}</h3><img src='{uri}'></div>"

    parts = [
        f"<h1>{_esc(ticker)} — Elliott Wave analysis</h1>",
        f"<p class='muted'>as of {_esc(d['as_of'])} · last {_esc(d['last_price'])} · "
        f"<span class='sig {_esc(sig)}'>{_esc(sig.upper())}</span> · "
        f"grade {_esc(grade)} · confidence {conf}%</p>",
        f"<div class='headline'>{_esc(headline(ticker, rec))}</div>",
    ]
    if nr:
        parts.append(f"<p class='nested'><b>Nested structure:</b> {_esc(nr['note'])} "
                     f"(alignment {nr['alignment']}).</p>")
    parts.append("<h2>Scenarios</h2><table><thead><tr><th>#</th><th>Path</th>"
                 "<th>Weight</th><th>Invalidation</th></tr></thead><tbody>"
                 + _scenario_rows(rec["scenarios"]) + "</tbody></table>")
    parts.append("<h2>Trade plan</h2>" + _trade_plan_html(rec))
    pl = rec.get("pivot_level")
    parts.append("<h2>The one level that matters next</h2>"
                 + (f"<p class='pivot'>{_esc(pl)}</p><p class='muted'>Highest-confluence "
                    f"level; it gates the lead scenario and the trade trigger.</p>"
                    if pl is not None else "<p class='muted'>None identified.</p>"))
    parts.append("<h2>Prior setups (scorecard)</h2>" + _scorecard_html(scorecard_rows))
    if chart_html:
        parts.append("<h2>Charts</h2>" + chart_html)
    parts.append(f"<footer>engine {_esc(rec['engine_version'])} · data_hash "
                 f"{_esc(d['data_hash'][:12])}… · schema v{rec['schema_version']}</footer>")

    doc = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{_esc(ticker)} EW report {_esc(d['as_of'])}</title>"
           f"<style>{_CSS}</style></head><body>{''.join(parts)}</body></html>")
    out_path.write_text(doc, encoding="utf-8")
    return out_path
