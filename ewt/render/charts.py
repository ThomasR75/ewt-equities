"""Pivot charts (M1).

Candlesticks on a log scale with the detected zigzag overlaid: line through the
pivots, H/L markers, and a partial-bar note. Later milestones add wave labels,
level lines, channels and the zoom inset (spec §14); the scaffolding here is
built to extend.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402

from ..schemas import Bars, PivotSeries

_TF_NAME = {"D": "Daily", "W": "Weekly", "M": "Monthly"}


def plot_pivots(
    bars: Bars,
    pivots: PivotSeries,
    out_path: str | Path,
    title: str | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = bars.df

    title = title or (
        f"{_TF_NAME.get(bars.tf, bars.tf)} — {len(pivots)} pivots "
        f"(as of {bars.as_of.date()}{', partial bar' if bars.is_partial else ''})"
    )

    # Zigzag line as an addplot aligned to the bar index.
    zz = df["close"].copy()
    zz[:] = float("nan")
    for p in pivots.pivots:
        zz.iloc[p.idx] = p.price
    zz = zz.interpolate(limit_area="inside")

    apds = [mpf.make_addplot(zz, color="#2563eb", width=1.3)]

    fig, axes = mpf.plot(
        df[["open", "high", "low", "close", "volume"]],
        type="candle",
        style="yahoo",
        addplot=apds,
        volume=True,
        yscale="log",
        figsize=(13, 7),
        returnfig=True,
        warn_too_much_data=10_000,
        tight_layout=True,
        datetime_format="%Y-%m",
        xrotation=0,
    )
    ax = axes[0]
    ax.set_title(title, fontsize=12, loc="left")

    # Mark pivots: red ▼ for highs, green ▲ for lows.
    for p in pivots.pivots:
        ax.annotate(
            "▼" if p.kind == "H" else "▲",
            xy=(p.idx, p.price),
            xytext=(0, 7 if p.kind == "H" else -14),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#dc2626" if p.kind == "H" else "#16a34a",
        )

    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_three_degrees(
    tf_bars: dict[str, Bars],
    tf_pivots: dict[str, PivotSeries],
    out_dir: str | Path,
    ticker: str,
) -> list[Path]:
    out_dir = Path(out_dir)
    paths = []
    for tf in ["M", "W", "D"]:
        if tf not in tf_bars:
            continue
        as_of = tf_bars[tf].as_of.date()
        p = plot_pivots(
            tf_bars[tf],
            tf_pivots[tf],
            out_dir / f"{ticker}-{as_of}-{tf}.png",
            title=f"{ticker} — {_TF_NAME[tf]} — {len(tf_pivots[tf])} pivots (as of {as_of})",
        )
        paths.append(p)
    return paths
