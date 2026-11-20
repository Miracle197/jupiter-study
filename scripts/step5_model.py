"""Step 5: the model -- the four swings and every photo's own scale, fitted together.

Step 4 found four bodies and which dot belongs to which (part 5), using each
photo's scale from step 1 (good to about +-5%). Now that the swings are known,
the photos can be put on a common scale much better: a body always swings out
to the same distance, so in a photo with dots of two or more bodies, all of
them have to agree on one stretch factor for that photo.

Fitted together (least squares, robust):
  X_dot = s_photo * A_k sin(2 pi f_k t + phi_k)
for every dot and the body (or bodies, when two share a dot) it belongs to.
  s_photo   one factor per photo with dots of at least two different bodies
            (other photos keep step 1's scale); each factor is held near 1
            within step 1's error for that photo, and their mean is 1, so the
            unit is still step 1's Rj.
After the fit the dots are handed out again, photo by photo: every stretch from
0.6 to 1.6 is tried, and at each one the dots go to the bodies one to one (a
body gives at most one dot in a photo; two bodies predicted within 0.8 Rj of
each other may share one, their images merge). The stretch and hand-out that
line the dots up best win. Step 4 handed out each dot on its own, so in a
photo whose step 1 scale was far off (12/17, another phone with a bigger glare)
three dots went to one body. The fit is repeated until the hand-out stays the
same. Then, on the corrected positions:
  Y_dot = B_k cos(2 pi f_k t + phi_k) + C_k
the drift across the line: the swing is a circle seen almost edge-on, tilted
by asin(B_k / A_k).

Errors: the larger of the fit's own (scaled by the actual scatter) and a
bootstrap over nights (whole nights resampled, 120 refits).

Output: output/step5/model.json, demo/model_data.json (for the page),
        demo/final/<photo>.jpg (each photo turned, put on the common scale and
        cut to a strip around the line; the page draws the labels on top),
        output/step5/annotated.jpg (all 58 strips with the labels drawn in),
        output/step5/model.png (the four orbits from above and from the Earth).
"""
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares, linear_sum_assignment

sys.path.insert(0, str(Path(__file__).parent))
import step4_joint as J  # noqa: E402
import step4_peel as P  # noqa: E402
from common import RAW, ImageOps, photo_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "step5"
DEMO = ROOT / "demo"
T_REF = datetime(2023, 12, 3)
NAMES = J.NAMES
SIG0, SIG1 = 0.10, 0.01          # Rj: dot error once the photo's scale is fitted (centring + turning)
PRIOR_MIN = 0.10                  # a photo's scale may move this much (in log) before it costs much
S_GRID = np.exp(np.linspace(np.log(0.6), np.log(1.6), 161))
SEARCH_PRIOR = 0.3                # how much trying a stretch away from step 1 costs while handing out
SHARE = 0.8                       # Rj: two bodies predicted this close may share one dot
STRIP_HALF_X, STRIP_HALF_Y = 27.0, 6.75   # Rj: the corrected strip, 4:1
STRIP_PX_PER_RJ = 20              # page strip: 1080 x 270 px
SHEET_PX_PER_RJ = 14              # README sheet
RNG = np.random.default_rng(1610)


def sig(X):
    return SIG0 + SIG1 * np.abs(X)


# ---------- data ----------
def load():
    joint = json.load(open(ROOT / "output/step4/joint.json"))
    rows = [r for r in csv.DictReader(open(ROOT / "output/step2/positions.csv"))
            if r["strong"] == "True" and r["in_band"] == "True"]
    if len(rows) != len(joint["dots"]) or any(abs(float(r["X_rj"]) - d["X"]) > 1e-9 for r, d in zip(rows, joint["dots"])):
        raise SystemExit("output/step4/joint.json does not match output/step2/positions.csv: rerun step 4")
    dots = [{"photo": r["photo"], "dot": int(r["dot"]), "t": d["t"], "X": d["X"], "Y": d["Y"]}
            for r, d in zip(rows, joint["dots"])]
    scale = {r["photo"]: r for r in csv.DictReader(open(ROOT / "output/step1/scale.csv"))}
    orient = {r["photo"]: r for r in csv.DictReader(open(ROOT / "output/step2/orientation.csv"))}
    return joint, dots, scale, orient


