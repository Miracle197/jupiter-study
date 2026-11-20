"""Step 4 (redo), part 3: the outermost body's period, by folding.

The photos were taken about once a night, mostly at the same hour, with gaps of
several days, so no body's turning point need ever be photographed. Folding
fixes that: guess a period, put every dot at "how far through one turn" it was
taken, and dots from different turns fill each other's gaps. With the right
period they make one clean back-and-forth swing; with a wrong one, a mess.

Only the outermost body is taken here: the dots farther out than LIMIT (Rj)
from Jupiter. Nothing about the inner bodies is assumed. Evidence used for
every trial period P:
  * dots  -- the swing X = a sin(2 pi t/P) + b cos(2 pi t/P) must pass them;
  * speed -- on nights with several photos (part 2) the measured speed along
             the line must match the swing's slope (this tells "going out"
             from "coming back" at the same X);
  * empty -- a photo that sees that far and has no dot out there says the
             body was NOT beyond LIMIT then ("should be there but isn't").
The score is a chi-square (lower is better). The swing is a plain sine: that
it fits is a result, not an assumption -- the leftover scatter shows it.

Output: output/step4/fold.json; demo/step4_data.json gets "fold".
"""
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "step4"
T_REF = datetime(2023, 12, 3)
LIMIT = 16.0                  # Rj: falls in a gap in |X| (see gap_around); beyond it, only one body
F_MIN, F_MAX, F_STEP = 0.02, 2.0, 0.0002   # cycles per day
EDGE_MARGIN_RJ = 1.0


def _design(t, w):
    return np.c_[np.sin(w * t), np.cos(w * t)]


def fit_one(f, t, X, err, t_empty=None, limit=None, vt=None, v=None, verr=None):
    """Best swing for frequency f (cycles/day) and its score."""
    w = 2 * np.pi * f
    rows, rhs = [_design(t, w) / err[:, None]], [X / err]
    if vt is not None and len(vt):
        rows.append(np.c_[w * np.cos(w * vt), -w * np.sin(w * vt)] / verr[:, None]); rhs.append(v / verr)
    A, y = np.vstack(rows), np.concatenate(rhs)
    extra_A, extra_y = np.zeros((0, 2)), np.zeros(0)
    for _ in range(3):                         # empties that the swing pushes out are pulled back to the limit
        ab = np.linalg.lstsq(np.vstack([A, extra_A]), np.concatenate([y, extra_y]), rcond=None)[0]
        if t_empty is None or not len(t_empty):
            break
        Xe = _design(t_empty, w) @ ab
        bad = np.abs(Xe) > limit
        se = 0.35 + 0.08 * limit
        extra_A = _design(t_empty[bad], w) / se
        extra_y = np.sign(Xe[bad]) * limit / se
    chi_d = np.sum(((_design(t, w) @ ab - X) / err) ** 2)
    chi_v = np.sum(((np.c_[w * np.cos(w * vt), -w * np.sin(w * vt)] @ ab - v) / verr) ** 2) if vt is not None and len(vt) else 0.0
    chi_e = 0.0
    if t_empty is not None and len(t_empty):
        Xe = _design(t_empty, w) @ ab
        chi_e = np.sum((np.clip(np.abs(Xe) - limit, 0, None) / (0.35 + 0.08 * limit)) ** 2)
    a, b = ab
    return {"freq": float(f), "period_d": float(1 / f), "reach_rj": float(math.hypot(a, b)),
            "phase_rad": float(math.atan2(b, a)), "a": float(a), "b": float(b),
            "score": float(chi_d + chi_v + chi_e), "chi_dots": float(chi_d), "chi_speed": float(chi_v), "chi_empty": float(chi_e)}


def scan_periods(t, X, t_empty=None, limit=LIMIT, err=None, vt=None, v=None, verr=None,
                 f_min=F_MIN, f_max=F_MAX, f_step=F_STEP, n_rivals=6):
    t, X = np.asarray(t, float), np.asarray(X, float)
    err = np.full(len(t), 0.5) if err is None else np.asarray(err, float)
    te = None if t_empty is None else np.asarray(t_empty, float)
    kw = dict(t_empty=te, limit=limit, vt=None if vt is None else np.asarray(vt, float),
              v=None if v is None else np.asarray(v, float), verr=None if verr is None else np.asarray(verr, float))
    fs = np.arange(f_min, f_max, f_step)
    S = np.array([fit_one(f, t, X, err, **kw)["score"] for f in fs])
    # local minima, best first, at least 0.01 cycles/day apart
    mins = [i for i in range(1, len(S) - 1) if S[i] <= S[i - 1] and S[i] <= S[i + 1]]
    mins.sort(key=lambda i: S[i])
    picked = []
    for i in mins:
        if all(abs(fs[i] - fs[j]) > 0.01 for j in picked):
            picked.append(i)
        if len(picked) >= n_rivals:
            break
    def refine(f0):
        ff = np.linspace(f0 - f_step, f0 + f_step, 41)
        r = [fit_one(f, t, X, err, **kw) for f in ff]
        return min(r, key=lambda x: x["score"])
    rivals = [refine(fs[i]) for i in picked]
    best = rivals[0]
    # photo error of the period: where the score rises by max(1, reduced chi-square)
    n_obs = len(t) + (0 if kw["vt"] is None else len(kw["vt"]))
    red = max(best["score"] / max(n_obs - 3, 1), 1.0)
    ff = np.linspace(best["freq"] - 0.004, best["freq"] + 0.004, 801)
    sc = np.array([fit_one(f, t, X, err, **kw)["score"] for f in ff])
    ok = ff[sc <= best["score"] + red]
    best["period_err_d"] = float((1 / ok.min() - 1 / ok.max()) / 2) if len(ok) > 1 else float("nan")
    best["reduced_chi2"] = float(best["score"] / max(n_obs - 3, 1))
    return {"best": best, "rivals": rivals, "curve": {"freq": fs.tolist(), "score": S.tolist()}}


