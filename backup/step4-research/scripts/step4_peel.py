"""Step 4 (redo), part 4: peel the bodies one by one, from the outside in.

Part 3 found the outermost body from the dots beyond the gap in |X| at 16 Rj.
The same trick is repeated: take away the dots the bodies found so far explain,
look at what is left, and find the next gap in |X|. Beyond it only one body
reaches, so it can be folded on its own, with the same three pieces of
evidence (dots, one-night speeds, "should be there but isn't").

A photo counts as "nothing out there" for the new body only if it sees beyond
the limit on both sides, has no unexplained dot there, and no body already
found sits out there (its dot could hide the new one).

Stop when what is left no longer has a clear gap, or a body would explain
fewer than MIN_DOTS dots.

Output: output/step4/peel.json; demo/step4_data.json gets "peel".
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from step4_fold import scan_periods, _view, T_REF  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "step4"
MIN_DOTS = 8
MIN_GAP = 0.6            # Rj: a gap in the sorted |X| narrower than this is not a gap
HIDE = 2.0               # Rj: Jupiter's glare


def sig(X):
    return 0.35 + 0.08 * np.abs(X)


def swing(b, t):
    w = 2 * np.pi * b["freq"]
    return b["a"] * np.sin(w * t) + b["b"] * np.cos(w * t)


def explained(b, t, X):
    return np.abs(X - swing(b, t)) < 1.0 * sig(swing(b, t))


def find_gap(absx, prev_limit):
    """Widest gap among the outer part of the remaining |X|; returns its middle."""
    x = np.sort(absx[(absx > 3) & (absx < prev_limit)])
    if len(x) < MIN_DOTS:
        return None
    top = x[len(x) // 3:]                       # look in the outer two thirds only
    g = np.diff(top)
    i = int(np.argmax(g))
    if g[i] < MIN_GAP:
        return None
    return float((top[i] + top[i + 1]) / 2), float(g[i])


def load():
    view = _view()
    dots = []
    for r in csv.DictReader(open(ROOT / "output/step2/positions.csv")):
        if r["strong"] != "True" or r["in_band"] != "True":
            continue
        dots.append({"photo": r["photo"], "dot": int(r["dot"]), "t": view[r["photo"]][1],
                     "X": float(r["X_rj"]), "Y": float(r["Y_rj"])})
    tracks = []
    for n, night in json.load(open(OUT / "tracks.json")).items():
        t0 = (datetime.fromisoformat(night["start"]) - T_REF).total_seconds() / 86400
        for k in night["tracks"]:
            if k["speed_rj_per_h"] is None or len(k["points"]) < 3:
                continue
            tracks.append({"night": n, "t": t0 + float(np.mean([p["t_h"] for p in k["points"]])) / 24,
                           "X": float(np.mean([p["X"] for p in k["points"]])),
                           "v": 24 * k["speed_rj_per_h"], "err": 24 * k["speed_err"],
                           "members": [(p["photo"], p["dot"]) for p in k["points"]]})
    return dots, tracks, view


def peel(dots, tracks, view, first_limit=16.0, max_bodies=6):
    t = np.array([d["t"] for d in dots]); X = np.array([d["X"] for d in dots])
    owner = np.full(len(dots), -1)
    key = {(d["photo"], d["dot"]): i for i, d in enumerate(dots)}
    photos = sorted({d["photo"] for d in dots} | set(view))
    bodies, limit = [], 1e9
    for k in range(max_bodies):
        free = owner < 0
        if k == 0:
            limit, gap = first_limit, None
        else:
            g = find_gap(np.abs(X[free]), limit)
            if g is None:
                break
            limit, gap = g
        sel = free & (np.abs(X) > limit)
        if sel.sum() < MIN_DOTS:
            break
        # empty photos: see beyond the limit both ways, no free dot there, no known body out there
        empty = []
        for s in photos:
            (lo, hi), ts = view[s]
            if not (lo < -(limit + 2) and hi > limit + 2):
                continue
            mine = [i for i, d in enumerate(dots) if d["photo"] == s]
            if any(free[i] and abs(X[i]) > limit for i in mine):
                continue
            if any(abs(swing(b, ts)) > limit - 1 for b in bodies):
                continue
            empty.append(ts)
        sp = [tr for tr in tracks if abs(tr["X"]) > limit
              and all(free[key[m]] for m in tr["members"] if m in key)]
        res = scan_periods(t[sel], X[sel], t_empty=np.array(empty), limit=limit, err=sig(X[sel]),
                           vt=np.array([s["t"] for s in sp]), v=np.array([s["v"] for s in sp]),
                           verr=np.array([s["err"] for s in sp]))
        b = res["best"]
        hit = free & explained(b, t, X)
        b.update({"limit_rj": limit, "gap_rj": gap, "n_used": int(sel.sum()), "n_empty": len(empty),
                  "n_speeds": len(sp), "n_explained": int(hit.sum()),
                  "rivals": [{"period_d": r["period_d"], "score": r["score"]} for r in res["rivals"][:5]],
                  "used": [int(i) for i in np.where(sel)[0]], "empty_t": empty,
                  "curve": {"period_d": [1 / f for f in res["curve"]["freq"][::5]], "score": res["curve"]["score"][::5]}})
        print(f"body {k + 1}: limit {limit:.2f} Rj (gap {gap}), {sel.sum()} dots, {len(empty)} empty photos, "
              f"{len(sp)} speeds -> P = {b['period_d']:.4f} ± {b['period_err_d']:.4f} d, reach {b['reach_rj']:.2f}, "
              f"red chi2 {b['reduced_chi2']:.2f}, explains {hit.sum()}; rivals "
              + ", ".join(f"{r['period_d']:.3f}({r['score']:.0f})" for r in res["rivals"][1:4]), file=sys.stderr)
        owner[hit | sel] = k
        bodies.append(b)
    return bodies, owner


def main():
    dots, tracks, view = load()
    bodies, owner = peel(dots, tracks, view, max_bodies=2)
    left = [dots[i] for i in np.where(owner < 0)[0]]
    print(f"left unexplained: {len(left)} dots, |X| =", sorted(round(abs(d['X']), 1) for d in left), file=sys.stderr)
    out = {"bodies": bodies, "owner": owner.tolist(),
           "dots": [{"t": d["t"], "X": d["X"], "Y": d["Y"], "photo": d["photo"], "dot": d["dot"]} for d in dots]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "peel.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    p = ROOT / "demo" / "step4_data.json"
    data = json.loads(p.read_text()); data["peel"] = out
    p.write_text(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
