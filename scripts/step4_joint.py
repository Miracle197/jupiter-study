"""Step 4 (redo), part 5: all bodies together, the checks, and what follows.

Starts from the four swings found one by one (parts 3, 4, 4b) and:
  1. hands every dot to the nearest swing (two bodies may share one dot when
     both are predicted on it -- their images merge), refits each swing on its
     own dots, repeats until nothing changes;
  2. errors: fit error scaled by the actual scatter, and a bootstrap over
     nights (whole nights are resampled, since photos of one night share a
     scale and an orientation);
  3. the "one turn more per day" trap: each body's dots are refitted at the
     rival frequencies f +- 1, f +- 2 cycles/day and the scores compared,
     with and without the nights that have several photos;
  4. the drift across the line, Y = B cos(phase) + C: a circle seen almost
     edge-on makes the dot sit on one side going out and the other coming
     back (B != 0); a straight back-and-forth gives B = 0;
  5. what the four have in common: period ratios, and P against reach
     (Kepler's third law says P^2 / a^3 is the same for all).

Output: output/step4/joint.json; demo/step4_data.json gets "joint".
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import step4_peel as P  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "step4"
RNG = np.random.default_rng(1610)
NAMES = ["I", "II", "III", "IV"]   # numbered from Jupiter outward, as Galileo did
SHARE = 0.8                        # Rj: predicted this close, two bodies share one dot


def swing(f, a, b, t):
    w = 2 * np.pi * f
    return a * np.sin(w * t) + b * np.cos(w * t)


def assign(B, t, X):
    """dot -> list of body indices (empty = no body within 3 sigma)."""
    pr = np.array([swing(*b, t) for b in B]).T          # (n, k)
    d = np.abs(X[:, None] - pr) / P.sig(pr)
    out = []
    for i in range(len(X)):
        k = int(np.argmin(d[i]))
        if d[i, k] > 3:
            out.append([]); continue
        ks = [k] + [j for j in range(len(B)) if j != k and d[i, j] < 2 and abs(pr[i, j] - pr[i, k]) < SHARE]
        out.append(sorted(ks))
    return out


def fit_body(f0, t, X, scan=0.002, n=401):
    """Best (f, a, b) near f0 by linear least squares on a fine frequency grid, plus errors."""
    s = P.sig(X)
    best = None
    for f in np.linspace(f0 - scan, f0 + scan, n):
        w = 2 * np.pi * f
        A = np.c_[np.sin(w * t), np.cos(w * t)] / s[:, None]
        ab, *_ = np.linalg.lstsq(A, X / s, rcond=None)
        chi = float(np.sum((A @ ab - X / s) ** 2))
        if best is None or chi < best[0]:
            best = (chi, f, ab)
    chi, f, (a, b) = best
    # local curvature in f for the period's fit error, scaled by the reduced chi-square
    red = max(chi / max(len(X) - 3, 1), 1.0)
    h = 1e-5
    def c(ff):
        w = 2 * np.pi * ff; A = np.c_[np.sin(w * t), np.cos(w * t)] / s[:, None]
        ab, *_ = np.linalg.lstsq(A, X / s, rcond=None); return float(np.sum((A @ ab - X / s) ** 2))
    curv = (c(f + h) - 2 * chi + c(f - h)) / h ** 2
    sf = np.sqrt(2 * red / curv) if curv > 0 else np.nan
    return {"f": float(f), "a": float(a), "b": float(b), "chi2": chi, "red_chi2": chi / max(len(X) - 3, 1),
            "f_err": float(sf)}


def joint(B0, t, X, it=8):
    B = [tuple(b) for b in B0]
    for _ in range(it):
        asg = assign(B, t, X)
        new = []
        for k, b in enumerate(B):
            m = np.array([k in ks for ks in asg])
            r = fit_body(b[0], t[m], X[m], scan=0.001, n=201)
            new.append((r["f"], r["a"], r["b"]))
        if all(abs(n[0] - o[0]) < 1e-7 for n, o in zip(new, B)):
            B = new; break
        B = new
    return B, assign(B, t, X)


def rival_scores(f0, t, X):
    out = []
    for df in (0, -2, -1, 1, 2):
        f = abs(f0 + df)            # a negative frequency is the same swing turning the other way
        if f <= 0.01:
            continue
        r = fit_body(f, t, X, scan=0.003, n=301)
        out.append({"shift_per_day": df, "period_d": 1 / r["f"], "chi2": r["chi2"], "reach_rj": float(np.hypot(r["a"], r["b"]))})
    return out


def tilt(fb, t, Y):
    f, a, b = fb
    ph = 2 * np.pi * f * t + np.arctan2(b, a)            # X = R sin(ph)
    M = np.c_[np.cos(ph), np.ones_like(ph)]
    c, *_ = np.linalg.lstsq(M, Y, rcond=None)
    res = Y - M @ c
    cov = np.linalg.inv(M.T @ M) * np.sum(res ** 2) / max(len(Y) - 2, 1)
    return {"B_rj": float(c[0]), "B_err_rj": float(np.sqrt(cov[0, 0])), "C_rj": float(c[1]), "n": int(len(Y))}


def main():
    dots, tracks, view = P.load()
    t = np.array([d["t"] for d in dots]); X = np.array([d["X"] for d in dots]); Y = np.array([d["Y"] for d in dots])
    nights = np.array([d["photo"][:10] for d in dots])
    pe = json.load(open(OUT / "peel.json"))["bodies"]; inn = json.load(open(OUT / "inner.json"))["bodies"]
    B0 = sorted([(b["freq"], b["a"], b["b"]) for b in pe + inn], key=lambda b: -b[0])   # fastest = innermost first
    B, asg = joint(B0, t, X)
    resid = []
    bodies = []
    for k, fb in enumerate(B):
        m = np.array([k in ks for ks in asg])
        r = fit_body(fb[0], t[m], X[m], scan=0.0005, n=201)
        resid += list(X[m] - swing(r["f"], r["a"], r["b"], t[m]))
        # bootstrap over nights
        un = np.unique(nights[m]); Ps = []
        for _ in range(200):
            pick = RNG.choice(un, len(un))
            idx = np.concatenate([np.where(m & (nights == n))[0] for n in pick])
            rb = fit_body(r["f"], t[idx], X[idx], scan=0.0006, n=61)
            Ps.append(1 / rb["f"])
        P_err_fit = r["f_err"] / r["f"] ** 2
        P_err_boot = float(np.std(Ps))
        multi = np.array([np.sum(nights == n) >= 3 * 1 for n in nights]) & m
        busy = {n for n in np.unique(nights) if len({d["photo"] for d, nn in zip(dots, nights) if nn == n}) >= 3}
        single = m & ~np.isin(nights, list(busy))
        bodies.append({
            "name": NAMES[k], "period_d": 1 / r["f"], "period_err_d": max(P_err_fit, P_err_boot),
            "period_err_fit_d": P_err_fit, "period_err_boot_d": P_err_boot,
            "reach_rj": float(np.hypot(r["a"], r["b"])), "freq": r["f"], "a": r["a"], "b": r["b"],
            "dots": int(m.sum()), "red_chi2": r["red_chi2"],
            "rivals_all": rival_scores(r["f"], t[m], X[m]),
            "rivals_without_busy_nights": rival_scores(r["f"], t[single], X[single]) if single.sum() > 6 else None,
            "tilt": tilt((r["f"], r["a"], r["b"]), t[m & np.array([len(ks) == 1 for ks in asg])],
                         Y[m & np.array([len(ks) == 1 for ks in asg])]),
        })
    # reach error from the bootstrap is dominated by the per-photo scale (~6%); keep it simple
    for b in bodies:
        b["reach_err_rj"] = 0.06 * b["reach_rj"] / np.sqrt(max(b["dots"] / 4, 1))
    Pd = np.array([b["period_d"] for b in bodies]); a = np.array([b["reach_rj"] for b in bodies])
    ae = np.array([b["reach_err_rj"] for b in bodies])
    k, c = np.polyfit(np.log(a), np.log(Pd), 1, w=a / ae)
    # error of the slope by resampling the reaches within their errors
    ks = [np.polyfit(np.log(a + RNG.normal(0, ae)), np.log(Pd), 1)[0] for _ in range(2000)]
    kepler = {"slope": float(k), "slope_err": float(np.std(ks)),
              "P2_over_a3": (Pd ** 2 / a ** 3).tolist(),
              "P2_over_a3_err": (Pd ** 2 / a ** 3 * 3 * ae / a).tolist()}
    ratios = {"P2/P1": Pd[1] / Pd[0], "P3/P2": Pd[2] / Pd[1], "P4/P3": Pd[3] / Pd[2],
              "laplace_1/P1-3/P2+2/P3": 1 / Pd[0] - 3 / Pd[1] + 2 / Pd[2],
              "laplace_err": float(np.sqrt((bodies[0]["period_err_d"] / Pd[0] ** 2) ** 2 + (3 * bodies[1]["period_err_d"] / Pd[1] ** 2) ** 2
                                           + (2 * bodies[2]["period_err_d"] / Pd[2] ** 2) ** 2))}
    n_shared = sum(1 for ks in asg if len(ks) > 1); n_none = sum(1 for ks in asg if not ks)
    summary = {"n_dots": len(dots), "assigned": len(dots) - n_none, "shared": n_shared, "none": n_none,
               "resid_rms_rj": float(np.sqrt(np.mean(np.square(resid)))),
               "resid_robust_rj": float(1.4826 * np.median(np.abs(resid)))}
    for b in bodies:
        r0 = b["rivals_all"][0]["chi2"]
        riv = min(b["rivals_all"][1:], key=lambda x: x["chi2"])
        print(f"{b['name']:>3}: P = {b['period_d']:.4f} ± {b['period_err_d']:.4f} d (fit {b['period_err_fit_d']:.4f}, boot {b['period_err_boot_d']:.4f}), "
              f"reach {b['reach_rj']:.2f} ± {b['reach_err_rj']:.2f} Rj, dots {b['dots']}, red chi2 {b['red_chi2']:.2f}; "
              f"best rival {riv['period_d']:.3f} d chi2 {riv['chi2']:.0f} vs {r0:.0f}; tilt B {b['tilt']['B_rj']:+.2f} ± {b['tilt']['B_err_rj']:.2f}",
              file=sys.stderr)
    print("summary", summary, file=sys.stderr)
    print("kepler", {k_: (np.round(v, 4).tolist() if isinstance(v, list) else round(v, 4)) for k_, v in kepler.items()}, file=sys.stderr)
    print("ratios", {k_: round(v, 5) for k_, v in ratios.items()}, file=sys.stderr)
    out = {"bodies": bodies, "assign": asg, "summary": summary, "kepler": kepler, "ratios": ratios,
           "dots": [{"t": float(tt), "X": float(xx), "Y": float(yy)} for tt, xx, yy in zip(t, X, Y)]}
    (OUT / "joint.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    p = ROOT / "demo" / "step4_data.json"
    data = json.loads(p.read_text()); data["joint"] = out
    p.write_text(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
