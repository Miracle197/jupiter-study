"""Science results from the calibrated moon positions.

1. Orbit fits: X(t) = a * sin(2*pi*(t - t0)/P) for each moon, using the
   self-calibrated positions (Jupiter disk = ruler). Period from a periodogram
   search, then least-squares refinement.
2. Kepler's third law: slope of log a vs log P (scale free) and Jupiter's mass
   M = 4 pi^2 a^3 / (G P^2), with and without the glare (bloom) correction.
3. Inclination: angle of each moon from the moon line, and angles between
   pairs of moons in the same photo, compared with the ephemeris.
4. Time check: shift all photo times by dt and find the dt that best matches
   the ephemeris (tests the PST assumption and the file-name times).
5. Orientation: image angle of the moon line vs. the predicted tilt of
   Jupiter's equator to the horizon at the observing site.

Output: data/results.json, web/data.json
"""
import csv
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import curve_fit

ROOT = Path(__file__).resolve().parent.parent
MOONS = ["Io", "Europa", "Ganymede", "Callisto"]
RJ_KM = 71492.0
G = 6.67430e-11
M_JUP_TRUE = 1.89813e27
TRUE = {"Io": (1.769138, 5.905), "Europa": (3.551181, 9.397),
        "Ganymede": (7.154553, 14.99), "Callisto": (16.689018, 26.37)}  # P [d], a [Rj]


def sine(t, a, P, t0):
    return a * np.sin(2 * np.pi * (t - t0) / P)


def periodogram(t, x, w, periods):
    best = (np.inf, None)
    chi = []
    for P in periods:
        A = np.stack([np.sin(2 * np.pi * t / P), np.cos(2 * np.pi * t / P)], 1)
        coef, *_ = np.linalg.lstsq(A * w[:, None], x * w, rcond=None)
        c2 = float(np.sum(w ** 2 * (x - A @ coef) ** 2))
        chi.append(c2)
        if c2 < best[0]:
            best = (c2, (P, coef))
    return best[1], np.array(chi)


def fit_orbit(t, x, w, guess_P):
    span = t.max() - t.min()
    lo, hi = 0.6 * guess_P, 1.6 * guess_P
    periods = 1 / np.linspace(1 / hi, 1 / lo, int(40 * span / lo) + 200)
    (P, (cs, cc)), chi = periodogram(t, x, w, periods)
    a0 = float(np.hypot(cs, cc))
    t00 = float(-np.arctan2(cc, cs) * P / (2 * np.pi))
    p, cov = curve_fit(sine, t, x, p0=[a0, P, t00], sigma=1 / w, absolute_sigma=False, maxfev=20000)
    if p[0] < 0:
        p[0], p[2] = -p[0], p[2] + p[1] / 2
    err = np.sqrt(np.diag(cov))
    res = x - sine(t, *p)
    return {"a": float(p[0]), "a_err": float(err[0]), "P": float(p[1]), "P_err": float(err[1]),
            "t0": float(p[2]), "rms": float(np.sqrt(np.mean(res ** 2))), "n": int(len(t)),
            "periodogram": {"P": periods.round(5).tolist(), "chi2": np.round(chi / chi.max(), 5).tolist()}}


def _night_ids(jd):
    return np.floor(np.asarray(jd) - 8 / 24).astype(int)  # local (PST) noon-to-noon


