"""Identify the moons in every photo and convert pixels to Jupiter radii.

1. Identification: the ephemeris pattern (X, Y in Rj) is scaled, rotated and
   optionally mirrored onto the photo around Jupiter's centre; a brute-force
   search finds the transform that lands the most predicted moons on detected
   candidates. Matched candidates get the moon's name; others (stars, ghosts,
   noise) are dropped. Moons hidden behind / in front of Jupiter or inside its
   glare are not expected.
2. Two coordinate sets per moon:
   - "self": independent of the ephemeris scale. Scale = Jupiter disk radius
     in pixels, axis = line fitted through the detected moons. Used for the
     orbit fits and Kepler's law.
   - "fit": the best ephemeris-matched transform. Used for residuals and the
     overlay in the demo.
Manual fixes in data/annotations.json (written by tools/annotate.html) take
priority: {"<photo>": {"exclude": false, "moons": {"Io": [x, y] | null}}}.

Output: data/positions.csv, data/photo_fits.json
"""
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MOONS = ["Io", "Europa", "Ganymede", "Callisto"]
TOL_RJ = 0.6          # match tolerance in Jupiter radii
GLARE = 2.2           # detector ignores candidates within GLARE * disk radius


def load_annotations():
    p = ROOT / "data" / "annotations.json"
    return json.load(open(p)) if p.exists() else {}


def search_transform(pred, cands, jr, flips=(1, -1)):
    """pred: (M,2) Rj; cands: (N,2) px (y up). Returns best (score, s, theta, flip)."""
    if len(pred) == 0 or len(cands) == 0:
        return None
    s_grid = jr * np.exp(np.linspace(np.log(0.6), np.log(1.8), 90))
    th_grid = np.radians(np.arange(0, 360, 0.5))
    best = None
    for flip in flips:
        P = pred * np.array([1, flip])
        rho = np.hypot(P[:, 0], P[:, 1])
        psi = np.arctan2(P[:, 1], P[:, 0])
        for s in s_grid:
            # predicted pixel positions for every rotation: (T, M, 2)
            ang = psi[None, :] + th_grid[:, None]
            px = np.stack([s * rho * np.cos(ang), s * rho * np.sin(ang)], -1)
            d = np.linalg.norm(px[:, :, None, :] - cands[None, None, :, :], axis=-1)  # T,M,N
            dmin = d.min(-1) / (TOL_RJ * s)
            score = np.where(dmin < 1, 1 - dmin ** 2, 0).sum(-1)
            k = int(score.argmax())
            # small preference for unmirrored and for scale near the disk radius
            val = score[k] - 0.02 * (flip < 0) - 0.05 * abs(np.log(s / jr))
            if best is None or val > best[0]:
                best = (val, float(s), float(th_grid[k]), flip, float(score[k]))
    return best


def refine(P, C):
    """Least-squares similarity (scale+rotation, centre fixed) mapping P->C."""
    z_p = P[:, 0] + 1j * P[:, 1]
    z_c = C[:, 0] + 1j * C[:, 1]
    a = (np.conj(z_p) @ z_c) / (np.conj(z_p) @ z_p)
    return float(abs(a)), float(np.angle(a))


