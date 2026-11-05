"""Galileo mode: find the moons and their periods WITHOUT any moon ephemeris.

The question: if you were the first person to see these dots (Galileo, January
1610), not knowing they are moons of Jupiter, how would you locate them and
work out their periods? This script only uses what such an observer has:

  - the photos (data/detections.json: Jupiter's position and size, bright dots)
  - the time of each photo (data/photos.csv)
  - standard version only: which side of each photo is east. Galileo marked
    east/west on every sketch; our photographer did not record it, so this one
    bit per photo is borrowed from data/photo_fits.json. The challenge version
    works it out from the data instead.

Steps
  1. Dots that belong to Jupiter lie on one line through it: keep the dots on
     the best line through Jupiter (no ephemeris involved).
  2. Ruler = Jupiter's disk radius (Galileo measured in Jupiter diameters).
  3. Distances pile up at each body's greatest elongation: peaks of the |X|
     distribution give the number of bodies and their orbit sizes.
  4. Peel from the outside in: only the outermost body reaches beyond the third
     peak, so fit it first, remove its dots, go one ring inward. Inner bodies
     are required to be faster than outer ones (as Galileo saw).
  5. Iterate: give every dot to the nearest model, refit. Once-a-night sampling
     makes P and its "one cycle per day" alias look alike; the nights with
     many photos decide between them.
  6. Kepler's third law from the result.
Only at the very end, grade() reads the ephemeris-based identification
(data/positions.csv) to score the blind result.

Output: data/galileo.json
"""
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from astropy.time import Time
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parent.parent
RJ_KM = 71492.0
G = 6.67430e-11
CAP = 4.0           # residual cap (Rj^2): one junk dot cannot dominate a fit
F_MAX = 2.0         # fastest motion searched: 2 cycles per day
NAMES = ["I", "II", "III", "IV"]   # Galileo numbered the moons from the inside out
RNG = np.random.default_rng(1610)


# ---------- 1. dots on a line through Jupiter ----------
def blind_dots():
    det = json.load(open(ROOT / "data" / "detections.json"))
    times = {}
    for r in csv.DictReader(open(ROOT / "data" / "photos.csv")):
        utc = datetime.strptime(r["local_time"], "%Y-%m-%d %H:%M") + timedelta(hours=8)  # PST
        times[Path(r["file"]).stem] = Time(utc, scale="utc").jd
    jd0 = min(times.values())
    photos, prev_u = [], {}
    for stem in sorted(det, key=lambda s: times[s]):
        d = det[stem]
        j = d["jupiter"]
        jr = j["r"]
        jd = times[stem]
        night = int(np.floor(jd - 8 / 24))  # local noon to noon
        C = np.array([[c["x"] - j["x"], -(c["y"] - j["y"])] for c in d["candidates"]]).reshape(-1, 2) / jr
        w = np.sqrt([c["snr"] for c in d["candidates"]])
        r = np.hypot(C[:, 0], C[:, 1]) if len(C) else np.array([])
        best = None
        for th in np.radians(np.arange(0, 180, 0.5)):
            u = np.array([np.cos(th), np.sin(th)])
            perp = np.abs(C @ np.array([-u[1], u[0]])) if len(C) else np.array([])
            inl = (r < 30) & (perp < 0.35 + 0.03 * r)
            sc = float((w * inl).sum())
            if best is None or sc > best[0]:
                best = (sc, u, inl)
        _, u, inl = best
        # the phone turns slowly during a night: keep the axis direction continuous
        if night in prev_u and u @ prev_u[night] < 0:
            u = -u
        prev_u[night] = u
        idx = np.where(inl)[0]
        idx = idx[np.argsort(-w[idx])][:5]
        dots = []
        for i in idx:
            c = d["candidates"][i]
            dots.append({"X": float(C[i] @ u), "Y": float(C[i] @ np.array([-u[1], u[0]])),
                         "snr": c["snr"], "px": c["x"], "py": c["y"]})
        photos.append({"id": stem, "jd": jd, "t": jd - jd0, "night": night, "jr": jr,
                       "axis_deg": float(np.degrees(np.arctan2(u[1], u[0]))), "u": u, "dots": dots})
    return photos, jd0


