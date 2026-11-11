"""Find Jupiter and the small bright dots around it in one photo.

Jupiter: the brightest blob; centre = centroid of its saturated core.
Dots: every photo is first shrunk so that Jupiter's saturated core has the same
size (R_WORK pixels), then the same settings find compact bright peaks in all
photos. Long streaks (diffraction spikes) and big soft blobs (internal
reflections) are rejected. Nothing is assumed about what the dots are.
"""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.feature import peak_local_max

R_WORK = 20.0      # Jupiter core radius in the shrunk working image (pixels)


def find_jupiter(g, sat_level=250):
    b = ndi.gaussian_filter(g, 2)
    y0, x0 = np.unravel_index(b.argmax(), b.shape)
    lab, _ = ndi.label(g >= min(sat_level, 0.98 * g.max()))
    core = lab == lab[y0, x0]
    cy, cx = ndi.center_of_mass(core)
    r_sat = float(np.sqrt(core.sum() / np.pi))
    return float(cx), float(cy), r_sat


def radial_profile(g, cx, cy, rmax, step=0.5, across=None, half_width_deg=40):
    """Mean brightness in thin rings around (cx, cy).

    across: a direction (dx, dy); if given, only the two sectors at right
    angles to it are used (for a shaken photo, the disk is not stretched there).
    """
    y0, y1 = max(0, int(cy - rmax)), min(g.shape[0], int(cy + rmax) + 1)
    x0, x1 = max(0, int(cx - rmax)), min(g.shape[1], int(cx + rmax) + 1)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    k = (np.hypot(yy - cy, xx - cx) / step).astype(int)
    w = np.ones(k.shape)
    if across is not None:
        ang = np.arctan2(yy - cy, xx - cx) - np.arctan2(across[1], across[0])
        w = (np.abs(np.cos(ang)) < np.sin(np.radians(half_width_deg))).astype(float)
    n = np.bincount(k.ravel(), w.ravel())
    s = np.bincount(k.ravel(), (w * g[y0:y1, x0:x1]).ravel())
    r = (np.arange(len(n)) + 0.5) * step
    keep = (r < rmax) & (n > 0)
    return r[keep], (s / np.maximum(n, 1))[keep]


def shrink(g, f):
    if f >= 1:
        return g, 1.0
    h, w = g.shape
    im = Image.fromarray(g.astype(np.float32), mode="F").resize(
        (max(1, round(w * f)), max(1, round(h * f))), Image.BOX)
    a = np.asarray(im, float)
    return a, a.shape[1] / w


def find_dots(g, jx, jy, r_sat, max_dots=20):
    """Bright compact dots outside Jupiter's glare (full-image pixel coords)."""
    a, f = shrink(g, R_WORK / r_sat)
    J = np.array([jx, jy]) * f
    rj = r_sat * f
    hp = ndi.gaussian_filter(a, 1.5) - ndi.gaussian_filter(a, 10.0)
    noise = 1.4826 * np.median(np.abs(hp - np.median(hp))) + 0.05
    peaks = peak_local_max(hp, min_distance=4, threshold_abs=5 * noise, num_peaks=400)
    B = 14                                          # half-size of the box around a peak
    yy, xx = np.mgrid[-B:B + 1, -B:B + 1]
    dots = []
    for y, x in peaks:
        d = np.hypot(x - J[0], y - J[1])
        if d < 1.8 * rj or y < B or x < B or y >= a.shape[0] - B or x >= a.shape[1] - B:
            continue
        p = hp[y - B:y + B + 1, x - B:x + B + 1]
        m = p > 0.35 * hp[y, x]
        lab, _ = ndi.label(m)
        m = lab == lab[B, B]
        area = int(m.sum())
        w = np.where(m, p, 0)
        tot = w.sum()
        cy, cx = (w * yy).sum() / tot, (w * xx).sum() / tot
        cov = np.cov(np.vstack([xx[m] - cx, yy[m] - cy]), aweights=w[m]) if area > 2 else np.eye(2)
        ev = np.sort(np.linalg.eigvalsh(cov))
        elong = float(np.sqrt(ev[1] / max(ev[0], 1e-3)))
        size = float(np.sqrt(ev[1]))
        if elong > 6 or size > 0.4 * rj or m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any():
            continue                                  # streak, or part of something big
        # must stand out from the glow right around it (rejects ripples in the halo)
        ring = a[max(y - 2 * B, 0):y + 2 * B + 1, max(x - 2 * B, 0):x + 2 * B + 1]
        bump = a[y, x] - np.percentile(ring, 30)
        snr = float(hp[y, x] / noise)
        if bump < 4 * noise:
            continue
        dots.append({"x": float((x + cx) / f), "y": float((y + cy) / f), "snr": round(snr, 1),
                     "flux": float(round(tot, 1)), "elong": round(elong, 2),
                     "size": round(size / f, 1)})
    dots.sort(key=lambda c: -c["snr"])
    merged = []                                       # a shaken dot can give 2 peaks
    for c in dots:
        if all(np.hypot(c["x"] - m["x"], c["y"] - m["y"]) > 0.35 * r_sat for m in merged):
            merged.append(c)
    return merged[:max_dots], float(noise)


