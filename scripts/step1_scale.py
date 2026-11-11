"""Step 1: put every photo on the same scale.

Problem: the 58 photos were taken at different zoom settings, with the phone
held at slightly different spots behind the eyepiece, so one pixel means a
different angle on the sky in every photo (Jupiter's disk is 20 px wide in one
photo and 130 px in another).

Ruler: Jupiter's own disk, as Galileo used. Every distance is measured in
Jupiter radii (Rj). Jupiter and the dots around it sit in the same photo, so
whatever changed the magnification changed both by the same factor.

How the radius is measured: Jupiter is overexposed. Its edge is taken where the
ring-averaged brightness falls fastest (the blurred limb), not the edge of the
white blob, which grows with exposure.

Checking the ruler without any outside data: photos taken on the same night,
within 90 minutes, show the same pattern of dots, which barely moves in that
time. Matching the patterns gives the true scale ratio of the two photos.
Comparing that with the ratio of Jupiter radii tells how good the ruler is,
and also lets the photos of one night share their measurements.

Two separate error bars per photo:
  err_photo  from the pixels (disk edge, dot positions, dot motion)
  err_site   from not knowing the camera position better than 30 m

Output (output/step1/):
  detections.json     Jupiter and dots for each photo (pixels)
  pairs.csv           same-night pattern matches
  scale.csv           1 Rj in pixels for each photo, with both error bars
  ruler_check.png     dots ratio vs. Jupiter ratio vs. phone zoom ratio
  same_scale.jpg      all 58 photos resized to the same scale
"""
import csv
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import (OUT, RAW, ImageOps, gray, local_time, night_of, photo_list, relative_magnification,
                    save_json, usable, visual_check)
from detect import find_dots, find_jupiter, radial_profile, split_double

OUT1 = OUT / "step1"
MIN_SNR = 40          # dots used for matching: clearly real, not glare ripples
MAX_GAP_MIN = 90      # only match photos this close in time (dots move slowly)
MIN_MATCHED = 3       # a match must line up at least this many dots
SITE_RADIUS_M = 30.0


# ---------- 1. Jupiter and dots ----------
def disk_edge(g, jx, jy, r_sat, across=None):
    """Radius where the ring-averaged brightness drops fastest."""
    r, p = radial_profile(g, jx, jy, 4 * r_sat, across=across)
    p = ndi.gaussian_filter1d(p, 2)
    grad = np.gradient(p, r)
    sel = (r > 0.8 * r_sat) & (r < 2.5 * r_sat)
    return float(r[sel][np.argmin(grad[sel])])


def apply_visual_check(dots, confirmed, r_sat):
    """Mark each detected dot as confirmed or not, and add confirmed dots the detector missed."""
    if confirmed is None:
        return dots
    left = list(confirmed)
    for d in dots:
        hit = [c for c in left if c["found_by"] == "detector" and np.hypot(c["x"] - d["x"], c["y"] - d["y"]) < 3]
        d["confirmed"] = bool(hit)
        if hit:
            left.remove(hit[0])
    for c in left:                                   # seen by eye, missed by the detector
        dots.append({"x": c["x"], "y": c["y"], "snr": 0.0, "flux": 0.0, "elong": 1.0,
                     "size": round(0.15 * r_sat, 1), "confirmed": True, "found_by": "eye"})
    return dots


def measure_all(recs):
    det = {}
    vc = visual_check()
    for rec in recs:
        g = gray(rec)
        jx, jy, r_sat = find_jupiter(g)
        dots, noise = find_dots(g, jx, jy, r_sat)
        dots = apply_visual_check(dots, None if vc is None else vc.get(rec["stem"], []), r_sat)
        jup = {"x": jx, "y": jy, "r_sat": r_sat, "r_edge": disk_edge(g, jx, jy, r_sat), "double": None}
        sd = split_double(g, jx, jy, r_sat)
        if sd:
            # the phone moved during the exposure: two equal Jupiters overlap. Measure one disk:
            # its radius from the two-disk fit, its edge only at right angles to the shift.
            # Its centre is the middle of the two disks: the dots are shaken the same way and each
            # dot's position is the centre of its own shaken light, so both are measured alike.
            v = (sd["c2"][0] - sd["c1"][0], sd["c2"][1] - sd["c1"][1])
            mid = ((sd["c1"][0] + sd["c2"][0]) / 2, (sd["c1"][1] + sd["c2"][1]) / 2)
            jup.update(x=mid[0], y=mid[1], r_sat=sd["r"], r_edge=disk_edge(g, mid[0], mid[1], sd["r"], across=v),
                       double={"shift_px": [round(v[0], 1), round(v[1], 1)],
                               "blob_r_as_one_disk": round(r_sat, 1), "fit_overlap": [round(sd["iou1"], 3), round(sd["iou2"], 3)]})
        det[rec["stem"]] = {"w": rec["w"], "h": rec["h"], "jupiter": jup, "noise": noise, "dots": dots}
        print(f"  {rec['stem']:18s} Jupiter r_edge={jup['r_edge']:6.1f}px{'  (double image)' if jup['double'] else ''}  "
              f"dots used={sum(usable(d, MIN_SNR) for d in dots)} of {len(dots)} found")
    return det


