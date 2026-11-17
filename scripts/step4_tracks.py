"""Step 4 (redo), part 2: within one night, which dots belong together?

No bodies, periods or curves are assumed. On a night with several photos a
dot moves only a little between photos, so a dot is linked to the dot in the
next photo that sits where it should be next:
  * along the line: where the track's own recent motion puts it (with one point
    only, near where it was; the allowed distance grows with the time gap),
  * across the line: at about the same Y (a body keeps to its own side of the
    line during one night -- this is what tells two crossing bodies apart).
A track that finds no dot in a photo is kept (it may be hidden in Jupiter's
glare or behind another dot) and can pick up again later the same night.

Output: output/step4/tracks.json, demo/step4_data.json gets "nights".
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
POS = ROOT / "output" / "step2" / "positions.csv"
OUT = ROOT / "output" / "step4"

SIG_Y = 0.25          # Rj: how far a dot may wander across the line between photos
SIG_X0 = 0.35         # Rj: centring + scale error along the line
SIG_X_REL = 0.08      # scale error (step 1: ~6% per photo) grows with distance from Jupiter
SPEED_MAX = 1.5       # Rj/h: generous bound on along-line speed for the first link only
Y_GATE = 2.5          # across-line jump larger than this (in sigma) is never one body
GATE = 3.0            # a link must cost less than this (in sigma, combined)


def _predict(tr, t):
    """Where a track should be at time t (along X), and how sure that is.

    The speed comes from a straight line through the track's points; over a short
    stretch of time it is poorly known (each photo's scale is good to only ~6%),
    so its uncertainty is (position error) / (time covered), and never above SPEED_MAX.
    """
    p = tr["points"]
    last = p[-1]
    dt = t - last["t_h"]
    sx = SIG_X0 + SIG_X_REL * abs(last["X"])
    if len(p) == 1:
        return last["X"], sx + SPEED_MAX * abs(dt)
    tt = np.array([q["t_h"] for q in p]); xx = np.array([q["X"] for q in p])
    v, c = np.polyfit(tt, xx, 1)
    v = float(np.clip(v, -SPEED_MAX, SPEED_MAX))
    sv = min(np.sqrt(2) * sx / max(tt[-1] - tt[0], 1e-3), SPEED_MAX)
    return float(c + v * tt[-1] + v * dt), sx + sv * abs(dt)


def _cost(tr, d, t):
    xp, sx = _predict(tr, t)
    yp = np.mean([q["Y"] for q in tr["points"][-3:]])
    cy = (d["Y"] - yp) / SIG_Y
    if abs(cy) > Y_GATE:                        # wrong side of the line: a different body
        return np.inf
    return float(np.hypot((d["X"] - xp) / sx, cy))


def link_night(photos):
    """photos: [{"t_h": hours, "dots": [{"X","Y", ...}]}] -> list of tracks."""
    tracks = []
    for ph in sorted(photos, key=lambda p: p["t_h"]):
        t = ph["t_h"]
        pairs = sorted((_cost(tr, d, t), k, m) for k, tr in enumerate(tracks) for m, d in enumerate(ph["dots"]))
        used_t, used_d = set(), set()
        for c, k, m in pairs:                   # cheapest links first
            if c > GATE or k in used_t or m in used_d:
                continue
            used_t.add(k); used_d.add(m)
            tracks[k]["points"].append(dict(ph["dots"][m], t_h=t))
        for m, d in enumerate(ph["dots"]):
            if m not in used_d:
                tracks.append({"points": [dict(d, t_h=t)]})
    for tr in tracks:
        p = tr["points"]
        if len(p) >= 2:
            tt = np.array([q["t_h"] for q in p]); xx = np.array([q["X"] for q in p])
            tr["speed"] = float(np.polyfit(tt, xx, 1)[0])
            # photo error of the speed: each X is good to ~SIG_X, spread over the time covered
            sx = np.array([SIG_X0 + SIG_X_REL * abs(x) for x in xx])
            tr["speed_err"] = float(np.sqrt(1 / np.sum((tt - tt.mean()) ** 2 / sx ** 2)))
        else:
            tr["speed"] = tr["speed_err"] = None
        tr["Y_mean"] = float(np.mean([q["Y"] for q in p]))
    tracks.sort(key=lambda tr: -np.mean([q["X"] for q in tr["points"]]))
    return tracks


def load(path=POS):
    nights = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(path)):
        if r["strong"] != "True" or r["in_band"] != "True":
            continue
        nights[r["night"]][(r["local_time"], r["photo"])].append(
            {"X": float(r["X_rj"]), "Y": float(r["Y_rj"]), "err": float(r["err_photo_X_rj"]),
             "photo": r["photo"], "dot": int(r["dot"])})
    out = {}
    for n, ph in nights.items():
        if len(ph) < 3:                         # need at least three photos to see motion
            continue
        t0 = min(datetime.fromisoformat(lt) for lt, _ in ph)
        out[n] = [{"t_h": (datetime.fromisoformat(lt) - t0).total_seconds() / 3600, "time": lt, "photo": s, "dots": d}
                  for (lt, s), d in sorted(ph.items())]
    return out


def main():
    nights = load()
    res = {}
    for n, photos in sorted(nights.items()):
        tracks = link_night(photos)
        start = photos[0]["time"]
        res[n] = {"start": start, "photos": [{"time": p["time"], "t_h": p["t_h"], "n": len(p["dots"])} for p in photos],
                  "tracks": [{"speed_rj_per_h": tr["speed"], "speed_err": tr["speed_err"], "Y_mean": tr["Y_mean"],
                              "points": [{k: q[k] for k in ("t_h", "X", "Y", "err", "photo", "dot")} for q in tr["points"]]}
                             for tr in tracks]}
        desc = ", ".join(f"{len(tr['points'])}pt " + ("—" if tr["speed"] is None else f"{tr['speed']:+.2f}/h")
                         for tr in tracks)
        print(f"{n}: {len(photos)} photos, {len(tracks)} tracks: {desc}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tracks.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    p = ROOT / "demo" / "step4_data.json"
    data = json.loads(p.read_text()) if p.exists() else {}
    data["nights"] = res
    p.write_text(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