def east_signs(photos):
    """Standard version: +1 when the photo's axis already points east (borrowed bit)."""
    fits = json.load(open(ROOT / "data" / "photo_fits.json"))
    out = []
    for p in photos:
        th = np.radians(fits[p["id"]]["theta_deg"])
        out.append(1 if p["u"] @ np.array([np.cos(th), np.sin(th)]) >= 0 else -1)
    return np.array(out)


# ---------- 2-3. evidence and orbit sizes ----------
def evidence(photos, A):
    counts = [len(p["dots"]) for p in photos]
    perp_deg = [np.degrees(np.arctan2(abs(d["Y"]), abs(d["X"]))) for p in photos for d in p["dots"] if abs(d["X"]) > 3]
    grid = np.linspace(0, 28, 561)
    bw = 0.55
    kde = np.exp(-0.5 * ((grid[:, None] - A[None, :]) / bw) ** 2).sum(1) / (len(A) * bw * np.sqrt(2 * np.pi))
    kde[grid < 1.5] = 0
    pk, prop = find_peaks(kde, prominence=0.002)
    top = sorted(pk[np.argsort(-prop["prominences"])][:4])
    peaks = grid[top]
    thresholds = [float(np.sqrt(peaks[i] * peaks[i + 1])) for i in range(len(peaks) - 1)]
    hist, edges = np.histogram(A, bins=np.arange(0, 28.5, 1.0))
    det = json.load(open(ROOT / "data" / "detections.json"))
    return {"n_candidates": sum(len(d["candidates"]) for d in det.values()), "n_on_line": int(len(A)),
            "dots_per_photo": np.bincount(counts, minlength=6).tolist(), "max_dots": int(max(counts)),
            "line_scatter_deg_median": float(np.median(perp_deg)), "max_distance": float(A.max()),
            "hist": {"edges": edges.tolist(), "counts": hist.tolist()},
            "kde": {"x": grid[::2].round(3).tolist(), "y": kde[::2].round(5).tolist()},
            "peaks": peaks.round(2).tolist(), "thresholds": [round(x, 2) for x in thresholds]}


# ---------- 4-5. sine fits ----------
def scan(t, x, freqs, w=None, amp=None, trim=2):
    """Vectorised robust sine fit at many frequencies: least squares, then
    `trim` refits without the points that miss by more than sqrt(CAP).
    Returns score, sin and cos coefficients per frequency."""
    if w is None:
        w = np.ones_like(x)
    ph = 2 * np.pi * freqs[:, None] * t[None, :]
    S, C = np.sin(ph), np.cos(ph)
    W = np.broadcast_to(w, S.shape)
    for it in range(trim + 1):
        ss, sc, cc = (S * S * W).sum(1), (S * C * W).sum(1), (C * C * W).sum(1)
        xs, xc = (S * x * W).sum(1), (C * x * W).sum(1)
        det = ss * cc - sc ** 2 + 1e-9
        a_s, a_c = (xs * cc - xc * sc) / det, (xc * ss - xs * sc) / det
        res = x[None, :] - a_s[:, None] * S - a_c[:, None] * C
        if it < trim:
            W = w[None, :] * (res ** 2 < CAP)
    score = (np.minimum(res ** 2, CAP) * w).sum(1)
    if amp is not None:
        a = np.hypot(a_s, a_c)
        score = np.where((a >= amp[0]) & (a <= amp[1]), score, np.inf)
    return score, a_s, a_c


class Model:
    def __init__(self, f, a_s, a_c):
        self.f, self.a_s, self.a_c = float(f), float(a_s), float(a_c)

    def __call__(self, t):
        ph = 2 * np.pi * self.f * t
        return self.a_s * np.sin(ph) + self.a_c * np.cos(ph)

    @property
    def amp(self):
        return float(np.hypot(self.a_s, self.a_c))


def best_fit(t, x, f_lo, f_hi, span, w=None, amp=None):
    if len(t) < 3 or f_lo >= f_hi - 1 / (12 * span):
        return None
    freqs = np.arange(f_lo, f_hi, 1 / (12 * span))
    score, a_s, a_c = scan(t, x, freqs, w, amp)
    k = int(np.argmin(score))
    if not np.isfinite(score[k]):
        return None
    fine = np.linspace(freqs[k] - 1 / (12 * span), freqs[k] + 1 / (12 * span), 61)
    s2, b_s, b_c = scan(t, x, fine, w, amp)
    k2 = int(np.argmin(s2))
    return Model(fine[k2], b_s[k2], b_c[k2])