# ---------- shaken photos: two overlapping Jupiters ----------
def _union_iou(mask, yy, xx, c1, v, r):
    m = ((xx - c1[0]) ** 2 + (yy - c1[1]) ** 2 < r * r) | ((xx - c1[0] - v[0]) ** 2 + (yy - c1[1] - v[1]) ** 2 < r * r)
    inter = (m & mask).sum()
    return inter / max((m | mask).sum(), 1)


def split_double(g, cx, cy, r_sat, sat_level=250):
    """Is the saturated blob two equal disks (the phone moved during the exposure)?

    Fits one disk and two equal overlapping disks to the saturated pixels.
    Returns None for a single disk, else {"c1", "c2", "r", "iou1", "iou2"}.
    """
    from scipy.optimize import minimize
    R = int(3 * r_sat)
    y0, x0 = max(0, int(cy) - R), max(0, int(cx) - R)
    sub = g[y0:int(cy) + R, x0:int(cx) + R]
    lab, _ = ndi.label(sub >= min(sat_level, 0.98 * g.max()))
    core = lab == lab[int(cy) - y0, int(cx) - x0]
    f = max(1, int(r_sat / 40))                       # work on a coarser grid for speed
    mask = core[::f, ::f]
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]] * f
    ys, xs = np.nonzero(core)
    c0 = np.array([xs.mean(), ys.mean()])
    cov = np.cov(np.vstack([xs, ys]))
    ev, evec = np.linalg.eigh(cov)
    r1 = np.sqrt(core.sum() / np.pi)
    iou1 = _union_iou(mask, yy, xx, c0, np.zeros(2), r1)
    d = 2 * np.sqrt(max(ev[1] - ev[0], 0))            # separation from the stretch of the blob
    if d < 0.15 * r1:
        return None
    v0 = evec[:, 1] * d
    r0 = 2 * np.sqrt(ev[0])
    p0 = np.array([*(c0 - v0 / 2), *v0, r0])
    res = minimize(lambda p: -_union_iou(mask, yy, xx, p[0:2], p[2:4], p[4]), p0, method="Nelder-Mead",
                   options={"xatol": 0.5, "fatol": 1e-4, "maxiter": 600})
    c1, v, r = res.x[0:2], res.x[2:4], res.x[4]
    iou2 = -res.fun
    if iou2 - iou1 < 0.02 or np.hypot(*v) < 0.15 * r:
        return None
    return {"c1": (float(c1[0] + x0), float(c1[1] + y0)), "c2": (float(c1[0] + v[0] + x0), float(c1[1] + v[1] + y0)),
            "r": float(r), "iou1": float(iou1), "iou2": float(iou2)}