# ---------- the fit ----------
def unpack(p, nb):
    f, a, b = p[0:3 * nb:3], p[1:3 * nb:3], p[2:3 * nb:3]
    return f, a, b, p[3 * nb:]


def fit(B0, t, X, assign, photo_idx, free, prior, start_ls=None):
    """B0: [(f, a, b)]; returns bodies, log-scales of the free photos, covariance, chi2, residuals."""
    nb = len(B0)
    obs = [(i, k) for i, ks in enumerate(assign) for k in ks]
    oi = np.array([o[0] for o in obs]); ok = np.array([o[1] for o in obs])
    slot = {p: n for n, p in enumerate(free)}
    os_ = np.array([slot.get(photo_idx[i], -1) for i in oi])
    pr = np.array([prior[p] for p in free])
    ls0 = np.zeros(len(free)) if start_ls is None else start_ls
    p0 = np.concatenate([np.ravel(B0), ls0])

    def res(p):
        f, a, b, ls = unpack(p, nb)
        s = np.where(os_ >= 0, np.exp(ls[np.maximum(os_, 0)]), 1.0)
        w = 2 * np.pi * f[ok]
        model = a[ok] * np.sin(w * t[oi]) + b[ok] * np.cos(w * t[oi])
        r = (X[oi] / s - model) / sig(model)
        return np.concatenate([r, ls / pr, [np.sum(ls / pr ** 2) / np.sum(1 / pr ** 2) / 1e-3]])

    sol = least_squares(res, p0, loss="soft_l1", f_scale=2.5, x_scale="jac")
    r = res(sol.x)[:len(obs)]
    chi2 = float(np.sum(r ** 2) / max(len(obs) - 3 * nb, 1))
    cov = np.linalg.pinv(sol.jac.T @ sol.jac) * max(chi2, 1.0)
    f, a, b, ls = unpack(sol.x, nb)
    return [(float(f[k]), float(a[k]), float(b[k])) for k in range(nb)], ls, cov, chi2


def corrected(X, photo_idx, free, ls):
    s = np.ones(len(X))
    slot = {p: n for n, p in enumerate(free)}
    for i, p in enumerate(photo_idx):
        if p in slot:
            s[i] = math.exp(ls[slot[p]])
    return X / s, s


def free_photos(assign, photo_idx):
    """Photos with dots of at least two different bodies: only these can tell their own scale."""
    seen = {}
    for i, ks in enumerate(assign):
        seen.setdefault(photo_idx[i], set()).update(ks)
    return sorted(p for p, ks in seen.items() if len(ks) >= 2)


def match_photo(B, tq, X):
    """Best stretch and one-to-one hand-out of one photo's dots (X: their step 1 positions).

    Returns the stretch and, per dot, the list of bodies it belongs to.
    """
    pred = np.array([J.swing(*fb, tq) for fb in B])
    sd = P.sig(pred)
    n, k = len(X), len(B)
    grid = S_GRID if n >= 2 else np.array([1.0])        # one dot cannot tell its own stretch
    best = None
    for st in grid:
        d2 = ((X / st)[:, None] - pred[None, :]) ** 2 / sd[None, :] ** 2
        cost = np.hstack([d2, np.full((n, n), 9.0)])     # the extra columns: "no body" (a 3-sigma miss)
        r, c = linear_sum_assignment(cost)
        tot = cost[r, c].sum() + (np.log(st) / SEARCH_PRIOR) ** 2
        if best is None or tot < best[0]:
            best = (tot, st, dict(zip(r.tolist(), c.tolist())))
    _, st, pick = best
    out = [[pick[i]] if pick.get(i, k) < k else [] for i in range(n)]
    taken = {ks[0] for ks in out if ks}
    for j in range(k):                                    # merged images: a body left out shares a dot
        if j in taken or abs(pred[j]) < P.HIDE:
            continue
        for i, ks in enumerate(out):
            if ks and abs(pred[ks[0]] - pred[j]) < SHARE and abs(X[i] / st - pred[j]) < 2 * sd[j]:
                ks.append(j); break
    return st, [sorted(ks) for ks in out]


