"""Find Jupiter and moon candidates in every photo.

Jupiter: the brightest blob. Its centre is the centroid of the saturated core
and its radius is where the azimuthally averaged brightness drops fastest
(the disk edge, before the glare halo).

Moons: small round peaks left after removing the smooth glow (background =
large median filter). Candidates on the diffraction spikes are rejected by a
roundness test. Every candidate is kept with a signal-to-noise score; the
calibration step decides which ones are real moons using the ephemeris.

Output: data/detections.json
"""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.feature import peak_local_max

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "data" / "processed" / "full"


def find_jupiter(g):
    b = ndi.gaussian_filter(g, 3)
    y0, x0 = np.unravel_index(b.argmax(), b.shape)
    thr = 0.97 * g.max()
    lab, _ = ndi.label(g >= thr)
    core = lab == lab[y0, x0]
    cy, cx = ndi.center_of_mass(core)
    # radial profile around the core centroid
    R = int(max(60, 3 * np.sqrt(core.sum() / np.pi)))
    ys, xs = np.mgrid[int(cy) - R:int(cy) + R + 1, int(cx) - R:int(cx) + R + 1]
    ok = (ys >= 0) & (ys < g.shape[0]) & (xs >= 0) & (xs < g.shape[1])
    r = np.hypot(ys - cy, xs - cx)[ok]
    v = g[ys[ok], xs[ok]]
    bins = np.arange(0, R, 0.5)
    idx = np.digitize(r, bins)
    prof = np.array([v[idx == i].mean() if np.any(idx == i) else np.nan for i in range(1, len(bins))])
    prof = ndi.gaussian_filter1d(np.nan_to_num(prof, nan=0), 1.5)
    grad = np.gradient(prof)
    r_core = np.sqrt(core.sum() / np.pi)
    # steepest drop between 0.6x and 2x the saturated-core radius
    lo, hi = int(0.6 * r_core / 0.5), int(min(2 * r_core, R - 1) / 0.5)
    k = lo + int(np.argmin(grad[lo:hi]))
    radius = bins[k] + 0.25
    return float(cx), float(cy), float(radius), float(r_core)


def find_moons(g, jx, jy, jr, max_cands=15):
    # moon blobs grow with magnification like Jupiter does, so scale with jr
    sig = max(1.5, 0.045 * jr)
    small = ndi.gaussian_filter(g, sig)
    bg = ndi.median_filter(ndi.zoom(g, 0.25, order=1), size=9)
    bg = ndi.zoom(bg, (g.shape[0] / bg.shape[0], g.shape[1] / bg.shape[1]), order=1)
    hp = small - bg
    noise = 1.4826 * np.median(np.abs(hp - np.median(hp))) + 0.3
    peaks = peak_local_max(hp, min_distance=int(max(6, 0.3 * jr)), threshold_abs=6 * noise, num_peaks=200)
    cands = []
    for y, x in peaks:
        d = np.hypot(x - jx, y - jy)
        if d < 2.2 * jr:  # inside Jupiter glare
            continue
        h = int(max(10, 0.35 * jr))
        y0, y1, x0, x1 = max(y - h, 0), min(y + h + 1, g.shape[0]), max(x - h, 0), min(x + h + 1, g.shape[1])
        patch = np.clip(hp[y0:y1, x0:x1], 0, None)
        m = patch > 0.5 * hp[y, x]
        lab, _ = ndi.label(m)
        m = lab == lab[y - y0, x - x0]
        area = int(m.sum())
        if area < 3 or area > 4 * h * h:
            continue
        w = patch * m
        yy, xx = np.mgrid[y0:y1, x0:x1]
        tot = w.sum()
        cy, cx = (w * yy).sum() / tot, (w * xx).sum() / tot
        cov = np.cov(np.vstack([xx[m] - cx, yy[m] - cy]), aweights=w[m]) if area > 2 else np.eye(2)
        ev = np.sort(np.linalg.eigvalsh(cov))
        elong = float(np.sqrt(ev[1] / max(ev[0], 1e-3)))
        if elong > 5:  # long streak = diffraction spike (short streaks are shaken moons)
            continue
        # a spike-free bright peak can also be a local bump on the glow: require
        # it to stand out against its ring of neighbours
        ring = hp[max(y - 2 * h, 0):y + 2 * h + 1, max(x - 2 * h, 0):x + 2 * h + 1]
        contrast = hp[y, x] - np.percentile(ring, 50)
        snr = float(contrast / noise)
        if snr < 6:
            continue
        cands.append({"x": float(cx), "y": float(cy), "snr": round(snr, 1),
                      "area": area, "elong": round(elong, 2),
                      "peak": float(round(small[y, x], 1))})
    cands.sort(key=lambda c: -c["snr"])
    merged = []  # one blob can still yield several peaks: keep the strongest
    for c in cands:
        if all(np.hypot(c["x"] - m["x"], c["y"] - m["y"]) > 0.45 * jr for m in merged):
            merged.append(c)
    return merged[:max_cands], float(noise)


def main():
    out = {}
    for r in csv.DictReader(open(ROOT / "data" / "photos.csv")):
        stem = Path(r["file"]).stem
        g = np.asarray(Image.open(FULL / f"{stem}.png").convert("L"), float)
        jx, jy, jr, jcore = find_jupiter(g)
        cands, noise = find_moons(g, jx, jy, jr)
        out[stem] = {"w": g.shape[1], "h": g.shape[0],
                     "jupiter": {"x": jx, "y": jy, "r": jr, "r_core": jcore},
                     "noise": noise, "candidates": cands}
        print(f"{stem}: J=({jx:.0f},{jy:.0f}) r={jr:.1f} core={jcore:.1f}  "
              f"{len(cands)} cands snr={[c['snr'] for c in cands]}")
    json.dump(out, open(ROOT / "data" / "detections.json", "w"), indent=1)


if __name__ == "__main__":
    main()