def field_rotation(fits, ephp, site):
    from astropy.coordinates import get_body
    from astropy.time import Time
    ks = sorted([k for k in fits if fits[k]["n_matched"] >= 1], key=lambda k: ephp[k]["jd"])
    jd = np.array([ephp[k]["jd"] for k in ks])
    L = np.radians([fits[k]["line_angle_deg"] for k in ks])
    night = _night_ids(jd)
    t = Time(jd, format="jd")
    b = get_body("jupiter", t)
    ra, dec = b.ra.rad, b.dec.rad
    gmst = t.sidereal_time("mean", "greenwich").rad
    keep = np.array([np.sum(night == n) >= 3 for n in night])

    def model(lat, lon):
        phi = np.radians(lat)
        H = gmst + np.radians(lon) - ra
        q = np.arctan2(np.sin(H), np.tan(phi) * np.cos(dec) - np.sin(dec) * np.cos(H))
        alt = np.arcsin(np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(H))
        return q + alt

    def cost(lat, lon, detail=False):
        r = L + model(lat, lon)
        tot, n, per = 0.0, 0, {}
        for nn in np.unique(night[keep]):
            sel = night == nn
            z = np.exp(1j * r[sel])
            c = np.angle(z.mean())
            d = np.angle(z * np.exp(-1j * c))
            tot += float(np.sum(np.minimum(d ** 2, np.radians(15) ** 2)))
            n += int(sel.sum())
            per[int(nn)] = c
        rms = float(np.degrees(np.sqrt(tot / n)))
        return (rms, per) if detail else rms

    lats = np.arange(10, 61, 1.0)
    lons = np.arange(-135, -64, 1.0)
    C = np.array([[cost(a, o) for o in lons] for a in lats])
    i, j = np.unravel_index(C.argmin(), C.shape)
    rms_site, per = cost(site["lat_deg"], site["lon_deg"], detail=True)
    rot = model(site["lat_deg"], site["lon_deg"])
    nights = []
    for nn in np.unique(night[keep]):
        sel = np.where(night == nn)[0]
        # predicted image angle = offset - (q + alt); unwrap observed around it
        pred = per[int(nn)] - rot[sel]
        obs = pred + np.angle(np.exp(1j * (L[sel] - pred)))
        base = pred[0]
        nights.append({"night": ks[sel[0]][:10], "photos": [ks[k] for k in sel],
                       "t": (jd[sel] - jd[sel][0]).round(5).tolist(),
                       "pred_deg": np.degrees(pred - base).round(2).tolist(),
                       "obs_deg": np.degrees(obs - base).round(2).tolist()})
    ok = C < C.min() + 1.0  # within 1 degree of the best rms
    return {"site_rms_deg": rms_site, "best_lat": float(lats[i]), "best_lon": float(lons[j]),
            "best_rms_deg": float(C[i, j]),
            "lat_range": [float(lats[ok.any(1)].min()), float(lats[ok.any(1)].max())],
            "lon_range": [float(lons[ok.any(0)].min()), float(lons[ok.any(0)].max())],
            "lat_profile": {"lat": lats.tolist(), "rms": C[:, j].round(3).tolist()},
            "lon_profile": {"lon": lons.tolist(), "rms": C[i, :].round(3).tolist()},
            "nights": nights, "n_photos": int(keep.sum())}