def handout(B, t, X, photo_idx):
    by = {}
    for i, p in enumerate(photo_idx):
        by.setdefault(p, []).append(i)
    asg = [None] * len(X)
    for p, idx in by.items():
        _, ks = match_photo(B, t[idx[0]], X[idx])
        for i, kk in zip(idx, ks):
            asg[i] = kk
    return asg


def solve(B0, assign0, t, X, photo_idx, prior_all, it=6):
    """Fit, hand the dots out again photo by photo, repeat until the hand-out stays the same."""
    assign = assign0
    for n in range(it):
        free = free_photos(assign, photo_idx)
        B, ls, cov, chi2 = fit(B0, t, X, assign, photo_idx, free, {p: prior_all[p] for p in free})
        new = handout(B, t, X, photo_idx)
        B0 = B
        changed = sum(a != b for a, b in zip(new, assign))
        print(f"  round {n + 1}: {changed} dots change hands", file=sys.stderr)
        if not changed:
            return B, ls, cov, chi2, assign, free
        assign = new
    free = free_photos(assign, photo_idx)
    B, ls, cov, chi2 = fit(B0, t, X, assign, photo_idx, free, {p: prior_all[p] for p in free})
    return B, ls, cov, chi2, assign, free


def tilt(fb, t, Y):
    return J.tilt(fb, t, Y)


def bootstrap(B, t, X, assign, photo_idx, nights, prior_all, n=120):
    """Resample whole nights; refit the swings and scales with the assignment held fixed."""
    names = sorted(set(nights))
    by = {nm: np.where(nights == nm)[0] for nm in names}
    out = []
    for _ in range(n):
        pick = RNG.choice(names, len(names))
        idx = np.concatenate([by[nm] for nm in pick])
        # each resampled copy of a photo is its own photo (its scale is fitted separately)
        pid = [f"{photo_idx[i]}#{c}" for c, nm in enumerate(pick) for i in by[nm]]
        asg = [assign[i] for i in idx]
        free = free_photos(asg, pid)
        prior = {p: prior_all[p.split("#")[0]] for p in free}
        try:
            Bb, *_ = fit(B, t[idx], X[idx], asg, pid, free, prior)
        except Exception:
            continue
        out.append([v for fb in Bb for v in (1 / fb[0], math.hypot(fb[1], fb[2]))])
    return np.array(out)


# ---------- pictures ----------
def strip_image(rec, jup, rj_px, angle_deg, s, px_per_rj, gamma=0.6):
    """The photo turned so the line is horizontal with +X to the right, at px_per_rj on the common scale."""
    from PIL import Image
    im = ImageOps.exif_transpose(Image.open(RAW / rec["file"])).convert("RGB")
    W, H = int(round(2 * STRIP_HALF_X * px_per_rj)), int(round(2 * STRIP_HALF_Y * px_per_rj))
    c = s * rj_px / px_per_rj                     # photo pixels per strip pixel
    r = min(1.0, 1.25 / c)                        # shrink first so the turn does not alias
    if r < 1:
        im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.Resampling.LANCZOS)
    jx, jy, c = jup["x"] * r, jup["y"] * r, c * r
    th = math.radians(angle_deg)
    a, b = c * math.cos(th), c * math.sin(th)
    d, e = -c * math.sin(th), c * math.cos(th)
    u0, v0 = W / 2, H / 2
    out = im.transform((W, H), Image.Transform.AFFINE, (a, b, jx - a * u0 - b * v0, d, e, jy - d * u0 - e * v0),
                       resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0))
    return out.point(lambda v: int(255 * (v / 255) ** gamma))


