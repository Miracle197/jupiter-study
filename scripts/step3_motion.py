"""Step 3: which dots are the same body, how they move, and how long they take.

Input: step 2 positions. Every bright dot in the band has X (along the line,
Jupiter radii, +X the same end of the sky in every photo) and a time.

1. How many bodies: something swinging back and forth spends most of its time
   near its farthest point, so distances |X| pile up there. Each pile-up is
   one body, and where it sits is how far that body gets.
2. Peel from the outside in. Only the outermost body reaches beyond the next
   pile-up, so look for it first. Try every period (0.5 to 50 days), start
   and reach; score each guess photo by photo: +1 if a dot sits where the
   guess puts the body, -1 if the guess puts it in plain view (inside the
   photo, outside Jupiter's glare) and nothing is there. "Should be there but
   isn't" is evidence too. Take the best, hand it its dots, go one body in.
   Stop when the best score is no longer clearly above what a period picked
   at random reaches (99th percentile of all periods tried, plus 3).
3. All bodies together: each dot goes to the body predicted nearest to it,
   then every body's swing X = A sin(2 pi (t - t0) / P) is fitted again, along
   with one scale correction per photo (the step 1 ruler is not perfect; a
   body always swings to the same distance, so each photo's true scale shows).
   Repeat until nothing changes.
4. Checks: the best rival periods for each body (most photos were taken at
   about the same hour, so P and "one turn more or less per day" look alike;
   the nights with many photos decide), and whether the dots also drift a
   little across the line in step with the swing (a circle seen almost edge-on).

Errors, kept separate:
  photo  from the fit (scaled by the actual scatter) and a bootstrap over nights
  site   step 2's site error turns each photo by a tiny angle, which moves X
         by Y * angle; refitting with that change gives the effect (tiny)

Output (output/step3/):
  bodies.json        each body: reach, period, phase, errors, rival periods, tilt
  assignments.csv    every dot: which body (or none), predicted X, residual
  photo_scale.csv    measured scale correction for each photo
  summary.json
  motion.png         X against time with the fitted swings, error bars and bands
  folded.png         each body folded on its period
  piles.png          the |X| pile-ups that count the bodies
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares
from scipy.signal import find_peaks

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, save_json

OUT1, OUT2, OUT3 = OUT / "step1", OUT / "step2", OUT / "step3"
T_REF = datetime(2023, 12, 3)
STRONG_SNR = 40
HIDE_RJ = 2.0          # closer than this to Jupiter's centre: lost in the glare
FULL_VIEW_RJ = 4.0     # the "nothing is there" penalty grows from HIDE_RJ to here
EDGE_MARGIN_RJ = 1.0   # stay this far inside the photo's edge
F_MIN, F_MAX, F_STEP = 0.02, 2.0, 0.0005   # cycles per day searched
NAMES = ["I", "II", "III", "IV", "V", "VI"]  # numbered from Jupiter outward, as Galileo did
RNG = np.random.default_rng(1610)
SITE_AMPLIFY = 1e4     # see the site error in main()


# ---------- data ----------
def load():
    orient = {r["photo"]: r for r in csv.DictReader(open(OUT2 / "orientation.csv"))}
    scale = {r["photo"]: r for r in csv.DictReader(open(OUT1 / "scale.csv"))}
    det = json.load(open(OUT1 / "detections.json"))
    photos = sorted(orient, key=lambda s: orient[s]["local_time"])
    t = np.array([(datetime.fromisoformat(orient[s]["local_time"]) - T_REF).total_seconds() / 86400
                  for s in photos])
    nights = np.array([orient[s]["night"] for s in photos])
    dots = [[] for _ in photos]
    idx = {s: i for i, s in enumerate(photos)}
    for r in csv.DictReader(open(OUT2 / "positions.csv")):
        if r["strong"] != "True" or r["in_band"] != "True":
            continue
        dots[idx[r["photo"]]].append({"dot": int(r["dot"]), "X": float(r["X_rj"]), "Y": float(r["Y_rj"]),
                                      "err_site_Y": float(r["err_site_Y_rj"]), "snr": float(r["snr"])})
    # how far along the line each photo can see, both ways
    view = np.zeros((len(photos), 2))
    for i, s in enumerate(photos):
        j = det[s]["jupiter"]
        rj = float(scale[s]["rj_px"])
        th = np.radians(float(orient[s]["final_plusX_deg"]))
        for k, sgn in enumerate((-1, 1)):
            dx, dy = sgn * np.cos(th), -sgn * np.sin(th)          # image y points down
            lim = []
            for d, p, n in ((dx, j["x"], det[s]["w"]), (dy, j["y"], det[s]["h"])):
                if abs(d) > 1e-9:
                    lim.append(((n if d > 0 else 0) - p) / d)
            view[i, k] = sgn * (min(lim) / rj - EDGE_MARGIN_RJ)
    return photos, t, nights, dots, view


def dot_array(dots, used=None):
    n = max(len(d) for d in dots)
    DX = np.full((len(dots), n), np.nan)
    for i, d in enumerate(dots):
        for k, p in enumerate(d):
            if used is None or not used[i][k]:
                DX[i, k] = p["X"]
    return DX


def sigma_x(X):
    """How far a dot may sit from where a body should be (centring + scale + leftover)."""
    return 0.5 + 0.07 * np.abs(X)


# ---------- 1. count the pile-ups ----------
def pileups(absx, smooth=0.5):
    g = np.arange(0, 30, 0.05)
    h = np.histogram(absx, bins=np.append(g, 30))[0].astype(float)
    k = gaussian_filter1d(h, smooth / 0.05)
    pk, prop = find_peaks(k, prominence=k.max() * 0.12)
    return g, k, g[pk]


# ---------- 2. peel ----------
def score_grid(A, f, ph, t, DX, view, extra_hide=None):
    """Score of every (frequency, phase) for reach A; see module docstring."""
    X = A * np.sin(2 * np.pi * f[:, None, None] * t[None, None, :] + ph[None, :, None])
    sig = sigma_x(X)
    d = np.abs(X[..., None] - DX[None, None])
    d = np.where(np.isnan(d), 1e9, d).min(-1)
    hit = np.exp(-0.5 * (d / sig) ** 2)
    ax = np.abs(X)
    seen = np.clip((ax - HIDE_RJ) / (FULL_VIEW_RJ - HIDE_RJ), 0, 1)
    seen *= (X > view[None, None, :, 0]) & (X < view[None, None, :, 1])   # inside the photo
    if extra_hide is not None:
        seen *= ~extra_hide(X)
    return (2 * hit - 1) * np.where(hit > 0.5, 1.0, seen)


def peel_one(t, DX, view, A_guess, others):
    """Best swing for the outermost body still unexplained."""
    f = np.arange(F_MIN, F_MAX, F_STEP)
    ph = np.linspace(0, 2 * np.pi, 72, endpoint=False)

    def hidden_by_known(X):
        # a known body sitting at the same spot hides this one (their dots merge)
        if not others:
            return np.zeros(X.shape, bool)
        h = np.zeros(X.shape, bool)
        for b in others:
            Xb = b["A"] * np.sin(2 * np.pi * b["f"] * t + b["ph"])
            h |= np.abs(X - Xb[None, None, :]) < 0.8
        return h

    best = None
    per_f = None
    for A in A_guess * np.arange(0.85, 1.26, 0.05):
        S = score_grid(A, f, ph, t, DX, view, hidden_by_known).sum(-1)
        i, j = np.unravel_index(S.argmax(), S.shape)
        if best is None or S[i, j] > best[0]:
            best = (float(S[i, j]), float(A), float(f[i]), float(ph[j]))
            per_f = S.max(1)
    rivals, seen = [], []
    for i in np.argsort(per_f)[::-1]:
        if all(abs(f[i] - x) > 0.01 for x in seen):
            seen.append(f[i])
            rivals.append({"period_d": round(float(1 / f[i]), 4), "score": round(float(per_f[i]), 1)})
        if len(rivals) >= 6:
            break
    # how well a period picked at random does: the best score must stand far above this
    noise = float(np.percentile(per_f, 99))
    return {"score": best[0], "A": best[1], "f": best[2], "ph": best[3], "rivals": rivals, "noise_99": noise}


# ---------- 3. all bodies together ----------
def model_x(b, t):
    return b["A"] * np.sin(2 * np.pi * b["f"] * t + b["ph"])


SCALE_SEARCH = np.exp(np.linspace(np.log(0.5), np.log(1.6), 120))
SCALE_PRIOR = 0.3       # how far (in log) a photo's scale may drift from step 1 before it costs much


def best_scales(bodies, t, dots):
    """For each photo, the scale that lines its dots up best with the bodies' predictions.

    The step 1 ruler can be off a lot for an odd photo (one was taken with a
    different phone, with a bigger glare). Before dots are handed out, every
    scale from 0.5 to 1.6 is tried; a dot costs its distance to the nearest
    prediction (capped), and moving away from 1 costs a little.
    """
    out = np.ones(len(t))
    for i, d in enumerate(dots):
        if not d:
            continue
        X = np.array([p["X"] for p in d])
        pred = np.array([model_x(b, t[i:i + 1])[0] for b in bodies])
        cost = []
        for s in SCALE_SEARCH:
            dist = np.abs(X[:, None] / s - pred[None, :]) / sigma_x(pred)[None, :]
            cost.append(np.sum(np.minimum(dist.min(1), 3) ** 2) + (np.log(s) / SCALE_PRIOR) ** 2)
        out[i] = SCALE_SEARCH[int(np.argmin(cost))]
    return out


def assign(bodies, t, dots, view, scales=None):
    """Each body takes the dot nearest its prediction (within 3 sigma).

    Predictions are stretched by the photo's scale. Two bodies may share a dot
    when they are predicted within 0.8 Rj of each other (their images merge).
    """
    out = [[None] * len(d) for d in dots]           # dot -> list of bodies
    for i, d in enumerate(dots):
        s_i = 1.0 if scales is None else scales[i]
        X = np.array([p["X"] for p in d]) / s_i
        pred = [model_x(b, t[i:i + 1])[0] for b in bodies]
        pairs = []
        for k, xp in enumerate(pred):
            if len(X):
                dist = np.abs(X - xp) / sigma_x(xp)
                for m in np.argsort(dist):
                    pairs.append((dist[m], k, m))
        pairs.sort()
        taken_b, taken_d = set(), {}
        for dist, k, m in pairs:
            if dist > 3 or k in taken_b:
                continue
            if m in taken_d and abs(pred[taken_d[m][0]] - pred[k]) > 0.8:
                continue
            taken_b.add(k)
            taken_d.setdefault(m, []).append(k)
        for m, ks in taken_d.items():
            out[i][m] = ks
    return out


def joint_fit(bodies, t, dots, asg, photo_scale=True, x_shift=None, start_scales=None):
    """Least squares for every body's swing plus one scale per photo."""
    obs = []                                         # (photo, body, X, sigma)
    for i, d in enumerate(dots):
        for m, ks in enumerate(asg[i]):
            if not ks:
                continue
            X = d[m]["X"] + (x_shift[i][m] if x_shift is not None else 0.0)
            for k in ks:
                obs.append((i, k, X))
    obs_i = np.array([o[0] for o in obs])
    obs_k = np.array([o[1] for o in obs])
    obs_x = np.array([o[2] for o in obs])
    nb = len(bodies)
    # photos with a scale of their own: those with dots of >= 2 bodies (else it is a free stretch of one dot)
    nper = np.bincount(obs_i, minlength=len(t))
    free = np.where(nper >= 2)[0] if photo_scale else np.zeros(0, int)
    fidx = {p: n for n, p in enumerate(free)}
    ls0 = np.log(start_scales[free]) if start_scales is not None and len(free) else np.zeros(len(free))
    p0 = np.concatenate([[b["A"], b["f"], b["ph"]] for b in bodies] + [ls0])

    def res(p):
        A, f, ph = p[0:3 * nb:3], p[1:3 * nb:3], p[2:3 * nb:3]
        ls = p[3 * nb:]
        s = np.ones(len(t))
        if len(free):
            s[free] = np.exp(ls)
        pred = A[obs_k] * np.sin(2 * np.pi * f[obs_k] * t[obs_i] + ph[obs_k])
        r = (obs_x / s[obs_i] - pred) / sigma_fit(pred)
        prior = ls / SCALE_PRIOR
        return np.concatenate([r, prior, [np.sum(ls) / 0.01]])   # mean log-scale held at 0

    sol = least_squares(res, p0, loss="soft_l1", f_scale=2.5)
    p = sol.x
    r = res(p)[:len(obs)]
    chi2 = float(np.sum(r ** 2) / max(len(obs) - len(p), 1))
    J = sol.jac
    cov = np.linalg.pinv(J.T @ J) * max(chi2, 1.0)
    new = []
    for k in range(nb):
        A, f, ph = p[3 * k:3 * k + 3]
        if A < 0:
            A, ph = -A, ph + np.pi
        new.append(dict(bodies[k], A=float(A), f=float(f), ph=float(ph % (2 * np.pi))))
    scales = np.ones(len(t))
    if len(free):
        scales[free] = np.exp(p[3 * nb:])
    return new, scales, free, cov, chi2, (obs_i, obs_k, obs_x), r


