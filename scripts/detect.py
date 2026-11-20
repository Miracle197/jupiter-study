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


# ---------- Jupiter's edge, ray by ray ----------
def limb_points(g, cx, cy, r0, n_rays=360, step=0.25, smooth_az=2):
    """One edge point on each of n_rays rays from (cx, cy): where the brightness falls fastest.

    Each ray is smoothed along its length by ~4% of the radius (blur and JPEG noise) and,
    lightly, against its neighbours. Returns ray angles, edge radii, and the edge points.
    """
    gs = ndi.gaussian_filter(g, 1.0)
    th = np.arange(n_rays) * 2 * np.pi / n_rays
    r = np.arange(0, 2.6 * r0, step)
    X = cx + r[None, :] * np.cos(th)[:, None]
    Y = cy + r[None, :] * np.sin(th)[:, None]
    P = ndi.map_coordinates(gs, [Y, X], order=1, mode="nearest")
    P = ndi.uniform_filter1d(P, 2 * smooth_az + 1, axis=0, mode="wrap")
    grad = np.gradient(ndi.gaussian_filter1d(P, max(2.0, 0.04 * r0) / step, axis=1), r, axis=1)
    sel = (r > 0.5 * r0) & (r < 2.0 * r0)
    rr = r[sel][np.argmin(grad[:, sel], axis=1)]
    return th, rr, cx + rr * np.cos(th), cy + rr * np.sin(th)


def fit_circle(x, y, r_guess):
    """Robust circle through edge points (diffraction spikes and flares pull single rays outward)."""
    from scipy.optimize import least_squares
    c0 = [np.median(x), np.median(y), r_guess]
    sc = max(0.02 * r_guess, 0.75)
    sol = least_squares(lambda p: (np.hypot(x - p[0], y - p[1]) - p[2]) / sc, c0, loss="soft_l1")
    res = np.hypot(x - sol.x[0], y - sol.x[1]) - sol.x[2]
    return float(sol.x[0]), float(sol.x[1]), float(sol.x[2]), res


def jupiter_edge(g, cx, cy, r0, across=None, half_width_deg=40, iters=3):
    """Centre and radius of Jupiter's edge from 360 rays.

    across: for a shaken photo, the shift direction (dx, dy); then (cx, cy) is kept and the radius
    is the median edge distance in the two sectors at right angles to the shift, where the disk
    is not stretched. Returns (cx, cy, R, err_R) with err_R from the spread of the edge points.
    """
    if across is None:
        for _ in range(iters):
            th, rr, x, y = limb_points(g, cx, cy, r0)
            cx, cy, r0, res = fit_circle(x, y, r0)
        mad = 1.4826 * np.median(np.abs(res))
        n_ind = len(res) / 5                                   # neighbouring rays share pixels
        return cx, cy, r0, float(mad / np.sqrt(n_ind))
    for _ in range(iters):
        th, rr, x, y = limb_points(g, cx, cy, r0)
        a = np.arctan2(across[1], across[0])
        keep = np.abs(np.cos(th - a)) < np.sin(np.radians(half_width_deg))
        r0 = float(np.median(rr[keep]))
    d = rr[keep] - r0
    mad = 1.4826 * np.median(np.abs(d))
    return cx, cy, r0, float(mad / np.sqrt(keep.sum() / 5))


# ---------- how bright the dots are: how hard the photo was exposed ----------
def dot_brightness(g, dots, jx, jy, R, min_dist=3.0):
    """How hard the photo was exposed, read from the dots: their light divided by Jupiter's area.

    A dot's total light (summed over its image, background removed) does not change when the
    phone shakes and smears it. Divided by Jupiter's area in pixels (R^2), it is proportional to
    how bright each pixel of Jupiter's disk is -- the thing that decides how far the overexposed
    white spreads. The phone stores brightness with a gamma of about 2.2; undoing it makes the
    numbers proportional to the light. Median over the dots well clear of Jupiter's glare.
    """
    vals = []
    for d in dots:
        if np.hypot(d["x"] - jx, d["y"] - jy) < min_dist * R:
            continue
        B = int(max(8, 0.5 * R))
        xi, yi = int(round(d["x"])), int(round(d["y"]))
        if yi - 2 * B < 0 or xi - 2 * B < 0 or yi + 2 * B >= g.shape[0] or xi + 2 * B >= g.shape[1]:
            continue
        p = ndi.gaussian_filter(g[yi - 2 * B:yi + 2 * B + 1, xi - 2 * B:xi + 2 * B + 1], 1.0)
        yy, xx = np.mgrid[-2 * B:2 * B + 1, -2 * B:2 * B + 1]
        rr = np.hypot(xx, yy)
        lin = (p / 255) ** 2.2
        bg = float(np.median(lin[(rr > 1.3 * B) & (rr < 2 * B)]))
        vals.append(float(((lin - bg) * (rr < 0.8 * B)).sum()) / R ** 2)
    if not vals and min_dist > 2:
        return dot_brightness(g, dots, jx, jy, R, min_dist=2.0)
    vals = [v for v in vals if v > 0]
    return float(np.median(vals)) if vals else None