# ---------- 2. same-night pattern matching ----------
def dot_vectors(d):
    """Strong dots as complex numbers relative to Jupiter (y up), in pixels."""
    j = d["jupiter"]
    z = np.array([complex(c["x"] - j["x"], -(c["y"] - j["y"])) for c in d["dots"] if usable(c, MIN_SNR)])
    r = j["r_edge"]
    return z[(abs(z) > 1.8 * r) & (abs(z) < 35 * r)] if len(z) else z


def match(a, b, r_a, tol_rj):
    """Best similarity transform T (scale + rotation, maybe mirror) with a ~ T*b.

    Jupiter is the fixed centre, so pairing one dot of A with one dot of B
    fixes T. Try every pairing; keep the one that lines up the most dots.
    """
    best = None
    for mirror in (False, True):
        bb = np.conj(b) if mirror else b
        for ai in a:
            for bk in bb:
                T = ai / bk
                if not 0.2 < abs(T) < 5:
                    continue
                d = np.abs(bb[:, None] * T - a[None, :]).min(1)
                n = int((d < tol_rj * r_a).sum())
                cost = n - 1e-3 * np.minimum(d, tol_rj * r_a).sum() / r_a
                if best is None or cost > best[0]:
                    best = (cost, T, mirror)
    if best is None:
        return None
    _, T, mirror = best
    bb = np.conj(b) if mirror else b
    for _ in range(2):                                 # least-squares refinement
        d = np.abs(bb[:, None] * T - a[None, :])
        j, ok = d.argmin(1), d.min(1) < tol_rj * r_a
        if ok.sum() == 0:
            return None
        T = (np.conj(bb[ok]) * a[j[ok]]).sum() / (abs(bb[ok]) ** 2).sum()
    res = bb[ok] * T - a[j[ok]]
    n = int(ok.sum())
    # error of log|T|: dot scatter projected on the radial direction, over the lever arm
    rms = np.sqrt((abs(res) ** 2).sum() / max(2 * n - 2, 1)) if n > 1 else 0.5 * r_a
    sig = float(rms / np.sqrt((abs(a[j[ok]]) ** 2).sum()))
    return {"n": n, "scale": float(abs(T)), "rot_deg": float(np.degrees(np.angle(T))),
            "mirror": bool(mirror), "sig_log": max(sig, 0.005)}


def all_pairs(recs, det):
    by_night = {}
    for r in recs:
        by_night.setdefault(night_of(r), []).append(r)
    pairs = []
    for night, rs in sorted(by_night.items()):
        rs.sort(key=local_time)
        for i, A in enumerate(rs):
            for B in rs[i + 1:]:
                gap = (local_time(B) - local_time(A)).total_seconds() / 60
                if gap > MAX_GAP_MIN:
                    continue
                a, b = dot_vectors(det[A["stem"]]), dot_vectors(det[B["stem"]])
                if len(a) < 2 or len(b) < 2:
                    continue
                # dots move < ~0.9 Rj per hour: allow for that
                m = match(a, b, det[A["stem"]]["jupiter"]["r_edge"], 0.6 + 0.9 * gap / 60)
                if m is None or m["n"] < MIN_MATCHED:
                    continue
                ja, jb = det[A["stem"]]["jupiter"], det[B["stem"]]["jupiter"]
                ma, mb = relative_magnification(A), relative_magnification(B)
                pairs.append({"night": night, "a": A["stem"], "b": B["stem"], "gap_min": round(gap),
                              "matched": m["n"], "ratio_dots": m["scale"], "sig_log_dots": m["sig_log"],
                              "ratio_jupiter": ja["r_edge"] / jb["r_edge"],
                              "ratio_jupiter_blob": ja["r_sat"] / jb["r_sat"],
                              "ratio_zoom": ma / mb if ma and mb else None,
                              "rotation_deg": m["rot_deg"], "mirror": m["mirror"]})
    return pairs