def main():
    det = json.load(open(ROOT / "data" / "detections.json"))
    eph = json.load(open(ROOT / "data" / "ephemeris_photos.json"))["photos"]
    ann = load_annotations()
    rows, fits = [], {}
    # The mirror flip is a property of the optics (e.g. a star diagonal), so it
    # is decided once for all photos by a score-weighted vote.
    vote = 0.0
    for stem, d in det.items():
        e, j = eph[stem], d["jupiter"]
        cands = np.array([[c["x"] - j["x"], -(c["y"] - j["y"])] for c in d["candidates"]]).reshape(-1, 2)
        vis = [m for m in MOONS if e["moons"][m]["status"] == "visible"]
        pred = np.array([[e["moons"][m]["X"], e["moons"][m]["Y"]] for m in vis]).reshape(-1, 2)
        sc = [search_transform(pred, cands, j["r"], (f,)) for f in (1, -1)]
        if sc[0] and sc[1]:
            vote += sc[1][4] - sc[0][4]
    global_flip = -1 if vote > 0 else 1
    print(f"global mirror flip: {global_flip:+d} (vote {vote:+.2f})")
    for stem, d in det.items():
        e = eph[stem]
        a = ann.get(stem, {})
        j = d["jupiter"]
        jx, jy, jr = j["x"], j["y"], j["r"]
        cands = np.array([[c["x"] - jx, -(c["y"] - jy)] for c in d["candidates"]]).reshape(-1, 2)
        snr = [c["snr"] for c in d["candidates"]]
        manual = a.get("moons", {})
        expected = [m for m in MOONS if e["moons"][m]["status"] == "visible"]
        pred = np.array([[e["moons"][m]["X"], e["moons"][m]["Y"]] for m in expected]).reshape(-1, 2)
        info = {"jx": jx, "jy": jy, "jr": jr, "w": d["w"], "h": d["h"], "excluded": bool(a.get("exclude")),
                "local_time": e["local_time"], "alt_deg": e["alt_deg"], "airmass": e["airmass"],
                "parallactic_deg": e["parallactic_deg"], "pa_pole_deg": e["pa_pole_deg"]}
        match = {}
        best = search_transform(pred, cands, jr, (global_flip,))
        if best:
            _, s, th, flip, _ = best
            for i, m in enumerate(expected):
                if np.hypot(*pred[i]) * s < GLARE * jr * 0.9:
                    continue  # predicted inside the glare: not measurable
                P = pred[i] * np.array([1, flip])
                px = s * np.array([P[0] * np.cos(th) - P[1] * np.sin(th), P[0] * np.sin(th) + P[1] * np.cos(th)])
                dd = np.linalg.norm(cands - px, axis=1)
                k = int(dd.argmin())
                if dd[k] < TOL_RJ * s and k not in match.values():
                    match[m] = k
        # manual annotations override automatic matches
        pts = {m: (cands[k], snr[k], "auto") for m, k in match.items()}
        for m, xy in manual.items():
            if xy is None:
                pts.pop(m, None)
            else:
                pts[m] = (np.array([xy[0] - jx, -(xy[1] - jy)]), None, "manual")
        flip = global_flip
        if len(pts) >= 1:
            P = np.array([[e["moons"][m]["X"], flip * e["moons"][m]["Y"]] for m in pts])
            C = np.array([v[0] for v in pts.values()])
            s, th = refine(P, C)
        else:
            s, th = (best[1], best[2]) if best else (jr, 0.0)
        # self-calibrated axis: principal direction of moon positions through Jupiter
        C = np.array([v[0] for v in pts.values()]).reshape(-1, 2)
        if len(C):
            sgn = np.sign(C @ np.array([np.cos(th), np.sin(th)]))
            sgn[sgn == 0] = 1
            V = C * sgn[:, None]  # fold moons onto the +X side
            u_ = V.sum(0) / np.linalg.norm(V.sum(0))
            if len(C) >= 2:
                w, vec = np.linalg.eigh(V.T @ V)
                u_ = vec[:, -1] * np.sign(vec[:, -1] @ u_)
            phi = float(np.arctan2(u_[1], u_[0]))
        else:
            phi = th
        resid = []
        for m, (c, sn, src) in pts.items():
            em = e["moons"][m]
            # fit frame (aligned to the ephemeris equator)
            xf = (c[0] * np.cos(th) + c[1] * np.sin(th)) / s
            yf = flip * (-c[0] * np.sin(th) + c[1] * np.cos(th)) / s
            # self frame (disk scale, fitted moon line)
            xs = (c[0] * np.cos(phi) + c[1] * np.sin(phi)) / jr
            ys = flip * (-c[0] * np.sin(phi) + c[1] * np.cos(phi)) / jr
            r = float(np.hypot(xf - em["X"], yf - em["Y"]))
            resid.append(r)
            rows.append({"photo": stem, "local_time": e["local_time"], "jd": e["jd"], "moon": m, "source": src,
                         "snr": sn, "px": round(c[0] + jx, 2), "py": round(-c[1] + jy, 2),
                         "X_self": round(xs, 4), "Y_self": round(ys, 4),
                         "X_fit": round(xf, 4), "Y_fit": round(yf, 4),
                         "X_eph": round(em["X"], 4), "Y_eph": round(em["Y"], 4), "D_eph": round(em["D"], 4),
                         "resid_fit": round(r, 4), "excluded": info["excluded"]})
        # orientation diagnostics: image angle of the equator vs. predicted tilt to the horizon
        tilt_pred = ((e["pa_pole_deg"] - e["parallactic_deg"] + 90) % 180) - 90
        info.update({"scale_fit_px_per_rj": s, "theta_deg": float(np.degrees(th)) % 360, "flip": int(flip),
                     "line_angle_deg": float(np.degrees(phi)) % 360, "bloom": jr / s,
                     "n_matched": len(pts), "n_expected": len(expected),
                     "matched": {m: src for m, (_, _, src) in pts.items()},
                     "rms_resid_rj": float(np.sqrt(np.mean(np.square(resid)))) if resid else None,
                     "equator_tilt_vs_horizon_deg": float(tilt_pred),
                     "status": {m: e["moons"][m]["status"] for m in MOONS}})
        fits[stem] = info
        print(f"{stem}: matched {len(pts)}/{len(expected)} {sorted(pts)} s={s:6.1f}px/Rj disk={jr:5.1f} "
              f"bloom={jr / s:4.2f} flip={flip:+d} rms={info['rms_resid_rj'] if resid else float('nan'):.2f}")
    with open(ROOT / "data" / "positions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump(fits, open(ROOT / "data" / "photo_fits.json", "w"), indent=1)
    n = sum(len(v["matched"]) for v in fits.values())
    print(f"{n} moon positions from {len(fits)} photos")


if __name__ == "__main__":
    main()
