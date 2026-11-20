"""Last: how good is it? The photo-only results compared with NASA's.

This is the only script that reads NASA data. Steps 1-5 never do.

NASA data: data/nasa/ephemeris_*.json, light-time corrected positions of the
four moons relative to Jupiter as seen from the observing site, from the JPL
Horizons system (downloaded for the earlier version of this project, see
data/nasa/README.md). Units: Jupiter equatorial radii (71,492 km).
  X  along Jupiter's equator on the sky, + toward celestial east
  Y  along Jupiter's projected spin axis, + toward Jupiter's north
  D  depth, + farther than Jupiter (behind it)
The hourly series is interpolated (cubic) to the camera times used by the
project; the per-photo file used the file-name time for one photo
(2024-01-10, file 18:11, camera 20:11).

What is compared:
  - which NASA moon each body is, and whether every dot was given to the right one
  - the unit: the photos' "1 Rj" (the overexposed edge) against Jupiter's true radius
  - which way +X and +Y point on the sky, whether the image is mirrored,
    and which half of each orbit is in front of Jupiter
  - every dot's position, with step 1's scale and with step 5's per-photo scale
  - the periods: against NASA's positions fitted the same way over the same
    40 days (as seen from the Earth), and against the true orbital periods
  - the tilt of the orbits
  - step 3's findings: when Jupiter was highest, its declination, its daily drift,
    and the camera clock of the 2024-01-10 photo
  - moons that NASA puts in plain view where no dot was found

Output: output/check/nasa.json, output/check/nasa.png, demo/nasa_data.json
"""
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "check"
NASA = ROOT / "data" / "nasa"
JD_T0 = 2460281.5 + 8 / 24            # 2023-12-03 00:00 PST = the project's t = 0
MOONS = ["Io", "Europa", "Ganymede", "Callisto"]
SIDEREAL_D = {"Io": 1.769137786, "Europa": 3.551181041, "Ganymede": 7.15455296, "Callisto": 16.6890184}  # NASA/JPL
FLAT = 66854.0 / 71492.0              # Jupiter's polar / equatorial radius
LAT = math.radians(json.load(open(ROOT / "data/observer.json"))["lat_deg"])


def nasa_series():
    h = json.load(open(NASA / "ephemeris_hourly.json"))
    jd = h["jd0"] + np.arange(h["n"]) * h["step_h"] / 24
    t = jd - JD_T0
    spl = {m: {c: CubicSpline(t, h["moons"][m][c]) for c in "XYD"} for m in MOONS}
    return t, spl


def at(spl, m, t):
    return {c: float(spl[m][c](t)) for c in "XYD"}


def status(p):
    """visible / occulted (behind Jupiter) / transit (in front of the disk); eclipses are not worked out here."""
    inside = math.hypot(p["X"], p["Y"] / FLAT) < 1
    return "occulted" if inside and p["D"] > 0 else "transit" if inside else "visible"


def sine_fit(t, x, f0, span=0.004):
    """Best X = a sin(2 pi f t) + b cos(2 pi f t) near f0 (the same model as steps 4-5); f, amplitude, phase, f error."""
    best = None
    for f in np.linspace(f0 - span, f0 + span, 801):
        A = np.c_[np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)]
        ab, *_ = np.linalg.lstsq(A, x, rcond=None)
        r = float(np.sum((A @ ab - x) ** 2))
        if best is None or r < best[0]:
            best = (r, f, ab)
    r, f, (a, b) = best
    sol = least_squares(lambda p: p[1] * np.sin(2 * np.pi * p[0] * t) + p[2] * np.cos(2 * np.pi * p[0] * t) - x, [f, a, b])
    f, a, b = sol.x
    return {"f": float(f), "P": float(1 / f), "A": float(math.hypot(a, b)), "phase": float(math.atan2(b, a)), "a": float(a), "b": float(b)}