def objective(t, X, models):
    if not models:
        return float(len(X) * CAP)
    r2 = np.min([(X - m(t)) ** 2 for m in models], axis=0)
    return float(np.minimum(r2, CAP).sum())


def _local_minima(score, n):
    idx = [i for i in range(1, len(score) - 1) if score[i] <= score[i - 1] and score[i] <= score[i + 1] and np.isfinite(score[i])]
    return sorted(idx, key=lambda i: score[i])[:n]


def solve(t, X, dense, peaks, span, sweeps=4):
    # lower edge of each ring's distance band (between neighbouring peaks), used to seed it
    lower = [0.0] + [float(np.sqrt(peaks[i] * peaks[i + 1])) for i in range(len(peaks) - 1)]
    """Find one sine per ring. Ring k's amplitude is tied to its |X| peak (its
    greatest elongation, read off the data). Candidate periods for a ring come
    from its periodogram plus the daily alias family of the current choice;
    each ring in turn keeps the candidate that best explains ALL dots (dots on
    nights with many photos count 3x, because they show the motion within a
    night and so separate a period from its aliases)."""
    A = np.abs(X)
    w = np.where(dense, 3.0, 1.0)
    n = len(peaks)
    amp = [(0.75 * pk, 1.35 * pk) for pk in peaks]
    freqs = np.arange(1 / 40, F_MAX + 0.6, 1 / (12 * span))
    models = [None] * n

    def wobj(ms):
        ms = [m for m in ms if m is not None]
        if not ms:
            return float((CAP * w).sum())
        r2 = np.min([(X - m(t)) ** 2 for m in ms], axis=0)
        return float((np.minimum(r2, CAP) * w).sum())

    def avail_for(k):
        others = [m for i, m in enumerate(models) if i != k and m is not None]
        ok = A <= 1.4 * peaks[k]
        if others:
            r = np.min([np.abs(X - m(t)) for m in others], axis=0)
            ok &= r > 1.0 + 0.05 * A
        return ok

    for sweep in range(sweeps + 1):
        changed = False
        for k in range(n - 1, -1, -1):          # outermost ring first
            sel = avail_for(k)
            if sweep == 0:   # seed: only this ring can reach beyond the band below it
                sel &= A > lower[k]
            if sel.sum() < 4:
                continue
            score, _, _ = scan(t[sel], X[sel], freqs, w[sel], amp[k])
            cand = {round(float(freqs[i]), 6) for i in _local_minima(score, 6)}
            if models[k] is not None:
                f = models[k].f
                cand |= {round(x, 6) for x in (f, f - 1, f + 1, 1 - f, 2 - f, f - 2) if 1 / 45 < x < F_MAX + 0.6}
            best = (wobj(models), models[k])
            for f0 in sorted(cand):
                mm = best_fit(t[sel], X[sel], max(1 / 45, f0 * 0.97), f0 * 1.03 + 1 / (6 * span), span, w=w[sel], amp=amp[k])
                if mm is None:
                    continue
                trial = models[:k] + [mm] + models[k + 1:]
                o = wobj(trial)
                if o < best[0] - 1e-9:
                    best = (o, mm)
            if best[1] is not models[k]:
                changed = True
                models[k] = best[1]
        if sweep > 0 and not changed:
            break
    if any(m is None for m in models):
        return models, np.full(len(X), -1), np.inf
    r = np.array([np.abs(X - m(t)) for m in models])
    lab = np.argmin(r, axis=0)
    lab = np.where(r[lab, np.arange(len(X))] < 1.0 + 0.05 * A, lab, -1)
    return models, lab, objective(t, X, models)


def night_signs_from(models, t, Xraw, night):
    signs = {}
    for n in np.unique(night):
        sel = night == n
        sc = {s: objective(t[sel], s * Xraw[sel], models) for s in (1, -1)}
        signs[int(n)] = 1 if sc[1] <= sc[-1] else -1
    return signs