def sheet(photos, recs, det, scale, orient, bodies, path, cols=2):
    from PIL import Image, ImageDraw, ImageFont
    K = SHEET_PX_PER_RJ
    W, H = int(2 * STRIP_HALF_X * K), int(2 * STRIP_HALF_Y * K)
    lab_h = 18
    rows = (len(photos) + cols - 1) // cols
    out = Image.new("RGB", (cols * W + (cols - 1) * 8, rows * (H + lab_h + 6)), (10, 12, 18))
    dr = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
        small = ImageFont.truetype("DejaVuSans-Bold.ttf", 11)
    except OSError:
        font = small = ImageFont.load_default()
    cols_rgb = [(239, 122, 99), (232, 180, 69), (92, 196, 133), (116, 162, 245)]
    for n, ph in enumerate(photos):
        s = ph["id"]
        x0 = (n % cols) * (W + 8); y0 = (n // cols) * (H + lab_h + 6)
        im = strip_image(recs[s], det[s]["jupiter"], float(scale[s]["rj_px"]), float(orient[s]["final_plusX_deg"]), ph["scale_fix"], K)
        out.paste(im, (x0, y0 + lab_h))
        X = lambda v: x0 + W / 2 + v * K
        Y = lambda v: y0 + lab_h + H / 2 - v * K
        for v in range(-25, 26, 5):
            dr.line([(X(v), y0 + lab_h + H - 5), (X(v), y0 + lab_h + H)], fill=(90, 100, 130))
        for k, pr in enumerate(ph["pred"]):
            if abs(pr["X"]) > STRIP_HALF_X - 0.5:
                continue
            dr.line([(X(pr["X"]), Y(pr["Y"]) - 13), (X(pr["X"]), Y(pr["Y"]) - 8)], fill=cols_rgb[k], width=2)
        for d in ph["dots"]:
            ks = d["bodies"]
            c = cols_rgb[ks[0]] if ks else (170, 170, 170)
            dr.ellipse([X(d["X"]) - 6, Y(d["Y"]) - 6, X(d["X"]) + 6, Y(d["Y"]) + 6], outline=c, width=2)
            name = "+".join(NAMES[k] for k in ks) if ks else "?"
            dr.text((X(d["X"]) - 6, Y(d["Y"]) + 7), name, fill=c, font=small)
        dr.text((x0 + 2, y0 + 2), f"{ph['time'].replace('T', ' ')}   scale x{ph['scale_fix']:.3f}", fill=(200, 205, 215), font=font)
    out.save(path, quality=86)


def model_plot(bodies, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = ["#ef7a63", "#e8b445", "#5cc485", "#74a2f5"]
    fig, ax = plt.subplots(1, 2, figsize=(12, 5.6), gridspec_kw={"width_ratios": [1, 1.25]})
    th = np.linspace(0, 2 * np.pi, 400)
    for a in ax:
        a.set_facecolor("#0b0e15")
        a.add_patch(plt.Circle((0, 0), 1, color="#e9d9b6"))
    for k, b in enumerate(bodies):
        A, eps = b["reach_rj"], math.radians(b["tilt_deg"])
        ax[0].plot(A * np.sin(th), A * np.cos(eps) * np.cos(th), color=cols[k], lw=1.6, label=f"{b['name']}  P = {b['period_d']:.4f} d")
        ax[1].plot(A * np.sin(th), A * np.sin(eps) * np.cos(th), color=cols[k], lw=1.6)
    ax[0].set(xlim=(-25, 25), ylim=(-25, 25), aspect="equal", title="from above (up = toward the Earth or away: photos cannot tell)",
              xlabel="X (Rj, +X = the end that is right in every turned photo)", ylabel="depth (Rj)")
    ax[0].legend(loc="lower right", fontsize=8, facecolor="#1a1f2b", labelcolor="#e4e8f0")
    ax[1].set(xlim=(-25, 25), ylim=(-2, 2), title="from the Earth (across the line stretched x6)", xlabel="X (Rj)", ylabel="Y (Rj)")
    ax[1].set_aspect(6)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------- main ----------
def main():
    joint, dots, scale, orient = load()
    recs = {r["stem"]: r for r in photo_list()}
    det = json.load(open(ROOT / "output/step1/detections.json"))
    t = np.array([d["t"] for d in dots]); X = np.array([d["X"] for d in dots]); Y = np.array([d["Y"] for d in dots])
    photo_idx = [d["photo"] for d in dots]
    nights = np.array([orient[d["photo"]]["night"] for d in dots])
    prior_all = {s: max(float(r["err_photo_pct"]) / 100, PRIOR_MIN) for s, r in scale.items()}

    B0 = [(b["freq"], b["a"], b["b"]) for b in joint["bodies"]]
    B, ls, cov, chi2, assign, free = solve(B0, joint["assign"], t, X, photo_idx, prior_all)
    Xc, s = corrected(X, photo_idx, free, ls)
    Yc = Y / s
    nb = len(B)
    pred = np.array([[J.swing(*fb, tt) for fb in B] for tt in t])
    res = np.array([Xc[i] - pred[i, ks[0]] for i, ks in enumerate(assign) if ks])
    print(f"photos with their own scale: {len(free)};  dots assigned {sum(1 for a in assign if a)} of {len(assign)}, "
          f"shared {sum(1 for a in assign if len(a) > 1)};  residual rms {np.sqrt(np.mean(res ** 2)):.3f} Rj, "
          f"robust {1.4826 * np.median(np.abs(res)):.3f} Rj;  reduced chi2 {chi2:.2f}", file=sys.stderr)
    scale_sd = float(np.std(ls))
    scale_mad = float(1.4826 * np.median(np.abs(ls - np.median(ls))))
    print(f"scale corrections: rms {100 * scale_sd:.1f}%, typical (robust) {100 * scale_mad:.1f}%", file=sys.stderr)

    boot = bootstrap(B, t, X, assign, photo_idx, nights, prior_all)
    bodies = []
    for k, (f, a, b) in enumerate(B):
        A = math.hypot(a, b); ph = math.atan2(b, a)
        # errors of f and A from the covariance of (f, a, b)
        C = cov[3 * k:3 * k + 3, 3 * k:3 * k + 3]
        g_A = np.array([0, a / A, b / A])
        err_P_fit = math.sqrt(max(C[0, 0], 0)) / f ** 2
        err_A_fit = math.sqrt(max(g_A @ C @ g_A, 0))
        err_P_boot = float(np.std(boot[:, 2 * k])) if len(boot) else 0.0
        err_A_boot = float(np.std(boot[:, 2 * k + 1])) if len(boot) else 0.0
        single = np.array([len(ks) == 1 and ks[0] == k for ks in assign])
        tl = tilt((f, a, b), t[single], Yc[single])
        eps = math.degrees(math.asin(max(-1.0, min(1.0, tl["B_rj"] / A))))
        bodies.append({"name": NAMES[k], "freq": f, "a": a, "b": b, "period_d": 1 / f,
                       "period_err_d": max(err_P_fit, err_P_boot), "period_err_fit_d": err_P_fit, "period_err_boot_d": err_P_boot,
                       "reach_rj": A, "reach_err_rj": max(err_A_fit, err_A_boot), "phase_rad": ph,
                       "dots": int(sum(k in ks for ks in assign)),
                       "tilt": tl, "tilt_deg": eps, "tilt_err_deg": math.degrees(tl["B_err_rj"] / A),
                       "cov_f_a_b": C.tolist()})
        print(f"{NAMES[k]:>4}: P = {1 / f:.5f} ± {bodies[-1]['period_err_d']:.5f} d (fit {err_P_fit:.5f}, boot {err_P_boot:.5f}), "
              f"reach {A:.2f} ± {bodies[-1]['reach_err_rj']:.2f} Rj, tilt B {tl['B_rj']:+.3f} ± {tl['B_err_rj']:.3f} -> {eps:+.2f}°", file=sys.stderr)

    # every photo: its own scale fix, its dots with labels, and what the model says at that moment
    slot = {p: n for n, p in enumerate(free)}
    stems = sorted(orient, key=lambda q: orient[q]["local_time"])
    photos = []
    for q in stems:
        tq = (datetime.fromisoformat(orient[q]["local_time"]) - T_REF).total_seconds() / 86400
        sf = math.exp(ls[slot[q]]) if q in slot else 1.0
        mine = [i for i, d in enumerate(dots) if d["photo"] == q]
        pr = []
        for k, fb in enumerate(B):
            w = 2 * np.pi * fb[0]
            Xp = fb[1] * math.sin(w * tq) + fb[2] * math.cos(w * tq)
            th = w * tq + math.atan2(fb[2], fb[1])
            Cv = np.array(bodies[k]["cov_f_a_b"])
            jac = np.array([2 * np.pi * tq * (fb[1] * math.cos(w * tq) - fb[2] * math.sin(w * tq)), math.sin(w * tq), math.cos(w * tq)])
            pr.append({"X": round(Xp, 3), "Y": round(bodies[k]["tilt"]["B_rj"] * math.cos(th) + bodies[k]["tilt"]["C_rj"], 3),
                       "err": round(float(math.sqrt(max(jac @ Cv @ jac, 0))), 3), "hidden": abs(Xp) < P.HIDE})
        photos.append({"id": q, "t": round(tq, 5), "time": orient[q]["local_time"], "night": orient[q]["night"],
                       "scale_fix": round(sf, 4), "own_scale": q in slot,
                       "rj_px": float(scale[q]["rj_px"]), "angle_deg": float(orient[q]["final_plusX_deg"]),
                       "dots": [{"X": round(float(Xc[i]), 3), "Y": round(float(Yc[i]), 3), "bodies": assign[i],
                                 "resid": round(float(Xc[i] - pred[i, assign[i][0]]), 3) if assign[i] else None} for i in mine],
                       "pred": pr})

    summary = {"n_dots": len(dots), "assigned": sum(1 for a in assign if a), "shared": sum(1 for a in assign if len(a) > 1),
               "none": sum(1 for a in assign if not a), "photos_with_own_scale": len(free),
               "scale_fix_rms": scale_sd, "scale_fix_typical": scale_mad, "resid_rms_rj": float(np.sqrt(np.mean(res ** 2))),
               "resid_robust_rj": float(1.4826 * np.median(np.abs(res))), "reduced_chi2": chi2,
               "bootstrap_refits": int(len(boot)),
               "mean_tilt_deg": float(np.mean([b["tilt_deg"] for b in bodies]))}
    for b in bodies:
        b.pop("cov_f_a_b", None)
    OUT.mkdir(parents=True, exist_ok=True)
    model = {"t_ref": T_REF.isoformat(), "bodies": bodies, "summary": summary, "photos": photos,
             "strip": {"half_x_rj": STRIP_HALF_X, "half_y_rj": STRIP_HALF_Y, "px_per_rj": STRIP_PX_PER_RJ}}
    (OUT / "model.json").write_text(json.dumps(model, ensure_ascii=False, indent=1))
    (DEMO / "model_data.json").write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")))

    (DEMO / "final").mkdir(exist_ok=True)
    for ph in photos:
        q = ph["id"]
        strip_image(recs[q], det[q]["jupiter"], ph["rj_px"], ph["angle_deg"], ph["scale_fix"], STRIP_PX_PER_RJ).save(
            DEMO / "final" / f"{q}.jpg", quality=80)
    sheet(photos, recs, det, scale, orient, bodies, OUT / "annotated.jpg")
    model_plot(bodies, OUT / "model.png")
    print("model:", OUT / "model.json", "| page data:", DEMO / "model_data.json", f"| {len(photos)} strips in demo/final/", file=sys.stderr)


if __name__ == "__main__":
    main()