def sigma_fit(X):
    """Per-dot error in the joint fit, where the photo scale is fitted separately."""
    return 0.25 + 0.02 * np.abs(X)


# ---------- 4. checks ----------
def rival_table(b, t, DX_all, view, others):
    """Score of the chosen period against its 'one turn more/less per day' rivals."""
    f0 = b["f"]
    cands = sorted({round(x, 6) for x in [f0, abs(1 - f0), 1 + f0, abs(f0 - 1), abs(2 - f0), f0 + 2,
                                          abs(f0 - 0.5), f0 + 0.5] if F_MIN <= x <= 3})
    out = []
    for fc in cands:
        ff = fc + np.arange(-0.004, 0.0041, 0.0002)
        ph = np.linspace(0, 2 * np.pi, 144, endpoint=False)
        S = score_grid(b["A"], ff, ph, t, DX_all, view).sum(-1)
        out.append({"period_d": round(1 / fc, 4), "score": round(float(S.max()), 1)})
    out.sort(key=lambda x: -x["score"])
    return out


def tilt(b, t, dots, asg, k):
    """Do the dots drift across the line in step with the swing? Y = B cos(phase) + C."""
    ph, Y = [], []
    for i, d in enumerate(dots):
        for m, ks in enumerate(asg[i]):
            if ks == [k]:
                ph.append(2 * np.pi * b["f"] * t[i] + b["ph"])
                Y.append(d[m]["Y"])
    if len(Y) < 6:
        return None
    ph, Y = np.array(ph), np.array(Y)
    M = np.vstack([np.cos(ph), np.ones_like(ph)]).T
    c, *_ = np.linalg.lstsq(M, Y, rcond=None)
    res = Y - M @ c
    s2 = np.sum(res ** 2) / max(len(Y) - 2, 1)
    cov = np.linalg.inv(M.T @ M) * s2
    return {"B_rj": float(c[0]), "B_err_rj": float(np.sqrt(cov[0, 0])), "offset_rj": float(c[1]),
            "n": int(len(Y)), "tilt_deg": float(np.degrees(np.arcsin(np.clip(c[0] / b["A"], -1, 1))))}