def main():
    rows = [r for r in csv.DictReader(open(ROOT / "data" / "positions.csv")) if r["excluded"] != "True"]
    for r in rows:
        for k in ("jd", "px", "py", "X_self", "Y_self", "X_fit", "Y_fit", "X_eph", "Y_eph", "D_eph", "resid_fit"):
            r[k] = float(r[k])
    fits = json.load(open(ROOT / "data" / "photo_fits.json"))
    eph = json.load(open(ROOT / "data" / "ephemeris_photos.json"))
    hourly = json.load(open(ROOT / "data" / "ephemeris_hourly.json"))
    jd0 = min(r["jd"] for r in rows)
    out = {"jd0": jd0, "n_points": len(rows), "orbits": {}}

    # weight: drop the worst-seeing photos (low altitude -> more blur)
    def weight(r):
        am = fits[r["photo"]]["airmass"] or 10
        return 1 / np.sqrt(am)

    # 1-2. orbit fits and Kepler
    bloom = np.median([f["bloom"] for f in fits.values() if f["n_matched"] >= 2])
    for m in MOONS:
        rs = [r for r in rows if r["moon"] == m]
        if len(rs) < 5:
            continue
        t = np.array([r["jd"] - jd0 for r in rs])
        x = np.array([r["X_self"] for r in rs])
        w = np.array([weight(r) for r in rs])
        f = fit_orbit(t, x, w, TRUE[m][0])
        f["a_corrected"] = f["a"] * bloom
        f["true_P"], f["true_a"] = TRUE[m]
        # Y amplitude (projected orbit ellipse) with the same phase: Y = b*cos(...)
        y = np.array([r["Y_fit"] for r in rs])
        c = np.cos(2 * np.pi * (t - f["t0"]) / f["P"])
        b = float(np.sum(w ** 2 * c * y) / np.sum(w ** 2 * c * c))
        f["b"] = b
        # Same projection measured on the ephemeris itself (hourly samples):
        # depth sign (prograde motion: which half of the orbit is in front) and
        # the true minor axis b of the projected orbit ellipse.
        th_ = np.arange(hourly["n"]) / 24 + hourly["jd0"] - jd0
        Xe, Ye, De = (np.array(hourly["moons"][m][k]) for k in ("X", "Y", "D"))
        fe = fit_orbit(th_, Xe, np.ones_like(th_), TRUE[m][0])
        ce = np.cos(2 * np.pi * (th_ - fe["t0"]) / fe["P"])
        f["depth_sign"] = int(np.sign(np.sum(De * ce)))
        f["b_eph"] = float(np.sum(Ye * ce) / np.sum(ce * ce))
        f["a_eph"] = fe["a"]
        out["orbits"][m] = f
    bloom_spread = np.percentile([f["bloom"] for f in fits.values() if f["n_matched"] >= 2], [16, 84])
    out["bloom_median"] = float(bloom)
    out["bloom_16_84"] = bloom_spread.tolist()

    P = np.array([out["orbits"][m]["P"] for m in out["orbits"]])
    a = np.array([out["orbits"][m]["a"] for m in out["orbits"]])
    slope, icpt = np.polyfit(np.log(P), np.log(a), 1)
    out["kepler_slope"] = float(slope)  # expected 2/3
    masses = {}
    for m, o in out["orbits"].items():
        for key, aa in (("raw", o["a"]), ("corrected", o["a_corrected"])):
            Mj = 4 * np.pi ** 2 * (aa * RJ_KM * 1e3) ** 3 / (G * (o["P"] * 86400) ** 2)
            masses.setdefault(key, {})[m] = float(Mj)
    out["jupiter_mass"] = {k: {"per_moon": v, "median": float(np.median(list(v.values())))} for k, v in masses.items()}
    out["jupiter_mass_true"] = M_JUP_TRUE

    # 3. inclination / coplanarity
    by_photo = {}
    for r in rows:
        by_photo.setdefault(r["photo"], []).append(r)
    single, pairs = [], []
    for ph, rs in by_photo.items():
        for r in rs:
            if abs(r["X_fit"]) > 3:
                single.append({"photo": ph, "moon": r["moon"],
                               "obs_deg": float(np.degrees(np.arctan2(r["Y_fit"], abs(r["X_fit"])))),
                               "eph_deg": float(np.degrees(np.arctan2(r["Y_eph"], abs(r["X_eph"]))))})
        for i in range(len(rs)):
            for k in range(i + 1, len(rs)):
                ri, rk = rs[i], rs[k]
                if min(abs(ri["X_self"]), abs(rk["X_self"])) < 3:
                    continue
                ang = lambda X, Y: np.degrees(np.arctan2(Y, abs(X)))
                pairs.append({"photo": ph, "pair": f"{ri['moon']}-{rk['moon']}",
                              "obs_deg": float(ang(ri["X_self"], ri["Y_self"]) - ang(rk["X_self"], rk["Y_self"])),
                              "eph_deg": float(ang(ri["X_eph"], ri["Y_eph"]) - ang(rk["X_eph"], rk["Y_eph"]))})
    diff = np.array([p["obs_deg"] - p["eph_deg"] for p in pairs])
    out["inclination"] = {
        "single": single, "pairs": pairs,
        "pair_obs_abs_median_deg": float(np.median(np.abs([p["obs_deg"] for p in pairs]))) if pairs else None,
        "pair_eph_abs_median_deg": float(np.median(np.abs([p["eph_deg"] for p in pairs]))) if pairs else None,
        "pair_obs_minus_eph_std_deg": float(diff.std()) if len(diff) else None,
    }

    # 4. time-offset scan using the hourly ephemeris
    th = np.arange(hourly["n"]) / 24 + hourly["jd0"]
    spl = {m: (CubicSpline(th, hourly["moons"][m]["X"]), CubicSpline(th, hourly["moons"][m]["Y"])) for m in MOONS}
    dts = np.arange(-180, 181, 5)
    cost = []
    for dt in dts:
        tot, n = 0.0, 0
        for ph, rs in by_photo.items():
            if len(rs) < 2:
                continue
            f = fits[ph]
            Pm = np.array([[spl[r["moon"]][0](r["jd"] + dt / 1440), f["flip"] * spl[r["moon"]][1](r["jd"] + dt / 1440)] for r in rs])
            C = np.array([[r["px"] - f["jx"], -(r["py"] - f["jy"])] for r in rs]) / f["jr"]
            zp, zc = Pm[:, 0] + 1j * Pm[:, 1], C[:, 0] + 1j * C[:, 1]
            k = (np.conj(zp) @ zc) / (np.conj(zp) @ zp)
            res = zc - k * zp
            tot += float(np.sum(np.abs(res) ** 2) / abs(k) ** 2)
            n += len(rs)
        cost.append(np.sqrt(tot / n))
    cost = np.array(cost)
    out["time_scan"] = {"dt_min": dts.tolist(), "rms_rj": cost.round(4).tolist(),
                        "best_dt_min": int(dts[cost.argmin()])}

    # 5. field rotation: with an alt-az mount and a star diagonal the image turns
    # by -(parallactic angle + altitude) as Jupiter crosses the sky. Compare the
    # photo's moon-line angle with that model at the site, and scan lat/lon to see
    # which site the photos themselves prefer.
    out["field_rotation"] = field_rotation(fits, eph["photos"], eph["site"])

    json.dump(out, open(ROOT / "data" / "results.json", "w"), indent=1)
    for m, o in out["orbits"].items():
        print(f"{m:9s} n={o['n']:2d} P={o['P']:.3f}±{o['P_err']:.3f} d (true {o['true_P']:.3f})  "
              f"a={o['a']:.2f}±{o['a_err']:.2f} Rj -> corrected {o['a_corrected']:.2f} (true {o['true_a']:.2f})  "
              f"rms={o['rms']:.2f}  b={o['b']:+.2f} (eph {o['b_eph']:+.2f}) depth_sign={o['depth_sign']:+d}")
    print(f"bloom median {bloom:.3f} (16-84%: {bloom_spread.round(3)})")
    print(f"Kepler slope log a / log P = {slope:.3f} (expected 0.667)")
    for k, v in out["jupiter_mass"].items():
        print(f"Jupiter mass ({k}): {v['median']:.3e} kg  (true {M_JUP_TRUE:.3e})")
    inc = out["inclination"]
    print(f"inclination pairs: n={len(pairs)} |obs| median {inc['pair_obs_abs_median_deg']}, "
          f"|eph| median {inc['pair_eph_abs_median_deg']}, obs-eph std {inc['pair_obs_minus_eph_std_deg']}")
    print(f"time scan best offset: {out['time_scan']['best_dt_min']} min")
    fr = out["field_rotation"]
    print(f"field rotation: rms at site {fr['site_rms_deg']:.1f} deg; best site lat {fr['best_lat']:.0f} lon {fr['best_lon']:.0f} "
          f"(rms {fr['best_rms_deg']:.1f}); lat range {fr['lat_range']} lon range {fr['lon_range']}")

    build_web(rows, fits, eph, hourly, out, jd0)


