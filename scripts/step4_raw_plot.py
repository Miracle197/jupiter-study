"""Step 4 (redo), part 0: the raw material, with no bodies assumed.

Every bright dot in the band (step 3 orientation, step 1 scale) as X against
time, over the whole run. No colours per body, no fitted curves, no step-4
scale correction -- just what the photos give. Error bars = photo error of X
from step 2.

Output: output/step4/raw_dots.png, demo/step4_data.json
"""
import csv
import json
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
        rows.append((r["photo"], datetime.fromisoformat(r["local_time"]), float(r["X_rj"]),
                     float(r["err_photo_X_rj"])))
    return rows


def plot(rows, out):
    fig, ax = plt.subplots(figsize=(14, 6), facecolor="#151a24")
    ax.set_facecolor("#151a24")
    ax.axhspan(-2, 2, color="#2a303c", lw=0)
    ax.errorbar([r[1] for r in rows], [r[2] for r in rows], yerr=[r[3] for r in rows],
                fmt="o", ms=3.5, color="#d8dee9", ecolor="#8891a0", elinewidth=0.8, capsize=1.5)
    ax.axhline(0, color="#4c566a", lw=0.6)
    ax.set_ylim(-30, 30)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    n_photos = len({r[0] for r in rows})
    ax.set_title(f"All bright dots, 2023-12-03 to 2024-01-11 ({len(rows)} dots, {n_photos} photos)",
                 color="#d8dee9", fontsize=10)
    ax.set_ylabel("X (Jupiter radii)", color="#aeb6c4")
    ax.tick_params(colors="#aeb6c4")
    for s in ax.spines.values():
        s.set_color("#4c566a")
    ax.grid(color="#2e3440", lw=0.6)
    fig.text(0.01, 0.01, "dots: positions along the line, step 1 scale only; bars: photo error; "
             "grey band: Jupiter's glare (|X|<2). No bodies, curves or step-4 corrections.",
             color="#8891a0", fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    rows = load()
    plot(rows, OUT / "raw_dots.png")
    p = ROOT / "demo" / "step4_data.json"
    data = json.loads(p.read_text()) if p.exists() else {}          # keep what the other step 4 scripts wrote
    data["dots"] = [{"t": r[1].isoformat(timespec="minutes"), "X": r[2], "err": r[3]} for r in rows]
    p.write_text(json.dumps(data, ensure_ascii=False))
    print(len(rows), "dots,", len({r[0] for r in rows}), "photos ->", OUT / "raw_dots.png", file=sys.stderr)