# ---------- pictures ----------
def plots(bodies, cov, t, dots, asg, scales, free, scale_sig, g, k):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = {b["name"]: c for b, c in zip(bodies, ["C3", "C1", "C2", "C0", "C4", "C5"])}
    nb = len(bodies)

    def band(b, kk, tt):
        p = np.array([b["A"], b["f"], b["ph"]])
        C = cov[3 * kk:3 * kk + 3, 3 * kk:3 * kk + 3]
        x = p[0] * np.sin(2 * np.pi * p[1] * tt + p[2])
        J = np.vstack([np.sin(2 * np.pi * p[1] * tt + p[2]),
                       p[0] * np.cos(2 * np.pi * p[1] * tt + p[2]) * 2 * np.pi * tt,
                       p[0] * np.cos(2 * np.pi * p[1] * tt + p[2])]).T
        return x, np.sqrt(np.einsum("ij,jk,ik->i", J, C, J))

    def dot_err(X, i):
        # centring error, plus the photo's scale error when it has no scale of its own
        own = i in set(free)
        return np.hypot(sigma_fit(X), 0 if own else abs(X) * scale_sig)

    # motion against time: whole run + the two busiest nights
    fig = plt.figure(figsize=(14, 9))
    axes = [fig.add_subplot(2, 1, 1), fig.add_subplot(2, 2, 3), fig.add_subplot(2, 2, 4)]
    spans = [(t.min() - 0.5, t.max() + 0.5), (36.6, 37.15), (37.6, 38.15)]
    for ax, (a, b_) in zip(axes, spans):
        tt = np.linspace(a, b_, 4000)
        for kk, b in enumerate(bodies):
            x, e = band(b, kk, tt)
            ax.plot(tt, x, color=col[b["name"]], lw=0.8)
            ax.fill_between(tt, x - e, x + e, color=col[b["name"]], alpha=0.25, lw=0)
        for i, d in enumerate(dots):
            if not a <= t[i] <= b_:
                continue
            for m, ks in enumerate(asg[i]):
                X = d[m]["X"] / scales[i]
                c = col[bodies[ks[0]]["name"]] if ks else "0.5"
                ax.errorbar(t[i], X, yerr=dot_err(X, i), fmt="o" if ks else "x", ms=3.5, color=c,
                            ecolor=c, elinewidth=0.8, capsize=1.5)
        ax.axhspan(-HIDE_RJ, HIDE_RJ, color="0.85", lw=0)
        ax.set_xlim(a, b_)
        ax.set_ylabel("X (Jupiter radii)")
        ax.grid(alpha=0.3)
    axes[0].set_xlabel("days since 2023-12-03 00:00 local time")
    axes[0].set_title("Every bright dot (error bars) and the fitted swing of each body (line, ±1σ band). "
                      "x = dot given to no body; grey = Jupiter's glare", fontsize=9)
    axes[1].set_title("night of 2024-01-08", fontsize=9)
    axes[2].set_title("night of 2024-01-09", fontsize=9)
    for ax in axes[1:]:
        ax.set_xlabel("days since 2023-12-03")
    handles = [plt.Line2D([], [], color=col[b["name"]], marker="o", lw=1,
                          label=f"{b['name']}: P = {b['P']:.4f} ± {b['P_err']:.4f} d, reach {b['A']:.1f} Rj")
               for b in bodies]
    axes[0].legend(handles=handles, fontsize=8, loc="upper right", ncol=2)
    fig.tight_layout()
    fig.savefig(OUT3 / "motion.png", dpi=120)
    plt.close(fig)

    # folded on each period
    fig, axs = plt.subplots(1, nb, figsize=(3.6 * nb, 3.6), sharey=False)
    for kk, b in enumerate(bodies):
        ax = axs[kk]
        phase = np.linspace(0, 1, 300)
        ax.plot(phase, b["A"] * np.sin(2 * np.pi * phase), color=col[b["name"]], lw=1)
        for i, d in enumerate(dots):
            for m, ks in enumerate(asg[i]):
                if ks and kk in ks:
                    X = d[m]["X"] / scales[i]
                    ph = ((b["f"] * t[i] + b["ph"] / (2 * np.pi)) % 1)
                    ax.errorbar(ph, X, yerr=dot_err(X, i), fmt="o", ms=3, color=col[b["name"]], elinewidth=0.7)
        ax.set_title(f"{b['name']}: P = {b['P']:.4f} ± {b['P_err']:.4f} d", fontsize=9)
        ax.set_xlabel("fraction of the period")
        ax.grid(alpha=0.3)
    axs[0].set_ylabel("X (Jupiter radii)")
    fig.tight_layout()
    fig.savefig(OUT3 / "folded.png", dpi=120)
    plt.close(fig)

    # pile-ups
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(g, k, "k-", lw=1)
    for b in bodies:
        ax.axvline(b["A"], color=col[b["name"]], lw=1, ls="--")
        ax.text(b["A"], k.max() * 1.02, b["name"], color=col[b["name"]], ha="center", fontsize=9)
    ax.set_xlabel("|X| of every bright dot (Jupiter radii), smoothed count")
    ax.set_title("Distances pile up where each body turns back (dashed = fitted reach)", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT3 / "piles.png", dpi=120)
    plt.close(fig)


