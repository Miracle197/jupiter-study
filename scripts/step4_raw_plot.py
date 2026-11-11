"""Step 4 (redo), part 0: the raw material, with no bodies assumed.

Every bright dot in the band (step 3 orientation, step 1 scale) as X against
time. No colours per body, no fitted curves, no step-4 scale correction --
just what the photos give. Error bars = photo error of X from step 2.

Output: output/step4/raw_dots.png
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent.parent
POS = ROOT / "output" / "step2" / "positions.csv"
OUT = ROOT / "output" / "step4"


def load(path=POS):
    rows = []
    for r in csv.DictReader(open(path)):
        if r["strong"] != "True" or r["in_band"] != "True":
            continue
        rows.append((datetime.fromisoformat(r["local_time"]), float(r["X_rj"]), float(r["err_photo_X_rj"])))
    return rows


def plot(rows, out):
    fig = plt.figure(figsize=(14, 9), facecolor="#151a24")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1])
    axes = [fig.add_subplot(gs[0, :]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
    spans = [None, (datetime(2024, 1, 8, 17), datetime(2024, 1, 9, 1, 30)),
             (datetime(2024, 1, 9, 16, 30), datetime(2024, 1, 10, 1, 0))]
    titles = ["All bright dots, 2023-12-03 to 2024-01-11 (205 dots, 58 photos)",
              "Night of 2024-01-08", "Night of 2024-01-09"]
    for ax, span, title in zip(axes, spans, titles):
        ax.set_facecolor("#151a24")
        sel = [r for r in rows if span is None or span[0] <= r[0] <= span[1]]
        ax.axhspan(-2, 2, color="#2a303c", lw=0)
        ax.errorbar([r[0] for r in sel], [r[1] for r in sel], yerr=[r[2] for r in sel],
                    fmt="o", ms=3.5, color="#d8dee9", ecolor="#8891a0", elinewidth=0.8, capsize=1.5)
        ax.axhline(0, color="#4c566a", lw=0.6)
        ax.set_ylim(-30, 30)
        if span:
            ax.set_xlim(*span)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.set_title(title, color="#d8dee9", fontsize=10)
        ax.set_ylabel("X (Jupiter radii)", color="#aeb6c4")
        ax.tick_params(colors="#aeb6c4")
        for s in ax.spines.values():
            s.set_color("#4c566a")
        ax.grid(color="#2e3440", lw=0.6)
    fig.text(0.01, 0.005, "dots: positions along the line, step 1 scale only; bars: photo error; "
             "grey band: Jupiter's glare (|X|<2). No bodies, curves or step-4 corrections.",
             color="#8891a0", fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    rows = load()
    plot(rows, OUT / "raw_dots.png")
    import json
    data = {"dots": [{"t": r[0].isoformat(timespec="minutes"), "X": r[1], "err": r[2]} for r in rows]}
    (ROOT / "demo" / "step4_data.json").write_text(json.dumps(data, ensure_ascii=False))
    print(len(rows), "dots,", len({r[0] for r in rows}), "photo times ->", OUT / "raw_dots.png", file=sys.stderr)