def challenge(t, Xraw, night, dense, peaks, thresholds, span):
    """East/west unknown: one +-1 per night, searched together with the orbits."""
    nights = np.unique(night)
    A = np.abs(Xraw)

    def run(signs):
        for _ in range(10):
            X = Xraw * np.array([signs[int(n)] for n in night])
            models, lab, obj = solve(t, X, dense, peaks, span)
            if not np.isfinite(obj):
                return np.inf, signs, models, lab
            new = night_signs_from(models, t, Xraw, night)
            if new == signs:
                break
            signs = new
        X = Xraw * np.array([signs[int(n)] for n in night])
        models, lab, obj = solve(t, X, dense, peaks, span)
        return obj, signs, models, lab

    starts = []
    # start 1: the outermost body seen sign-free, |X| = a |sin(2 pi (t - t0) / P)|
    far = A > thresholds[-1]
    best = None
    for P in 1 / np.linspace(1 / 40, 1 / 3, 800):
        t0 = np.linspace(0, P, 72, endpoint=False)
        s = np.abs(np.sin(2 * np.pi * (t[far][None, :] - t0[:, None]) / P))
        a = (s * A[far]).sum(1) / (s * s).sum(1)
        res = np.minimum((A[far][None, :] - a[:, None] * s) ** 2, CAP).sum(1)
        k = int(np.argmin(res))
        if best is None or res[k] < best[0]:
            best = (res[k], P, t0[k], a[k])
    _, P, t0, a = best
    outer = Model(1 / P, a * np.cos(-2 * np.pi * t0 / P), a * np.sin(-2 * np.pi * t0 / P))
    starts.append(night_signs_from([outer], t, Xraw, night))
    for _ in range(24):
        starts.append({int(n): int(RNG.choice([1, -1])) for n in nights})
    results = [run(s) for s in starts]
    results.sort(key=lambda r: r[0])
    best_obj = results[0][0]
    same = sum(1 for r in results if np.isfinite(r[0]) and r[0] <= best_obj * 1.001)
    return results[0], {"outer_sign_free_P": float(P), "restarts": len(starts),
                        "restarts_reaching_best": int(same), "objective_best": best_obj}


# ---------- 6. Kepler ----------
def kepler(models):
    P = np.array([1 / m.f for m in models])
    a = np.array([m.amp for m in models])
    slope = float(np.polyfit(np.log(P), np.log(a), 1)[0])
    k = a ** 3 / P ** 2
    mass = np.median(4 * np.pi ** 2 * (a * RJ_KM * 1e3) ** 3 / (G * (P * 86400) ** 2))
    return {"slope": slope, "a3_over_P2": k.round(2).tolist(), "a3_over_P2_spread": float(k.std() / k.mean()),
            "mass_kg_no_glare_correction": float(mass)}


def periodograms(t, X, lab, models, span):
    out = []
    freqs = np.arange(1 / 40, F_MAX + 0.6, 1 / (8 * span))
    for k, m in enumerate(models):
        sel = lab == k
        score, _, _ = scan(t[sel], X[sel], freqs)
        score = score / score.max()
        al = sorted({round(x, 5) for x in (m.f - 1, m.f + 1, 1 - m.f, 2 - m.f) if 1 / 40 < x < F_MAX + 0.6 and abs(x - m.f) > 1e-3})
        out.append({"f": freqs.round(5).tolist(), "score": score.round(4).tolist(), "f_best": m.f, "aliases": al})
    return out


# ---------- 7. grading (the only place the ephemeris-based answer is used) ----------
TRUE = {"Io": (1.769138, 5.905), "Europa": (3.551181, 9.397), "Ganymede": (7.154553, 14.99), "Callisto": (16.689018, 26.37)}
TRUE_ORDER = ["Io", "Europa", "Ganymede", "Callisto"]


def grade(photos, labels):
    truth = {}
    for r in csv.DictReader(open(ROOT / "data" / "positions.csv")):
        truth.setdefault(r["photo"], []).append((float(r["px"]), float(r["py"]), r["moon"]))
    stats = {"correct": 0, "wrong_moon": 0, "junk_kept": 0, "junk_rejected": 0, "moon_rejected": 0}
    tlabels = []
    i = 0
    for p in photos:
        for d in p["dots"]:
            tm = next((m for x, y, m in truth.get(p["id"], []) if np.hypot(x - d["px"], y - d["py"]) < 3), None)
            tlabels.append(tm)
            lab = labels[i]
            i += 1
            if lab >= 0 and tm:
                stats["correct" if TRUE_ORDER[lab] == tm else "wrong_moon"] += 1
            elif lab >= 0:
                stats["junk_kept"] += 1
            elif tm:
                stats["moon_rejected"] += 1
            else:
                stats["junk_rejected"] += 1
    n_true = sum(1 for x in tlabels if x)
    stats["true_moon_dots_after_line_filter"] = n_true
    stats["true_moon_dots_total"] = sum(len(v) for v in truth.values())
    return stats, tlabels