def main():
    OUT3.mkdir(parents=True, exist_ok=True)
    photos, t, nights, dots, view = load()
    DX_all = dot_array(dots)
    absx = np.abs(DX_all[np.isfinite(DX_all)])
    g, kde, peaks = pileups(absx)
    print("pile-ups at |X| =", np.round(peaks, 2))

    # --- peel ---
    used = [[False] * len(d) for d in dots]
    bodies = []
    for attempt in range(3 * len(NAMES)):
        if len(bodies) >= len(NAMES):
            break
        DX = dot_array(dots, used)
        rem = np.abs(DX[np.isfinite(DX)])
        if len(rem) < 6:
            break
        _, _, pk = pileups(rem)
        if not len(pk):
            break
        A_guess = float(pk.max())
        b = peel_one(t, DX, view, A_guess, bodies)
        n_hit = 0
        for i, d in enumerate(dots):
            xp = model_x(b, t[i:i + 1])[0]
            for m, p in enumerate(d):
                if not used[i][m] and abs(p["X"] - xp) < 2 * sigma_x(xp):
                    used[i][m] = True
                    n_hit += 1
                    break
        print(f"  body found: reach {b['A']:.1f} Rj, period {1 / b['f']:.3f} d, score {b['score']:.1f} "
              f"(99% of other periods score below {b['noise_99']:.1f}), dots {n_hit}")
        same = [x for x in bodies if abs(x["f"] - b["f"]) < 0.01 and abs(x["A"] - b["A"]) < 0.25 * x["A"]]
        if same:                     # leftover dots of a body already found: set them aside, look again
            print("    (same as a body already found; its dots are set aside)")
            if n_hit == 0:           # nothing new left to find
                break
            continue
        if b["score"] < b["noise_99"] + 3 or n_hit < 5:   # not clearly better than chance
            break
        b["dots_at_peel"] = n_hit
        bodies.append(b)

    # --- all together ---
    for it in range(6):
        sc = best_scales(bodies, t, dots)
        asg = assign(bodies, t, dots, view, sc)
        bodies, scales, free, cov, chi2, obs, r = joint_fit(bodies, t, dots, asg, start_scales=sc)
    sc = best_scales(bodies, t, dots)
    asg = assign(bodies, t, dots, view, sc)
    bodies, scales, free, cov, chi2, obs, r = joint_fit(bodies, t, dots, asg, start_scales=sc)

    # order from Jupiter outward and name them
    order = np.argsort([b["A"] for b in bodies])
    perm = {int(o): n for n, o in enumerate(order)}
    bodies = [bodies[o] for o in order]
    idx3 = np.concatenate([np.arange(3 * o, 3 * o + 3) for o in order])
    cov_b = cov[np.ix_(idx3, idx3)]
    asg = [[None if ks is None else sorted(perm[k] for k in ks) for ks in row] for row in asg]
    for n, b in enumerate(bodies):
        b["name"] = NAMES[n]

    # --- errors: fit covariance and a bootstrap over nights ---
    uniq = np.unique(nights)
    boot = []
    for _ in range(200):
        pick = RNG.choice(uniq, len(uniq))
        w = np.zeros(len(t), int)
        for nn in pick:
            w[nights == nn] += 1
        dots_b, t_b, asg_b = [], [], []
        for i in range(len(t)):
            for _ in range(w[i]):
                dots_b.append(dots[i]); t_b.append(t[i]); asg_b.append(asg[i])
        bb, *_ = joint_fit(bodies, np.array(t_b), dots_b, asg_b, start_scales=np.repeat(scales, w))
        boot.append([1 / x["f"] for x in bb] + [x["A"] for x in bb])
    boot = np.array(boot)

    # --- site: turn each photo by its step 2 site angle (X moves by Y * angle) ---
    # the change is far below the fit's numerical precision, so it is applied SITE_AMPLIFY times
    # larger and the result scaled back (the response is linear at this size)
    orient = {r["photo"]: r for r in csv.DictReader(open(OUT2 / "orientation.csv"))}
    shift = [[SITE_AMPLIFY * p["Y"] * np.radians(float(orient[photos[i]]["err_site_deg"])) for p in d]
             for i, d in enumerate(dots)]
    bs, *_ = joint_fit(bodies, t, dots, asg, x_shift=shift, start_scales=scales)
    b0, *_ = joint_fit(bodies, t, dots, asg, start_scales=scales)        # same start, no shift

    out = []
    for kk, b in enumerate(bodies):
        P = 1 / b["f"]
        P_err_fit = float(np.sqrt(cov_b[3 * kk + 1, 3 * kk + 1]) / b["f"] ** 2)
        P_err_boot = float(np.std(boot[:, kk]))
        A_err_fit = float(np.sqrt(cov_b[3 * kk, 3 * kk]))
        A_err_boot = float(np.std(boot[:, len(bodies) + kk]))
        b.update(P=float(P), P_err=max(P_err_fit, P_err_boot), A_err=max(A_err_fit, A_err_boot))
        others = [x for x in bodies if x is not b]
        n_dots = sum(1 for row in asg for ks in row if ks and kk in ks)
        out.append({
            "name": b["name"], "reach_rj": b["A"], "reach_err_photo_rj": b["A_err"],
            "period_d": P, "period_err_photo_d": b["P_err"],
            "period_err_fit_d": P_err_fit, "period_err_bootstrap_d": P_err_boot,
            "period_err_site_d": float(abs(1 / bs[kk]["f"] - 1 / b0[kk]["f"]) / SITE_AMPLIFY),
            "reach_err_site_rj": float(abs(bs[kk]["A"] - b0[kk]["A"]) / SITE_AMPLIFY),
            "phase_rad": b["ph"], "dots": n_dots,
            "freq_per_day": b["f"],
            "cov_reach_freq_phase": cov_b[3 * kk:3 * kk + 3, 3 * kk:3 * kk + 3].tolist(),
            "found_at_peel_score": b["score"], "chance_score_99pct": b["noise_99"], "peel_rivals": b["rivals"],
            "rival_periods": rival_table(b, t, DX_all, view, others),
            "drift_across_line": tilt(b, t, dots, asg, kk),
        })

    ratios = scales[free]
    scale_sig = float(1.4826 * np.median(np.abs(np.log(ratios))))
    plots(bodies, cov_b, t, dots, asg, scales, free, scale_sig, g, kde)

    with open(OUT3 / "assignments.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["photo", "dot", "t_days", "X_rj", "X_rj_scale_corrected", "body", "predicted_X_rj", "residual_rj"])
        for i, d in enumerate(dots):
            for m, p in enumerate(d):
                ks = asg[i][m]
                name = "+".join(bodies[k]["name"] for k in ks) if ks else ""
                pred = model_x(bodies[ks[0]], t[i:i + 1])[0] if ks else None
                xc = p["X"] / scales[i]
                wr.writerow([photos[i], p["dot"], round(t[i], 5), p["X"], round(xc, 3), name,
                             "" if pred is None else round(pred, 3), "" if pred is None else round(xc - pred, 3)])
    with open(OUT3 / "photo_scale.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["photo", "scale_correction", "fitted"])
        for i, s in enumerate(photos):
            wr.writerow([s, round(float(scales[i]), 4), i in set(free)])

    n_all = sum(len(d) for d in dots)
    n_asg = sum(1 for row in asg for ks in row if ks)
    resid = np.concatenate([[d[m]["X"] / scales[i] - model_x(bodies[asg[i][m][0]], t[i:i + 1])[0]
                             for m in range(len(d)) if asg[i][m]] for i, d in enumerate(dots)])
    summary = {
        "pile_ups_rj": [round(float(x), 2) for x in peaks],
        "bodies_found": len(bodies),
        "dots": {"bright_in_band": n_all, "given_to_a_body": n_asg, "given_to_none": n_all - n_asg},
        "residual_rms_rj": float(np.sqrt(np.mean(resid ** 2))),
        "residual_robust_rj": float(1.4826 * np.median(np.abs(resid))),
        "photo_scale": {"photos_with_own_scale": int(len(free)),
                        "measured_single_photo_scale_scatter": scale_sig,
                        "note": "step 1 claimed 1.7-3.5% per photo"},
        "reduced_chi2": chi2,
        "bodies": out,
    }
    save_json(summary, OUT3 / "summary.json")
    save_json(out, OUT3 / "bodies.json")
    print(json.dumps({k: v for k, v in summary.items() if k != "bodies"}, indent=1))
    for o in out:
        print(f"{o['name']:>3}: P = {o['period_d']:.4f} ± {o['period_err_photo_d']:.4f} d (site ± {o['period_err_site_d']:.1e})"
              f"   reach {o['reach_rj']:.2f} ± {o['reach_err_photo_rj']:.2f} Rj   dots {o['dots']}"
              f"   rivals {o['rival_periods'][:3]}   tilt {o['drift_across_line']}")


if __name__ == "__main__":
    main()