def transit_from_altaz(alt, az, local_hour):
    """Declination and the local time Jupiter was highest, from its altitude and azimuth (azimuth from north)."""
    a, A = math.radians(alt), math.radians(az)
    dec = math.asin(math.sin(LAT) * math.sin(a) + math.cos(LAT) * math.cos(a) * math.cos(A))
    H = math.atan2(-math.sin(A) * math.cos(a), math.cos(LAT) * math.sin(a) - math.sin(LAT) * math.cos(a) * math.cos(A))
    return math.degrees(dec), local_hour - math.degrees(H) / 15 * 0.99727     # hour angle (west +) in sidereal hours -> clock hours


def main():
    model = json.load(open(ROOT / "output/step5/model.json"))
    B, photos = model["bodies"], model["photos"]
    tgrid, spl = nasa_series()
    sky = json.load(open(ROOT / "output/step2/summary.json"))["method_B_turning_sky"]
    orient = {r["photo"]: r for r in csv.DictReader(open(ROOT / "output/step2/orientation.csv"))}
    per_photo = json.load(open(NASA / "ephemeris_photos.json"))["photos"]

    # every dot with its label, its step 5 position, its step 1 position, and NASA's four moons at that moment
    rows = []
    for p in photos:
        nasa = {m: at(spl, m, p["t"]) for m in MOONS}
        for d in p["dots"]:
            rows.append({"photo": p["id"], "t": p["t"], "X": d["X"], "Y": d["Y"], "X1": d["X"] * p["scale_fix"], "Y1": d["Y"] * p["scale_fix"],
                         "bodies": d["bodies"], "nasa": nasa})

    # 1. which NASA moon is each body, which way +X points, and the unit: fit X_ours = c * s * X_nasa
    single = [r for r in rows if len(r["bodies"]) == 1]
    best = None
    import itertools
    for perm in itertools.permutations(range(4)):
        for sx in (1, -1):
            xo = np.array([r["X"] for r in single]); xn = np.array([sx * r["nasa"][MOONS[perm[r["bodies"][0]]]]["X"] for r in single])
            c = float(np.sum(xo * xn) / np.sum(xn * xn))
            rms = float(np.sqrt(np.mean((xo - c * xn) ** 2)))
            if best is None or rms < best[0]:
                best = (rms, perm, sx, c)
    _, perm, sx, _ = best
    name = {k: MOONS[perm[k]] for k in range(4)}
    # unit c from all single dots, robustly (a few dots near Jupiter's glare are least reliable)
    xo = np.array([r["X"] for r in single]); xn = np.array([sx * r["nasa"][name[r["bodies"][0]]]["X"] for r in single])
    c = float(np.sum(xo * xn) / np.sum(xn * xn))
    for _ in range(3):
        res = xo - c * xn; keep = np.abs(res) < 4 * 1.4826 * np.median(np.abs(res))
        c = float(np.sum(xo[keep] * xn[keep]) / np.sum(xn[keep] ** 2))
    # Y: same unit; which way +Y points
    yo = np.array([r["Y"] for r in single]); yn = np.array([r["nasa"][name[r["bodies"][0]]]["Y"] for r in single])
    sy = 1 if np.sum(yo * yn) > 0 else -1
    mirrored = sx * sy > 0          # unmirrored: (right, up) = rotation of (west, north), so +X east goes with +Y south

    # 2. positions: every dot against NASA, with step 1's scale and with step 5's
    def resid(key_x, key_y):
        out = []
        for r in rows:
            if not r["bodies"]:
                continue
            m = name[r["bodies"][0]]
            out.append((r[key_x] / c - sx * r["nasa"][m]["X"], r[key_y] / c - sy * r["nasa"][m]["Y"]))
        return np.array(out)
    r5, r1 = resid("X", "Y"), resid("X1", "Y1")
    per_body = {}
    for k in range(4):
        idx = [i for i, r in enumerate([q for q in rows if q["bodies"]]) if r["bodies"][0] == k]
        per_body[B[k]["name"]] = {"rms_x_true_rj": float(np.sqrt(np.mean(r5[idx, 0] ** 2))), "n": len(idx)}

    # 3. was every dot given to the right moon? nearest NASA moon in (X, Y), in the photos' unit and orientation
    wrong, checked = [], 0
    for r in rows:
        if not r["bodies"]:
            continue
        checked += 1
        d = {m: math.hypot(r["X"] - c * sx * r["nasa"][m]["X"], (r["Y"] - c * sy * r["nasa"][m]["Y"]) * 0.5) for m in MOONS}
        near = min(d, key=d.get)
        mine = {name[k] for k in r["bodies"]}
        if near not in mine:
            wrong.append({"photo": r["photo"], "X": round(r["X"], 2), "ours": "+".join(B[k]["name"] for k in r["bodies"]), "nasa": near,
                          "dist_rj": round(d[near], 2)})
    # shared dots: were both bodies really close together?
    shared = []
    for r in rows:
        if len(r["bodies"]) == 2:
            m1, m2 = (name[k] for k in r["bodies"])
            shared.append(abs(r["nasa"][m1]["X"] - r["nasa"][m2]["X"]) * c)
    # moons NASA puts in plain view with no dot nearby (outside the glare, inside the frame)
    import step4_fold
    view = step4_fold._view()
    missed = []
    for p in photos:
        (lo, hi), _ = view[p["id"]]
        for m in MOONS:
            q = at(spl, m, p["t"])
            Xp = c * sx * q["X"]
            if status(q) != "visible" or abs(Xp) < 2.0 or not (lo < Xp < hi):
                continue
            if not any(abs(d["X"] - Xp) < 1.0 for d in p["dots"]):
                missed.append({"photo": p["id"], "moon": m, "X": round(Xp, 2)})
    hidden_dots = []
    for r in rows:
        for k in r["bodies"]:
            if status(r["nasa"][name[k]]) != "visible":
                hidden_dots.append({"photo": r["photo"], "moon": name[k], "status": status(r["nasa"][name[k]])})

    # 4. periods: NASA's positions fitted the same way at the same moments, and the true orbital periods
    periods = []
    for k, b in enumerate(B):
        m = name[k]
        ts = np.array([r["t"] for r in rows if k in r["bodies"]])
        xn = np.array([sx * c * r["nasa"][m]["X"] for r in rows if k in r["bodies"]])
        same = sine_fit(ts, xn, b["freq"])
        tt = np.linspace(min(r["t"] for r in rows), max(r["t"] for r in rows), 2000)
        span = sine_fit(tt, np.array([sx * c * spl[m]["X"](u) for u in tt]), b["freq"])
        periods.append({"body": b["name"], "moon": m, "ours": b["period_d"], "err": b["period_err_d"],
                        "nasa_same_moments": same["P"], "nasa_whole_span": span["P"], "nasa_orbit": SIDEREAL_D[m],
                        "sigma_vs_same": (b["period_d"] - same["P"]) / b["period_err_d"],
                        "sigma_vs_orbit": (b["period_d"] - SIDEREAL_D[m]) / b["period_err_d"],
                        "reach_ours": b["reach_rj"], "reach_ours_err": b["reach_err_rj"], "reach_nasa_true_rj": span["A"] / c,
                        "unit_ratio": b["reach_rj"] / (span["A"] / c)})

    # 5. tilt: NASA's Y swing on the same phase, against the photos'
    tilts = []
    for k, b in enumerate(B):
        m = name[k]
        tt = np.linspace(0, 40, 4000)
        th = 2 * np.pi * b["freq"] * tt + b["phase_rad"]
        yn = np.array([sy * c * spl[m]["Y"](u) for u in tt])
        M = np.c_[np.cos(th), np.sin(th), np.ones_like(th)]
        coef, *_ = np.linalg.lstsq(M, yn, rcond=None)
        A_true = periods[k]["reach_nasa_true_rj"] * c
        tilts.append({"body": b["name"], "moon": m, "ours_deg": b["tilt_deg"], "ours_err_deg": b["tilt_err_deg"],
                      "nasa_deg": math.degrees(math.asin(max(-1, min(1, coef[0] / A_true)))),
                      "sub_earth_lat_deg": float(np.mean([v["sub_obs_lat_deg"] for v in per_photo.values()]))})

    # 5b. the same tilt, with every photo turned by method B of step 3 alone (gravity sensor + turning sky,
    #     no dots): turning by the dots' own line absorbs part of an outer body's drift across the line
    for k, b in enumerate(B):
        th, yb, w = [], [], []
        for p in photos:
            o = orient[p["id"]]
            if not o["B_plusX_deg"]:
                continue
            dang = math.radians(((float(o["final_plusX_deg"]) - float(o["B_plusX_deg"]) + 180) % 360) - 180)
            for d in p["dots"]:
                if d["bodies"] == [k]:
                    z = complex(d["X"], d["Y"]) * complex(math.cos(dang), math.sin(dang))
                    th.append(2 * math.pi * b["freq"] * p["t"] + b["phase_rad"]); yb.append(z.imag)
                    w.append(1 / (0.15 ** 2 + (abs(d["X"]) * math.radians(float(o["B_err_deg"]))) ** 2))
        th, yb, w = np.array(th), np.array(yb), np.array(w)
        M = np.c_[np.cos(th), np.ones_like(th)]
        cf, *_ = np.linalg.lstsq(M * np.sqrt(w)[:, None], yb * np.sqrt(w), rcond=None)
        rr = yb - M @ cf
        cov = np.linalg.inv((M * w[:, None]).T @ M) * np.sum(w * rr ** 2) / max(len(yb) - 2, 1)
        tilts[k]["gravity_sky_deg"] = math.degrees(math.asin(cf[0] / b["reach_rj"]))
        tilts[k]["gravity_sky_err_deg"] = math.degrees(math.sqrt(cov[0, 0]) / b["reach_rj"])

    # 6. front and back: in the step 5 model (depth +1), a body moving toward +X is in front of Jupiter.
    #    NASA: D < 0 is in front. Correlate the model's "toward the Earth" with NASA's -D.
    front = []
    for k, b in enumerate(B):
        m = name[k]
        tt = np.linspace(0, 40, 2000)
        th = 2 * np.pi * b["freq"] * tt + b["phase_rad"]
        toward = np.cos(th)
        nd = -np.array([spl[m]["D"](u) for u in tt])
        front.append(float(np.corrcoef(toward, nd)[0, 1]))
    depth_sign = 1 if np.mean(front) > 0 else -1

    # 7. step 3's findings: Jupiter's highest time, declination, daily drift (from NASA's altitude and azimuth)
    tr = []
    for s, v in per_photo.items():
        hh, mm = map(int, v["local_time"][11:16].split(":"))
        dec, hi = transit_from_altaz(v["alt_deg"], v["az_deg"], hh + mm / 60)
        day = (np.datetime64(v["local_time"][:10]) - np.datetime64("2023-12-03")).astype(int)
        if hh < 12:
            day -= 1; hi += 24
        tr.append((int(day), hi, dec))
    days = np.array([d for d, _, _ in tr]); his = np.array([h for _, h, _ in tr]); decs = np.array([x for _, _, x in tr])
    slope, icpt = np.polyfit(days, his, 1)
    sky_nasa = {"highest_2023_12_03_local": float(icpt), "declination_deg": float(np.mean(decs[days == 0])),
                "drift_min_per_day_vs_stars": float(slope * 60 + (24 * 60 - 1436.068)),
                "declination_range_deg": [float(decs.min()), float(decs.max())]}
    hh, mm = sky["jupiter_highest_at_on_2023_12_03"].split(":"); hh, mm = int(hh), float(mm)       # e.g. "21:20.6"
    sky_ours = {"highest_2023_12_03_local": hh + mm / 60, "highest_err_min": sky["jupiter_highest_err_min"],
                "declination_deg": sky["jupiter_declination_deg"], "declination_err_deg": sky["jupiter_declination_err_deg"],
                "drift_min_per_day_vs_stars": sky["jupiter_drift_min_per_day"], "drift_err": sky["jupiter_drift_err"]}

    # 8. the 2024-01-10 photo: camera time 20:11 or file name 18:11?
    clock = {}
    p = next(q for q in photos if q["id"] == "2024-01-10T1811")
    for lab, tq in (("camera_20:11", p["t"]), ("file_name_18:11", p["t"] - 2 / 24)):
        nasa = {m: at(spl, m, tq) for m in MOONS}
        rr = [d["X"] - c * sx * nasa[name[d["bodies"][0]]]["X"] for d in p["dots"] if d["bodies"]]
        clock[lab] = float(np.sqrt(np.mean(np.square(rr))))

    # 9. each photo's scale: step 1 alone and after step 5, against NASA (photos with >= 2 bodies)
    sc1, sc5 = [], []
    for q in photos:
        ds = [d for d in q["dots"] if len(d["bodies"]) == 1]
        if len({d["bodies"][0] for d in ds}) < 2:
            continue
        xn = np.array([c * sx * at(spl, name[d["bodies"][0]], q["t"])["X"] for d in ds])
        x5 = np.array([d["X"] for d in ds]); x1 = x5 * q["scale_fix"]
        sc5.append(float(np.sum(x5 * xn) / np.sum(xn * xn))); sc1.append(float(np.sum(x1 * xn) / np.sum(xn * xn)))
    robust = lambda v: float(1.4826 * np.median(np.abs(np.log(v) - np.median(np.log(v)))))

    # residual of every dot against NASA (true Jupiter radii), for the page
    dot_res = [[round(r["t"], 4), r["bodies"][0], round(r["X"] / c - sx * r["nasa"][name[r["bodies"][0]]]["X"], 4)] for r in rows if r["bodies"]]
    # borrowed numbers, for the record: Jupiter's mass from the photos' periods and reaches, once NASA's unit
    # (1 photo Rj = 1/c true radii) and Jupiter's radius are borrowed, with Newton's G
    G, RJ_M = 6.674e-11, 7.1492e7
    masses = [4 * math.pi ** 2 * (b["reach_rj"] / c * RJ_M) ** 3 / (G * (b["period_d"] * 86400) ** 2) for b in B]

    out = {"source": "JPL Horizons (NASA), light-time corrected, observing site of data/observer.json; see data/nasa/README.md",
           "names": {B[k]["name"]: name[k] for k in range(4)},
           "plus_x_is": "east" if sx > 0 else "west", "plus_y_is": "Jupiter north" if sy > 0 else "Jupiter south",
           "mirrored": bool(mirrored), "unit_c": c, "photos_rj_in_true_rj": 1 / c,
           "front": {"model_default_right": depth_sign > 0, "correlations": front},
           "positions": {"rms_x_true_rj_step5": float(np.sqrt(np.mean(r5[:, 0] ** 2))), "median_abs_x_true_rj_step5": float(np.median(np.abs(r5[:, 0]))),
                         "rms_x_true_rj_step1": float(np.sqrt(np.mean(r1[:, 0] ** 2))), "median_abs_x_true_rj_step1": float(np.median(np.abs(r1[:, 0]))),
                         "rms_y_true_rj_step5": float(np.sqrt(np.mean(r5[:, 1] ** 2))), "per_body": per_body,
                         "arcsec_per_true_rj": float(np.mean([v["jupiter_radius_arcsec"] for v in per_photo.values()]))},
           "labels": {"dots_checked": checked, "wrong": wrong, "shared_dots": len(shared), "shared_max_sep_rj": float(max(shared)) if shared else None},
           "missed": missed, "hidden_dots": hidden_dots,
           "periods": periods, "tilts": tilts,
           "sky": {"ours": sky_ours, "nasa": sky_nasa},
           "clock_2024_01_10": clock,
           "photo_scale": {"photos": len(sc5), "step1_scatter": robust(sc1), "step5_scatter": robust(sc5)},
           "dot_residuals_true_rj": dot_res,
           "borrowed_mass_kg": {"per_body": masses, "mean": float(np.mean(masses)), "nasa": 1.8982e27}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nasa.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    # for the page: NASA's moons every 2 hours in the photos' unit and orientation, and at every photo
    tt = np.arange(-0.5, 40.51, 1 / 12)
    curves = {B[k]["name"]: {"X": [round(sx * c * float(spl[name[k]]["X"](u)), 3) for u in tt],
                             "Y": [round(sy * c * float(spl[name[k]]["Y"](u)), 3) for u in tt],
                             "toward": [round(-c * float(spl[name[k]]["D"](u)), 3) for u in tt]} for k in range(4)}
    page = dict(out, curves={"t0": -0.5, "step_d": 1 / 12, "bodies": curves})
    (ROOT / "demo" / "nasa_data.json").write_text(json.dumps(page, ensure_ascii=False, separators=(",", ":")))

    # figure: NASA's curves, the photos' dots, and the residuals
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = ["#c8432f", "#c08313", "#2f8a52", "#2f64c9"]
    fig, ax = plt.subplots(2, 1, figsize=(12, 7.5), gridspec_kw={"height_ratios": [2.2, 1]}, sharex=True)
    for k in range(4):
        ax[0].plot(tt, curves[B[k]["name"]]["X"], color=cols[k], lw=0.8, alpha=0.7, label=f"{B[k]['name']} = {name[k]} (NASA)")
        pts = [(r["t"], r["X"]) for r in rows if r["bodies"] and r["bodies"][0] == k]
        ax[0].plot([a for a, _ in pts], [b_ for _, b_ in pts], "o", ms=3.5, color=cols[k])
    ax[0].set(ylabel="X (photos' Rj)", title=f"NASA's moons (lines, in the photos' unit: 1 Rj = {1 / c:.3f} true Jupiter radii) and the photos' dots (step 5)")
    ax[0].legend(fontsize=8, ncol=4, loc="lower left")
    rr = [(r["t"], r["X"] / c - sx * r["nasa"][name[r["bodies"][0]]]["X"], r["bodies"][0]) for r in rows if r["bodies"]]
    for k in range(4):
        ax[1].plot([a for a, _, kk in rr if kk == k], [b_ for _, b_, kk in rr if kk == k], "o", ms=3, color=cols[k])
    ax[1].axhline(0, color="k", lw=0.6)
    ax[1].set(xlabel="days since 2023-12-03", ylabel="dot - NASA (true Rj)")
    fig.tight_layout(); fig.savefig(OUT / "nasa.png", dpi=110); plt.close(fig)

    print(f"names {out['names']};  +X = {out['plus_x_is']}, +Y = {out['plus_y_is']}, mirrored {mirrored};  1 Rj (photos) = {1 / c:.4f} true Rj", file=sys.stderr)
    print(f"front/back: model default {'right' if depth_sign > 0 else 'reversed'} (correlations {np.round(front, 2)})", file=sys.stderr)
    print(f"positions (true Rj): step 5 rms {out['positions']['rms_x_true_rj_step5']:.3f}, median |d| {out['positions']['median_abs_x_true_rj_step5']:.3f};  "
          f"step 1 rms {out['positions']['rms_x_true_rj_step1']:.3f}, median {out['positions']['median_abs_x_true_rj_step1']:.3f}", file=sys.stderr)
    print(f"labels: {checked} dots checked, {len(wrong)} wrong {wrong[:5]};  missed moons: {len(missed)} {missed[:6]};  dots on hidden moons: {hidden_dots[:4]}", file=sys.stderr)
    for q in periods:
        print(f"  {q['body']:>3} = {q['moon']:<9} P ours {q['ours']:.5f} ± {q['err']:.5f} | NASA same moments {q['nasa_same_moments']:.5f} "
              f"({q['sigma_vs_same']:+.1f} sigma) | NASA whole span {q['nasa_whole_span']:.5f} | true orbit {q['nasa_orbit']:.5f} ({q['sigma_vs_orbit']:+.1f} sigma) "
              f"| reach ours/true {q['unit_ratio']:.3f}", file=sys.stderr)
    for q in tilts:
        print(f"  tilt {q['body']:>3}: ours {q['ours_deg']:+.2f} ± {q['ours_err_deg']:.2f} (turned by gravity + sky only {q['gravity_sky_deg']:+.2f} ± {q['gravity_sky_err_deg']:.2f}), "
              f"NASA {q['nasa_deg']:+.2f} (Earth's jovicentric latitude {q['sub_earth_lat_deg']:.2f})", file=sys.stderr)
    print(f"sky: ours {sky_ours}\n     NASA {sky_nasa}", file=sys.stderr)
    print(f"clock 2024-01-10: {clock};  photo scale scatter vs NASA: step 1 {100 * out['photo_scale']['step1_scatter']:.1f}%, step 5 {100 * out['photo_scale']['step5_scatter']:.1f}% ({len(sc5)} photos)", file=sys.stderr)


if __name__ == "__main__":
    main()