def build_web(rows, fits, eph, hourly, res, jd0):
    photos = []
    for ph, f in fits.items():
        e = eph["photos"][ph]
        th, s, flip = np.radians(f["theta_deg"]), f["scale_fit_px_per_rj"], f["flip"]
        pred = {}
        for m in MOONS:
            X, Y = e["moons"][m]["X"], flip * e["moons"][m]["Y"]
            px = f["jx"] + s * (X * np.cos(th) - Y * np.sin(th))
            py = f["jy"] - s * (X * np.sin(th) + Y * np.cos(th))
            pred[m] = {"px": round(float(px), 1), "py": round(float(py), 1), "X": round(X, 3),
                       "Y": round(e["moons"][m]["Y"], 3), "D": round(e["moons"][m]["D"], 3),
                       "status": e["moons"][m]["status"]}
        obs = {r["moon"]: {"px": float(r["px"]), "py": float(r["py"]), "X": r["X_self"], "Y": r["Y_self"],
                           "Xf": r["X_fit"], "Yf": r["Y_fit"], "resid": r["resid_fit"], "source": r["source"]}
               for r in rows if r["photo"] == ph}
        photos.append({"id": ph, "img": f"img/{ph}.jpg", "w": f["w"], "h": f["h"], "local": f["local_time"],
                       "t": round(e["jd"] - jd0, 5), "jd": e["jd"], "jx": f["jx"], "jy": f["jy"], "jr": f["jr"],
                       "scale": round(s, 2), "theta": round(f["theta_deg"], 2), "flip": flip,
                       "alt": round(e["alt_deg"], 1), "az": round(e["az_deg"], 1),
                       "airmass": e["airmass"] and round(e["airmass"], 2),
                       "tilt": round(f["equator_tilt_vs_horizon_deg"], 1), "excluded": f["excluded"],
                       "rms": f["rms_resid_rj"] and round(f["rms_resid_rj"], 3), "bloom": round(f["bloom"], 3),
                       "pred": pred, "obs": obs})
    photos.sort(key=lambda p: p["jd"])
    orbits = {m: {k: v for k, v in o.items() if k != "periodogram"} for m, o in res["orbits"].items()}
    data = {"jd0": jd0, "site": eph["site"], "photos": photos, "orbits": orbits,
            "periodograms": {m: o["periodogram"] for m, o in res["orbits"].items()},
            "hourly": {"t0": hourly["jd0"] - jd0, "step_h": 1, "n": hourly["n"], "moons": hourly["moons"]},
            "kepler_slope": res["kepler_slope"], "jupiter_mass": res["jupiter_mass"],
            "jupiter_mass_true": res["jupiter_mass_true"], "bloom_median": res["bloom_median"],
            "inclination": res["inclination"], "time_scan": res["time_scan"], "field_rotation": res["field_rotation"],
            "bloom_16_84": res["bloom_16_84"], "n_points": res["n_points"]}
    gal = ROOT / "data" / "galileo.json"   # written by 07_galileo.py (run it before this script)
    if gal.exists():
        data["galileo"] = json.load(open(gal))
    json.dump(data, open(ROOT / "web" / "data.json", "w"), separators=(",", ":"))
    print("web/data.json written,", round((ROOT / "web" / "data.json").stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
