"""Annotated motive-count chart (M2): wave labels + key fib levels.

Extends the M1 pivot chart with the lead count's 0-1-2-3-4-5 labels at its
pivots and horizontal lines for the strongest confluence zones / fib levels.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402

from ..schemas import Bars, Count, FibLevel

_TF_NAME = {"D": "Daily", "W": "Weekly", "M": "Monthly"}


def plot_count(
    bars: Bars,
    count: Count,
    levels: list[FibLevel],
    out_path: str | Path,
    title: str | None = None,
    max_lines: int = 8,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = bars.df

    pivots = [count.legs[0].start] + [leg.end for leg in count.legs]
    labels = count.labels

    # Wave skeleton as an addplot line through the labeled pivots.
    zz = df["close"].copy()
    zz[:] = float("nan")
    for p in pivots:
        zz.iloc[p.idx] = p.price
    zz = zz.interpolate(limit_area="inside")
    apds = [mpf.make_addplot(zz, color="#7c3aed", width=1.6)]

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
    title = title or (
        f"{_TF_NAME.get(bars.tf, bars.tf)} — {count.structure} "
        f"(score {count.score:.2f}, as of {bars.as_of.date()})"
    )
    ax.set_title(title, fontsize=12, loc="left")

    # Wave labels.
    for lab, p in zip(labels, pivots):
        up = p.kind == "H"
        ax.annotate(
            lab,
            xy=(p.idx, p.price),
            xytext=(0, 11 if up else -16),
            textcoords="offset points",
            ha="center",
            fontsize=11,
            fontweight="bold",
            color="#111827",
            bbox=dict(boxstyle="circle,pad=0.18", fc="#fde68a", ec="#92400e", lw=0.8),
        )

    # Key fib levels as right-annotated horizontal lines.
    xmax = len(df) - 1
    for fl in levels[:max_lines]:
        ax.axhline(fl.price, color="#9ca3af", lw=0.7, ls="--", alpha=0.8)
        ax.annotate(
            f"{fl.label} · {fl.price:.2f}",
            xy=(xmax, fl.price),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=7.5,
            color="#374151",
        )

    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path