# ---------- real data ----------
def _view():
    """How far along the line each photo sees, both ways (Rj, step 1 scale)."""
    orient = {r["photo"]: r for r in csv.DictReader(open(ROOT / "output/step2/orientation.csv"))}
    scale = {r["photo"]: r for r in csv.DictReader(open(ROOT / "output/step1/scale.csv"))}
    det = json.load(open(ROOT / "output/step1/detections.json"))
    out = {}
    for s, o in orient.items():
        j = det[s]["jupiter"]; rj = float(scale[s]["rj_px"]); th = math.radians(float(o["final_plusX_deg"]))
        lim = []
        for sg in (-1, 1):
            dx, dy = sg * math.cos(th), -sg * math.sin(th)
            L = [((n if d > 0 else 0) - p) / d for d, p, n in ((dx, j["x"], det[s]["w"]), (dy, j["y"], det[s]["h"])) if abs(d) > 1e-9]
            lim.append(sg * (min(L) / rj - EDGE_MARGIN_RJ))
        out[s] = (lim, (datetime.fromisoformat(o["local_time"]) - T_REF).total_seconds() / 86400)
    return out


def gap_around(limit=LIMIT):
    """The nearest dot distances |X| below and above the limit: the empty stretch the limit sits in."""
    ax = [abs(float(r["X_rj"])) for r in csv.DictReader(open(ROOT / "output/step2/positions.csv"))
          if r["strong"] == "True" and r["in_band"] == "True"]
    return [round(max(a for a in ax if a <= limit), 2), round(min(a for a in ax if a > limit), 2)]


def load(limit=LIMIT):
    view = _view()
    outer, has_outer = [], {"-": set(), "+": set()}
    for r in csv.DictReader(open(ROOT / "output/step2/positions.csv")):
        if r["strong"] != "True" or r["in_band"] != "True":
            continue
        X = float(r["X_rj"])
        if abs(X) > limit:
            t = view[r["photo"]][1]
            outer.append({"photo": r["photo"], "t": t, "X": X, "err": 0.35 + 0.08 * abs(X)})
            has_outer["+" if X > 0 else "-"].add(r["photo"])
    empty = []
    for s, (lim, t) in view.items():
        # an empty photo counts only if it sees beyond the limit on BOTH sides and has nothing out there
        if lim[0] < -(limit + 2) and lim[1] > limit + 2 and s not in has_outer["+"] | has_outer["-"]:
            empty.append({"photo": s, "t": t})
    speeds = []
    tr = json.load(open(OUT / "tracks.json"))
    for n, night in tr.items():
        t0 = (datetime.fromisoformat(night["start"]) - T_REF).total_seconds() / 86400
        for k in night["tracks"]:
            P = k["points"]
            if k["speed_rj_per_h"] is None or len(P) < 3:
                continue
            xm = float(np.mean([p["X"] for p in P]))
            if abs(xm) > limit:
                tm = t0 + float(np.mean([p["t_h"] for p in P])) / 24
                speeds.append({"night": n, "t": tm, "X": xm, "v": 24 * k["speed_rj_per_h"], "err": 24 * k["speed_err"]})
    return outer, empty, speeds


def main():
    outer, empty, speeds = load()
    t = np.array([d["t"] for d in outer]); X = np.array([d["X"] for d in outer]); e = np.array([d["err"] for d in outer])
    te = np.array([d["t"] for d in empty])
    vt = np.array([s["t"] for s in speeds]); v = np.array([s["v"] for s in speeds]); ve = np.array([s["err"] for s in speeds])
    res = scan_periods(t, X, t_empty=te, limit=LIMIT, err=e, vt=vt, v=v, verr=ve)
    # the same without the speeds and without the empty photos, to show what each piece of evidence adds
    no_empty = scan_periods(t, X, err=e, vt=vt, v=v, verr=ve)["best"]
    b = res["best"]
    print(f"outer dots {len(t)}, empty photos {len(te)}, night speeds {len(vt)}", file=sys.stderr)
    print(f"best P = {b['period_d']:.3f} ± {b['period_err_d']:.3f} d, reach {b['reach_rj']:.2f} Rj, "
          f"score {b['score']:.1f} (dots {b['chi_dots']:.1f}, speed {b['chi_speed']:.1f}, empty {b['chi_empty']:.1f}), red chi2 {b['reduced_chi2']:.2f}",
          file=sys.stderr)
    for r in res["rivals"][1:]:
        print(f"   rival P = {r['period_d']:.3f} d  score {r['score']:.1f} (empty {r['chi_empty']:.1f})", file=sys.stderr)
    print(f"without the empty photos: P = {no_empty['period_d']:.3f} d, score {no_empty['score']:.1f}", file=sys.stderr)
    out = {"limit_rj": LIMIT, "gap_rj": gap_around(), "dots": outer, "empty": empty, "speeds": speeds, "best": b,
           "rivals": res["rivals"], "without_empty": no_empty,
           "curve": {"period_d": [1 / f for f in res["curve"]["freq"][::5]], "score": res["curve"]["score"][::5]}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fold.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    p = ROOT / "demo" / "step4_data.json"
    data = json.loads(p.read_text()); data["fold"] = out
    p.write_text(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