# ---------- 3. combine: one Rj per photo ----------
def solve_scales(recs, det, pairs):
    """Least squares per night on u = log(Rj in px).

    Each photo's own disk:     log r_edge_i      = u_i        +- sig_disk
    Each matched pair (i, j):  log ratio_dots_ij = u_i - u_j  +- sig_pair
    sig_disk comes from the data: the pair-to-pair scatter of
    (log ratio_dots - log ratio_jupiter) = 2 sig_disk^2 + sig_pair^2.
    """
    d = np.array([np.log(p["ratio_dots"] / p["ratio_jupiter"]) for p in pairs])
    sp = np.array([p["sig_log_dots"] for p in pairs])
    sig_disk = float(np.sqrt(max((np.mean(d ** 2) - np.mean(sp ** 2)) / 2, 0.01 ** 2)))

    idx = {r["stem"]: i for i, r in enumerate(recs)}
    n = len(recs)
    rows, rhs, w = [], [], []
    for r in recs:
        row = np.zeros(n)
        row[idx[r["stem"]]] = 1
        rows.append(row); rhs.append(np.log(det[r["stem"]]["jupiter"]["r_edge"])); w.append(1 / sig_disk ** 2)
    for p in pairs:
        row = np.zeros(n)
        row[idx[p["a"]]], row[idx[p["b"]]] = 1, -1
        rows.append(row); rhs.append(np.log(p["ratio_dots"])); w.append(1 / p["sig_log_dots"] ** 2)
    A, y, W = np.array(rows), np.array(rhs), np.array(w)
    N = A.T @ (A * W[:, None])
    cov = np.linalg.inv(N)
    u = cov @ (A.T @ (W * y))
    linked = {r["stem"]: 1 for r in recs}
    # size of each photo's group of linked photos (connected through pairs)
    lab = list(range(n))
    def find(i):
        while lab[i] != i:
            lab[i] = lab[lab[i]]; i = lab[i]
        return i
    for p in pairs:
        lab[find(idx[p["a"]])] = find(idx[p["b"]])
    groups = {}
    for r in recs:
        groups.setdefault(find(idx[r["stem"]]), []).append(r["stem"])
    for g in groups.values():
        for s in g:
            linked[s] = len(g)
    out = {}
    for r in recs:
        i = idx[r["stem"]]
        out[r["stem"]] = {"rj_px": float(np.exp(u[i])), "err_photo": float(np.sqrt(cov[i, i])),
                          "linked": linked[r["stem"]]}
    return out, sig_disk


def site_error():
    """How much a 30 m error in the camera position changes the scale.

    The scale is a ratio of two angles seen from the same spot: (dot offset) /
    (Jupiter radius). Moving the camera sideways by L shifts every object by
    L / distance; Jupiter and its dots are at nearly the same distance D (they
    differ by at most dD ~ 30 Rj), so the ratio changes by about
    (L / D) * (dD / D). Even if Jupiter were only as far as the Moon (it is
    much farther: it shows no shift at all between photos taken hours apart
    while the Earth turns us thousands of km around), D > 3.8e8 m and
    dD / D < 0.006, so the relative change is below 30 / 3.8e8 * 0.006 = 5e-10.
    """
    return SITE_RADIUS_M / 3.8e8 * 0.006