def summarise(models, lab, photos, t, X, span, signs_photo):
    st, tl = grade(photos, lab)
    moons = []
    for k, m in enumerate(models):
        name = TRUE_ORDER[k]
        moons.append({"ring": NAMES[k], "P": 1 / m.f, "a": m.amp, "f": m.f, "a_s": m.a_s, "a_c": m.a_c,
                      "n": int((lab == k).sum()), "true_name": name, "true_P": TRUE[name][0],
                      "P_err_pct": (1 / m.f - TRUE[name][0]) / TRUE[name][0] * 100})
    return {"moons": moons, "labels": lab.tolist(), "signs": [int(s) for s in signs_photo],
            "grade": st, "kepler": kepler(models), "periodograms": periodograms(t, X, lab, models, span)}, tl


def main():
    photos, jd0 = blind_dots()
    t = np.array([p["t"] for p in photos for _ in p["dots"]])
    Xraw = np.array([d["X"] for p in photos for d in p["dots"]])
    night = np.array([p["night"] for p in photos for _ in p["dots"]])
    per_night = {n: sum(1 for p in photos if p["night"] == n) for n in set(night.tolist())}
    dense = np.array([per_night[n] >= 4 for n in night])
    span = float(t.max() - t.min())
    A = np.abs(Xraw)
    ev = evidence(photos, A)
    th = ev["thresholds"]
    print(f"blind dots: {len(Xraw)} in {len(photos)} photos; |X| peaks {ev['peaks']} -> thresholds {th}")

    # standard version: east known for each photo
    s_photo = east_signs(photos)
    s_dot = np.array([s for p, s in zip(photos, s_photo) for _ in p["dots"]])
    Xs = Xraw * s_dot
    m_std, lab_std, obj_std = solve(t, Xs, dense, ev["peaks"], span)
    std, tl = summarise(m_std, lab_std, photos, t, Xs, span, s_photo)

    # challenge version: east unknown
    (obj_c, signs_c, m_ch, lab_ch), info = challenge(t, Xraw, night, dense, ev["peaks"], th, span)
    s_photo_c = np.array([signs_c[p["night"]] for p in photos])
    Xc = Xraw * np.array([signs_c[int(n)] for n in night])
    ch, _ = summarise(m_ch, lab_ch, photos, t, Xc, span, s_photo_c)
    agree = float(np.mean(s_photo_c == s_photo))
    ch["sign_agreement"] = max(agree, 1 - agree)   # overall mirror cannot be known
    ch["mirrored_overall"] = bool(agree < 0.5)
    ch["search"] = info
    std["objective"], ch["objective"] = obj_std, obj_c

    out = {"jd0": jd0, "span_days": span, "evidence": ev,
           "photos": [{"id": p["id"], "t": round(p["t"], 5), "night": p["night"], "axis_deg": round(p["axis_deg"], 2),
                       "dots": [{"X": round(d["X"], 3), "Y": round(d["Y"], 3)} for d in p["dots"]]} for p in photos],
           "truth_labels": tl, "standard": std, "challenge": ch,
           "true": {k: {"P": v[0], "a_true_rj": v[1]} for k, v in TRUE.items()}}
    json.dump(out, open(ROOT / "data" / "galileo.json", "w"), indent=1)

    for name, res in (("standard (east known)", std), ("challenge (east unknown)", ch)):
        print(f"\n{name}:")
        for m in res["moons"]:
            print(f"  {m['ring']:>3}  P={m['P']:7.3f} d  a={m['a']:5.2f}  n={m['n']:3d}   -> {m['true_name']:8s} true {m['true_P']:.3f}  ({m['P_err_pct']:+.2f}%)")
        g = res["grade"]
        print(f"  dots: correct {g['correct']}, wrong moon {g['wrong_moon']}, junk kept {g['junk_kept']}, "
              f"junk rejected {g['junk_rejected']}, moon dots rejected {g['moon_rejected']}")
        print(f"  Kepler slope {res['kepler']['slope']:.3f}  a^3/P^2 spread {res['kepler']['a3_over_P2_spread']:.1%}")
    print(f"\nchallenge: night-sign agreement {ch['sign_agreement']:.0%}, search {info}")


if __name__ == "__main__":
    main()
