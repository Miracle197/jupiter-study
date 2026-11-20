"""Step 4 (redo), part 4b: the inner bodies, found as a pair.

After the two outer bodies (part 4, peel by gaps in |X|) the dots left all sit
within ~9 Rj, and there is no clean gap any more: inside, two bodies overlap.
Folding the outer part alone then gives several periods that look about equally
good (the dots of the other body get in the way). So the inner ones are found
together:

  1. candidates for the outer of the two: the best few periods from folding
     the remaining dots beyond 6.7 Rj (the last small gap);
  2. for each candidate, every partner period is tried: dots are shared between
     the two swings (each dot to the nearer one), both swings refitted, repeated;
  3. the pair is scored on (a) how far each leftover dot is from the nearer
     swing and (b) "should be there but isn't": a swing that puts its body in
     plain view in a photo (outside the glare, inside the frame) where no dot is.

The pair that explains the dots AND never predicts a body where there is none
wins. Nothing about how many bodies there are is assumed beyond "try two".

Output: output/step4/inner.json; demo/step4_data.json gets "inner".
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import step4_peel as P  # noqa: E402
from step4_fold import scan_periods  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "step4"
MISS_COST = 9.0           # one "should be there but isn't" = a 3-sigma miss
F_GRID = np.arange(0.02, 2.0, 0.001)


def setup():
    dots, tracks, view = P.load()
    bodies, owner = P.peel(dots, tracks, view, max_bodies=2)
    t = np.array([d["t"] for d in dots]); X = np.array([d["X"] for d in dots])
    known = np.array([[P.swing(b, tt) for b in bodies] for tt in t])
    dk = np.min(np.abs(X[:, None] - known) / P.sig(known), 1)
    free = (dk > 2) & (np.abs(X) > P.HIDE)
    return dots, view, bodies, t, X, free


def outer_limit(absx, lo=P.MIN_DOTS, hi=3 * P.MIN_DOTS):
    """The last small gap in the leftover |X|: the widest one with lo..hi dots beyond it (its middle).

    Beyond it lie the outer swings of the outer one of the two inner bodies; folding those
    alone gives the candidates for its period.
    """
    x = np.sort(absx[absx > P.HIDE])
    beyond = len(x) - 1 - np.arange(len(x) - 1)
    g = np.where((beyond >= lo) & (beyond <= hi), np.diff(x), -1.0)
    i = int(np.argmax(g))
    return float((x[i] + x[i + 1]) / 2), float(g[i])


def fitsine(f, t, X, m):
    w = 2 * np.pi * f; s = P.sig(X[m])
    ab = np.linalg.lstsq(np.c_[np.sin(w * t[m]), np.cos(w * t[m])] / s[:, None], X[m] / s, rcond=None)[0]
    return {"freq": float(f), "a": float(ab[0]), "b": float(ab[1])}


def pair(f3, f4, t, X, free, limit, it=4):
    m3 = free & (np.abs(X) > limit); m4 = free & ~m3
    b3 = b4 = None
    for _ in range(it):
        if m3.sum() < 4 or m4.sum() < 4:
            return None
        b3, b4 = fitsine(f3, t, X, m3), fitsine(f4, t, X, m4)
        d3 = np.abs(X - P.swing(b3, t)) / P.sig(P.swing(b3, t))
        d4 = np.abs(X - P.swing(b4, t)) / P.sig(P.swing(b4, t))
        m3 = free & (d3 <= d4) & (d3 < 3); m4 = free & (d4 < d3) & (d4 < 3)
    return b3, b4


def dot_cost(bs, t, X, free):
    pr = np.array([P.swing(b, t) for b in bs]).T
    d = np.abs(X[:, None] - pr) / P.sig(pr)
    return float(np.sum(np.minimum(d.min(1)[free], 3) ** 2))


def misses(bs, dots, view):
    out = []
    by_photo = {}
    for d in dots:
        by_photo.setdefault(d["photo"], []).append(d["X"])
    for s, ((lo, hi), ts) in view.items():
        xs = np.array(by_photo.get(s, []))
        for k, b in enumerate(bs):
            p = P.swing(b, ts)
            if abs(p) > 3 and lo < p < hi and not np.any(np.abs(xs - p) < 2 * P.sig(p)):
                out.append({"photo": s, "body": k, "X_pred": float(p)})
    return out


def main():
    dots, view, outer, t, X, free = setup()
    limit, gap = outer_limit(np.abs(X[free]))
    sel = free & (np.abs(X) > limit)
    cand = scan_periods(t[sel], X[sel], err=P.sig(X[sel]), n_rivals=6)["rivals"]
    print(f"leftover dots {free.sum()} (|X| up to {np.abs(X[free]).max():.2f}), beyond {limit:.2f} Rj "
          f"(gap {gap:.2f}): {sel.sum()}", file=sys.stderr)
    trials = []
    for c in cand:
        f3 = c["freq"]
        best = None
        for f4 in F_GRID:
            if abs(f4 - f3) < 0.01:
                continue
            r = pair(f3, f4, t, X, free, limit, it=3)
            if r is None:
                continue
            cst = dot_cost(r, t, X, free)
            if best is None or cst < best[0]:
                best = (cst, f4)
        b3, b4 = pair(f3, best[1], t, X, free, limit, it=6)
        dc = dot_cost([b3, b4], t, X, free); ms = misses([b3, b4], dots, view)
        trials.append({"outer_alone_period_d": 1 / f3, "outer_alone_score": c["score"],
                       "partner_period_d": 1 / best[1], "dot_cost": dc, "misses": len(ms),
                       "total": dc + MISS_COST * len(ms), "bodies": [b3, b4], "miss_list": ms})
        print(f"  {1 / f3:8.4f} d (alone {c['score']:6.1f}) + partner {1 / best[1]:8.4f} d: "
              f"dots {dc:6.1f}, misses {len(ms)} -> {dc + MISS_COST * len(ms):6.1f}", file=sys.stderr)
    trials.sort(key=lambda x: x["total"])
    win = trials[0]
    # refine each winner on its own dots with the usual fold (gives the period error)
    b3, b4 = win["bodies"]
    d3 = np.abs(X - P.swing(b3, t)) / P.sig(P.swing(b3, t)); d4 = np.abs(X - P.swing(b4, t)) / P.sig(P.swing(b4, t))
    final = []
    for b, m in ((b3, free & (d3 <= d4) & (d3 < 3)), (b4, free & (d4 < d3) & (d4 < 3))):
        f0 = b["freq"]
        r = scan_periods(t[m], X[m], err=P.sig(X[m]), f_min=f0 - 0.01, f_max=f0 + 0.01, f_step=0.00005)["best"]
        r["n_dots"] = int(m.sum())
        final.append(r)
        print(f"  refined: P = {r['period_d']:.4f} ± {r['period_err_d']:.4f} d, reach {r['reach_rj']:.2f}, "
              f"dots {m.sum()}, red chi2 {r['reduced_chi2']:.2f}", file=sys.stderr)
    out = {"limit_outer_rj": limit, "gap_rj": gap, "max_abs_x_rj": float(np.abs(X[free]).max()),
           "n_free": int(free.sum()), "n_beyond": int(sel.sum()),
           "trials": [{k: v for k, v in tr.items() if k != "bodies"} for tr in trials], "bodies": final}
    (OUT / "inner.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    p = ROOT / "demo" / "step4_data.json"
    data = json.loads(p.read_text()); data["inner"] = out
    p.write_text(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