# ---------- 4. pictures ----------
def ruler_plot(pairs, sig_disk, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dots = np.array([p["ratio_dots"] for p in pairs])
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
    lim = [0.3, 2.2]
    for k, lab, c, m in [("ratio_jupiter", "Jupiter edge", "C0", "o"),
                         ("ratio_jupiter_blob", "Jupiter white blob", "C1", "s"),
                         ("ratio_zoom", "phone zoom (EXIF)", "C3", "^")]:
        v = np.array([p[k] if p[k] else np.nan for p in pairs])
        ok = np.isfinite(v)
        rms = 100 * np.sqrt(np.mean(np.log(dots[ok] / v[ok]) ** 2))
        ax[0].scatter(dots[ok], v[ok], marker=m, s=28, color=c, alpha=0.8, label=f"{lab}  (rms {rms:.1f}%)")
        ax[1].scatter(range(len(pairs)), 100 * np.log(v / dots), marker=m, s=28, color=c, alpha=0.8)
    ax[0].plot(lim, lim, "k--", lw=0.8)
    ax[0].set(xscale="log", yscale="log", xlim=lim, ylim=lim,
              xlabel="scale ratio from matching the dot patterns",
              ylabel="scale ratio given by the ruler")
    ax[0].legend(fontsize=8, loc="upper left")
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set(xlabel="photo pair (same night)", ylabel="ruler minus dots (%)",
              title=f"single-photo Jupiter ruler error ≈ ±{100 * sig_disk:.1f}%")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def contact_sheet(recs, det, scales, path, half_rj=28, tile=320, cols=6):
    """Every photo cut out around Jupiter and resized so 1 Rj = same size."""
    rows = (len(recs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * (tile + 18)), (12, 12, 16))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    px_per_rj = tile / (2 * half_rj)
    for k, r in enumerate(recs):
        j = det[r["stem"]]["jupiter"]
        rj = scales[r["stem"]]["rj_px"]
        h = half_rj * rj
        im = ImageOps.exif_transpose(Image.open(RAW / r["file"])).convert("RGB")
        im = im.crop((int(j["x"] - h), int(j["y"] - h), int(j["x"] + h), int(j["y"] + h)))
        im = im.resize((tile, tile), Image.LANCZOS)
        im = im.point(lambda v: int(255 * (v / 255) ** 0.6))      # brighten faint dots
        x0, y0 = (k % cols) * tile, (k // cols) * (tile + 18)
        sheet.paste(im, (x0, y0))
        c = (x0 + tile / 2, y0 + tile / 2)
        for d in det[r["stem"]]["dots"]:                            # mark the strong dots
            if not usable(d, MIN_SNR):
                continue
            px = c[0] + (d["x"] - j["x"]) / rj * px_per_rj
            py = c[1] + (d["y"] - j["y"]) / rj * px_per_rj
            if x0 + 4 < px < x0 + tile - 4 and y0 + 4 < py < y0 + tile - 4:
                dr.ellipse([px - 6, py - 6, px + 6, py + 6], outline=(255, 200, 60))
        for ring in (5, 10, 15, 20, 25):
            R = ring * px_per_rj
            dr.ellipse([c[0] - R, c[1] - R, c[0] + R, c[1] + R], outline=(70, 90, 140) if ring % 10 else (110, 130, 190))
        e = 100 * scales[r["stem"]]["err_photo"]
        dr.text((x0 + 4, y0 + tile + 2), f"{r['stem'][2:]}  ±{e:.0f}%", fill=(200, 200, 210), font=font)
    sheet.save(path, quality=88)


def main():
    OUT1.mkdir(parents=True, exist_ok=True)
    recs = sorted(photo_list(), key=local_time)
    print("1. Jupiter and dots")
    det = measure_all(recs)
    save_json(det, OUT1 / "detections.json")

    print("2. same-night pattern matching")
    pairs = all_pairs(recs, det)
    with open(OUT1 / "pairs.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(pairs[0]))
        wr.writeheader()
        for p in pairs:
            wr.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()})
    print(f"  {len(pairs)} matched pairs")

    print("3. one scale per photo")
    scales, sig_disk = solve_scales(recs, det, pairs)
    site = site_error()
    with open(OUT1 / "scale.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["photo", "night", "local_time", "camera", "focal35_mm",
                     "jupiter_blob_r_px", "jupiter_edge_r_px", "rj_px",
                     "err_photo_pct", "err_site_pct", "photos_linked"])
        for r in recs:
            s, j = scales[r["stem"]], det[r["stem"]]["jupiter"]
            wr.writerow([r["stem"], night_of(r), local_time(r).isoformat(timespec="minutes"), r["camera"] or "",
                         r["focal35_mm"] or "", round(j["r_sat"], 1), round(j["r_edge"], 1), round(s["rj_px"], 2),
                         round(100 * s["err_photo"], 1), f"{100 * site:.0e}", s["linked"]])
    e = np.array([100 * s["err_photo"] for s in scales.values()])
    print(f"  single-photo ruler error ±{100 * sig_disk:.1f}%;  final per photo: median ±{np.median(e):.1f}% "
          f"(range {e.min():.1f}-{e.max():.1f}%);  site error {100 * site:.0e}%")
    save_json({"sig_disk_single_photo": sig_disk, "site_error_rel": site,
               "median_err_photo": float(np.median(e) / 100)}, OUT1 / "summary.json")

    print("4. pictures")
    ruler_plot(pairs, sig_disk, OUT1 / "ruler_check.png")
    contact_sheet(recs, det, scales, OUT1 / "same_scale.jpg")


if __name__ == "__main__":
    main()
