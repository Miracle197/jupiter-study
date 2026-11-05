"""Step 2: turn every photo so the dots lie along one line, same end the same way.

What Galileo noticed first: the little stars next to Jupiter are always on one
straight line through it. The phone was turned differently for every photo and
the sky itself turns during the night, so that line points a different way in
each photo. Three independent ways to find it are compared:

A. Dots (one photo at a time): the line through Jupiter that passes closest
   to the dots (brighter dots count more). Precise, but a line has two ends
   and A cannot tell them apart.
B. Gravity + turning sky (all photos together, see field_rotation.py): the
   iPhone recorded which way was down; measured from there, the line turns
   the same way every night as Jupiter crosses the sky. One fitted curve
   predicts the direction in every photo, including which end is which.
   Each photo's prediction comes from a fit that leaves that photo out.
C. Same-night pairs (step 1 style dot matching, up to 3 h apart): tells
   whether two photos have the same end of the line on the same side. Used
   only to check B.

Final direction: the most likely angle given every dot (a far dot fixes the
angle far better than a near one; some dots may be off the line) and B as one
more measurement. B picks the end. A alone vs B alone is the main cross-check.

Errors, kept separate:
  err_photo  angle: A and B combined; positions: step 1 scale + centring + angle
  err_site   camera position within 30 m: B uses the latitude; refitting with
             the latitude moved by 30 m gives the change, carried to each photo

+X is the same end of the sky in every photo. Whether that end is east or
west depends on how the telescope turns the image, which the photos do not
show.

Output (output/step2/):
  orientation.csv    per photo: A, B, final direction, both errors, Jupiter altitude
  positions.csv      per dot: X, Y (Rj) with both errors
  links.csv          same-night pairs (method C) and whether B agrees
  summary.json       fit of the turning sky, A-vs-B and C checks, site effect
  field_rotation.png the fitted curve and A minus B for every photo
  notebook.png       Galileo-style notebook, one row per photo
  strips.jpg         the real photos turned and cut to a strip along the line
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import field_rotation
from common import OUT, RAW, ROOT, ImageOps, apple_gravity, local_time, night_of, photo_list, save_json
from field_rotation import REF_DAY, SIDEREAL, wrap180
from step1_scale import dot_vectors, match

OUT1, OUT2 = OUT / "step1", OUT / "step2"
MIN_SNR_LINE = 15       # dots used to find the line (weighted by brightness)
MAX_R = 35              # Rj: farther dots are foreground lights, not near Jupiter
MAX_GAP_MIN = 180       # same-night links for deciding which end is which
CENTROID_RJ = 0.05      # Jupiter centre + dot centroid floor (Rj)
LINE_THICK_RJ = 0.25    # measured rms distance of dots from the line (see summary.json)
STRONG_SNR = 40          # bright dots used for the final angle (as in step 1)
OFF_LINE_FRACTION = 0.15  # share of bright dots off the line (step 2, first pass)
NO_GRAVITY_ROLL_DEG = 20  # photo without gravity data: assume the phone was upright, give or take this
SITE_RADIUS_M = 30.0
_site = json.load(open(ROOT / "data" / "observer.json"))
LAT = np.radians(_site["lat_deg"])
SITE_DLAT = SITE_RADIUS_M / 6371000.0     # 30 m north-south, in radians of latitude
T_REF = datetime(2023, 12, 3)             # time origin for the fit (days)


def load_step1():
    det = json.load(open(OUT1 / "detections.json"))
    scale = {r["photo"]: r for r in csv.DictReader(open(OUT1 / "scale.csv"))}
    return det, scale


def dots_rj(d, rj):
    """All dots as complex numbers relative to Jupiter (y up), in Rj."""
    j = d["jupiter"]
    out = []
    for k, c in enumerate(d["dots"]):
        z = complex(c["x"] - j["x"], -(c["y"] - j["y"])) / rj
        if 1.5 < abs(z) < MAX_R and c["snr"] >= MIN_SNR_LINE:
            out.append((k, z, c))
    return out


def fit_line(pts):
    """Angle (mod 180) of the line through Jupiter that best fits the dots."""
    if not pts:
        return None
    z = np.array([p[1] for p in pts])
    w = np.sqrt([p[2]["snr"] for p in pts])
    r = np.abs(z)
    best = None
    for th in np.radians(np.arange(0, 180, 0.25)):
        perp = np.abs((z * np.exp(-1j * th)).imag)
        tol = 0.4 + 0.03 * r
        score = (w * np.clip(1 - (perp / tol) ** 2, 0, None)).sum()
        if best is None or score > best[0]:
            best = (score, th)
    th = best[1]
    for _ in range(3):                                  # refine on the inliers
        perp = (z * np.exp(-1j * th)).imag
        inl = np.abs(perp) < 0.4 + 0.03 * r
        if inl.sum() == 0:
            break
        # small-angle LS: perp_i ~ perp0_i - x_i * dth
        x = (z[inl] * np.exp(-1j * th)).real
        ww = w[inl]
        dth = (ww * x * perp[inl]).sum() / (ww * x * x).sum()
        th += dth
    perp = (z * np.exp(-1j * th)).imag
    x = (z * np.exp(-1j * th)).real
    inl = np.abs(perp) < 0.4 + 0.03 * r
    n = int(inl.sum())
    if n >= 2:
        rms = np.sqrt((w[inl] * perp[inl] ** 2).sum() / w[inl].sum())
        sig_th = float(max(rms, CENTROID_RJ) / np.sqrt((x[inl] ** 2).sum()))
    else:
        # one dot: it may itself sit off the true line by about the line thickness
        sig_th = float(LINE_THICK_RJ / max(abs(x[inl]).max(), 1)) if n else np.radians(5)
    return {"theta": float(th % np.pi), "sig_theta": sig_th, "n_on_line": n,
            "thickness_rj": float(np.sqrt(np.mean(perp[inl] ** 2))) if n else None}


def link_signs(recs, det, scale, lines):
    """Groups of same-night photos whose line ends can be matched up.

    Returns {stem: (group_id, sign)} where sign (+1/-1) flips the photo's
    own +X end so that all photos in a group share the same +X end.
    """
    parent = {r["stem"]: (r["stem"], 1) for r in recs}

    def find(s):
        p, sg = parent[s]
        if p == s:
            return s, 1
        root, sg2 = find(p)
        parent[s] = (root, sg * sg2)
        return root, sg * sg2

    links = []
    by_night = {}
    for r in recs:
        by_night.setdefault(night_of(r), []).append(r)
    for night, rs in by_night.items():
        rs.sort(key=local_time)
        for i, A in enumerate(rs):
            for B in rs[i + 1:]:
                gap = (local_time(B) - local_time(A)).total_seconds() / 60
                la, lb = lines[A["stem"]], lines[B["stem"]]
                if gap > MAX_GAP_MIN or la is None or lb is None:
                    continue
                a, b = dot_vectors(det[A["stem"]]), dot_vectors(det[B["stem"]])
                if len(a) < 2 or len(b) < 2:
                    continue
                m = match(a, b, det[A["stem"]]["jupiter"]["r_edge"], 0.6 + 0.9 * gap / 60)
                if m is None or m["n"] < 3:
                    continue
                # B's +X direction carried into A's photo by the match
                ub = np.exp(1j * lb["theta"])
                ub = np.conj(ub) if m["mirror"] else ub
                carried = ub * np.exp(1j * np.radians(m["rot_deg"]))
                cosang = (carried * np.conj(np.exp(1j * la["theta"]))).real
                if abs(cosang) < 0.85:            # lines disagree by > ~30 deg: don't trust
                    continue
                rel = 1 if cosang > 0 else -1     # sign_B = rel * sign_A
                links.append({"a": A["stem"], "b": B["stem"], "gap_min": round(gap),
                              "matched": m["n"], "relative_sign": rel,
                              "line_agreement_deg": round(float(np.degrees(np.arccos(min(1, abs(cosang))))), 1)})
                ra, sa = find(A["stem"])
                rb, sb = find(B["stem"])
                if ra != rb:
                    parent[rb] = (ra, sa * rel * sb)
    out = {}
    roots = {}
    for r in recs:
        root, sg = find(r["stem"])
        gid = roots.setdefault(root, len(roots) + 1)
        out[r["stem"]] = (gid, sg)
    return out, links




# ---------- method B: gravity + how the sky turns ----------
def gravity_down(recs):
    """Image direction of 'down' (deg, x right / y up) from the phone's gravity sensor."""
    out = {}
    for r in recs:
        g = apple_gravity(RAW / r["file"])
        out[r["stem"]] = None if g is None else float(np.degrees(np.arctan2(g[1], g[0])))
    return out


def days_since(rec, t=None):
    t = t or local_time(rec)
    return (t - T_REF).total_seconds() / 86400


def combine(pts, theta_a, theta_b, sig_b):
    """Final direction from every dot plus B, by the most likely angle.

    Only bright dots are used (faint ones near Jupiter are mostly glare).
    A dot at distance r that sits up to ~0.25 Rj off the line (the measured
    line thickness, plus Jupiter-centre error) fixes the angle to about
    0.27 / r radians, so far dots count much more than near ones. Any dot may
    also be something off the line (OFF_LINE_FRACTION of them are). B's
    prediction joins as one more measurement. Every angle 0-180 deg is tried,
    so the answer does not depend on a starting guess. The +X end is the end
    B points to.

    Returns final directed angle, its error, the number of dots on the final
    line, and how safely the +X end is known (in B errors).
    """
    strong = [p for p in pts if p[2]["snr"] >= STRONG_SNR]
    pts = strong or pts                  # faint dots near Jupiter are mostly glare ripples
    z = np.array([p[1] for p in pts]) if pts else np.zeros(0, complex)
    r = np.abs(z)
    ang = np.degrees(np.angle(z))
    sig = np.degrees(np.hypot(LINE_THICK_RJ, 0.1) / np.maximum(r, 1e-9))
    grid = theta_b + np.arange(-90, 90, 0.02)

    def loglik(th):
        d = wrap180(ang[None, :] - th[:, None])
        inl = (1 - OFF_LINE_FRACTION) * np.exp(-0.5 * (d / sig) ** 2) / (np.sqrt(2 * np.pi) * sig)
        ll = np.log(inl + OFF_LINE_FRACTION / 180).sum(1)
        return ll - 0.5 * ((th - theta_b) / sig_b) ** 2

    ll = loglik(grid)
    k = int(np.argmax(ll))
    th = grid[k]
    d = wrap180(ang - th)
    use = np.abs(d) < 3 * sig
    err = float(1 / np.sqrt(np.sum(1 / sig[use] ** 2) + 1 / sig_b ** 2))
    margin = (90 - abs(float(wrap180(th - theta_b)))) / sig_b
    return float(th % 360), err, int(use.sum()), margin


# ---------- pictures ----------
def rotation_plot(t, rel_a, sig_a, has, pred_rel, sol, final_rel, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import cm
    T0, dec, c, drift = sol["p"]
    # hours before (-) / after (+) Jupiter was highest, from the fit
    H = SIDEREAL * (t - T0 - drift * (t - REF_DAY) / 1440)
    H = (H - np.round(H)) * 24
    hh = np.linspace(H.min() - 0.3, H.max() + 0.3, 400)
    d, Hr = np.radians(dec), np.radians(hh * 15)
    q = np.degrees(np.arctan2(np.sin(Hr), np.tan(LAT) * np.cos(d) - np.sin(d) * np.cos(Hr)))
    h = np.degrees(np.arcsin(np.sin(LAT) * np.sin(d) + np.cos(LAT) * np.cos(d) * np.cos(Hr)))
    curve = c + sol["s"] * q + sol["k"] * h
    at = np.interp(H, hh, curve)
    y = at + (final_rel - at + 180) % 360 - 180          # directed angle drawn next to the curve
    col = cm.viridis(np.clip(t / 40, 0, 1))
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.4, 1]})
    ax[0].plot(hh, curve, "k-", lw=1, label="fitted turning of the sky")
    for i in range(len(t)):
        ax[0].scatter(H[i], y[i], color=col[i], s=22, marker="o" if has[i] else "x", zorder=3)
    ax[0].set_xlabel("hours from the moment Jupiter was highest (fitted)")
    ax[0].set_ylabel("+X end, measured from the phone's 'up' (deg)")
    ax[0].legend(fontsize=8, loc="upper right")
    ax[0].set_title("Method B: all photos follow one curve (colour = date Dec 3 to Jan 11; x = no gravity data)",
                    fontsize=9)
    resid = wrap180(rel_a - pred_rel)
    ax[1].errorbar(range(len(t)), resid, yerr=sig_a, fmt="none", ecolor="0.6", lw=0.8)
    ax[1].scatter(range(len(t)), resid, c=col, s=18, zorder=3)
    ax[1].axhspan(-sol["sigma"], sol["sigma"], color="C0", alpha=0.12,
                  label=f"±1σ of method B ({sol['sigma']:.1f}°)")
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_xlabel("photo (time order)")
    ax[1].set_ylabel("A (dots) minus B (prediction), deg")
    ax[1].set_title("Method A vs method B, photo by photo (B fitted without that photo)", fontsize=9)
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def notebook_plot(recs, rows, orient, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(recs)
    fig, ax = plt.subplots(figsize=(10, 0.24 * n + 1.2))
    for i, r in enumerate(recs):
        y = n - 1 - i
        o = orient[r["stem"]]
        ax.plot(0, y, "o", ms=7, color="k")
        sure = o["sign_margin_sigma"] >= 3
        for p in rows:
            if p["photo"] != r["stem"]:
                continue
            ms = 3 + min(p["snr"], 200) / 30
            if p["in_band"]:
                ax.plot(p["X_rj"], y, "*", ms=ms, color="C0" if sure else "C1")
            elif p["snr"] >= 40:
                ax.plot(p["X_rj"], y, "o", ms=ms * 0.7, mfc="none", mec="0.5", mew=0.8)
        ax.text(-31, y, r["stem"][2:].replace("T", " "), va="center", ha="right", fontsize=7, family="monospace")
        if not sure:
            ax.text(31, y, f"?{o['sign_margin_sigma']:.1f}σ", va="center", fontsize=7, color="C1")
    ax.set_xlim(-31, 31)
    ax.set_ylim(-1, n)
    ax.set_yticks([])
    ax.set_xlabel("position along the line (Jupiter radii); +X is the same end of the sky in every photo")
    ax.set_title("All photos turned so the dots lie on one line, every photo with the same +X end\n"
                 "orange = +X end less certain; hollow = bright dot outside the band of dots", fontsize=9)
    for s in ("left", "right", "top"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def strips(recs, det, scale, orient, path, half_x=26, half_y=3.5, px_per_rj=22):
    W, H = int(2 * half_x * px_per_rj), int(2 * half_y * px_per_rj)
    lab_h = 14
    sheet = Image.new("RGB", (W, len(recs) * (H + lab_h)), (10, 10, 14))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    for i, r in enumerate(recs):
        s = r["stem"]
        j = det[s]["jupiter"]
        rj = float(scale[s]["rj_px"])
        o = orient[s]
        y0 = i * (H + lab_h)
        dr.text((4, y0), f"{s}   turned {o['final_deg']:.1f}° ±{o['err_photo_deg']:.1f}°   (+X end: right)",
                fill=(190, 190, 200), font=font)
        im = ImageOps.exif_transpose(Image.open(RAW / r["file"])).convert("RGB")
        R = int(np.hypot(half_x, half_y) * rj) + 2
        crop = im.crop((int(j["x"]) - R, int(j["y"]) - R, int(j["x"]) + R, int(j["y"]) + R))
        crop = crop.rotate(-o["final_deg"], resample=Image.BICUBIC)   # PIL turns counter-clockwise
        c = crop.size[0] / 2
        crop = crop.crop((int(c - half_x * rj), int(c - half_y * rj), int(c + half_x * rj), int(c + half_y * rj)))
        crop = crop.resize((W, H), Image.LANCZOS).point(lambda v: int(255 * (v / 255) ** 0.6))
        sheet.paste(crop, (0, y0 + lab_h))
        for k in range(-25, 26, 5):
            x = W / 2 + k * px_per_rj
            dr.line([(x, y0 + lab_h + H - 4), (x, y0 + lab_h + H)], fill=(90, 110, 160))
    sheet.save(path, quality=88)


def band_edge(abs_y, min_gap=1.0):
    """Where the band of dots ends: middle of the first gap wider than min_gap Rj."""
    y = np.sort(abs_y)
    for a, b in zip(y[:-1], y[1:]):
        if b - a > min_gap:
            return float((a + b) / 2)
    return float(y[-1] + min_gap)


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


def main():
    OUT2.mkdir(parents=True, exist_ok=True)
    recs = sorted(photo_list(), key=local_time)
    det, scale = load_step1()
    stems = [r["stem"] for r in recs]

    # --- method A: the line of dots in each photo ---
    lines, pts_all = {}, {}
    for r in recs:
        s = r["stem"]
        pts_all[s] = dots_rj(det[s], float(scale[s]["rj_px"]))
        lines[s] = fit_line(pts_all[s])
    theta_a = np.array([np.degrees(lines[s]["theta"]) for s in stems])
    sig_a = np.array([np.degrees(lines[s]["sig_theta"]) for s in stems])

    # --- method B: gravity + turning sky ---
    down = gravity_down(recs)
    has = np.array([down[s] is not None for s in stems])
    D = np.array([down[s] if down[s] is not None else -90.0 for s in stems])
    rel_a = theta_a - (D + 90)                     # line angle measured from the phone's "up" (+90)
    t = np.array([days_since(r) for r in recs])
    sol = field_rotation.fit(t[has], rel_a[has], LAT)
    used = np.zeros(len(t), bool)
    used[np.where(has)[0][sol["used"]]] = True
    sol_full = dict(sol, used=used)
    pred_rel, sig_b = field_rotation.leave_one_out(t, rel_a, LAT, sol_full, has)
    sig_b[~has] = np.hypot(sig_b[~has], NO_GRAVITY_ROLL_DEG)   # phone roll unknown for these
    site_rel, site_par = field_rotation.site_shift(t, rel_a, LAT, sol_full, SITE_DLAT)
    theta_b = pred_rel + (D + 90)                  # back to the photo's own axes
    q, alt = field_rotation.q_h(t, sol["p"][0], sol["p"][1], sol["p"][3], LAT)

    # does the clock of photos whose file name and camera disagree fit better one way?
    clock_checks = []
    for i, r in enumerate(recs):
        nt = datetime.fromisoformat(r["name_time"])
        if r["exif_time"] and abs((local_time(r) - nt).total_seconds()) > 300:
            alt_rel = field_rotation.model(sol["p"], sol["s"], sol["k"], np.array([days_since(r, nt)]), LAT)[0]
            clock_checks.append({"photo": r["stem"], "camera_time": r["exif_time"], "file_name_time": r["name_time"],
                                 "A_minus_B_camera_time_deg": round(float(wrap180(rel_a[i] - pred_rel[i])), 1),
                                 "A_minus_B_file_name_time_deg": round(float(wrap180(rel_a[i] - alt_rel)), 1)})

    # --- combine A and B; B decides the +X end ---
    orient, sign_vs_a = {}, {}
    for i, r in enumerate(recs):
        s = r["stem"]
        final, err, n_used, margin = combine(pts_all[s], theta_a[i], theta_b[i], sig_b[i])
        d = float(wrap180(theta_a[i] - theta_b[i]))
        err_site = float((err / sig_b[i]) ** 2 * site_rel[i])    # only B depends on the site; B's share
        orient[s] = {"final_deg": final, "err_photo_deg": err, "A_minus_B_deg": d,
                     "agree_sigma": abs(d) / np.hypot(sig_a[i], sig_b[i]),
                     "final_minus_A_deg": float(wrap180(final - theta_a[i])), "dots_used": n_used,
                     "sign_margin_sigma": margin, "err_site_deg": err_site}
        sign_vs_a[s] = 1 if np.cos(np.radians(final - theta_a[i])) > 0 else -1

    # --- method C: same-night pairs check B's choice of ends ---
    groups, links = link_signs(recs, det, scale, lines)
    for L in links:
        L["B_says_same_end"] = sign_vs_a[L["b"]] == L["relative_sign"] * sign_vs_a[L["a"]]
    agree_links = sum(L["B_says_same_end"] for L in links)

    # --- positions along the line ---
    rows = []
    for i, r in enumerate(recs):
        s = r["stem"]
        o = orient[s]
        rot = np.exp(-1j * np.radians(o["final_deg"]))
        es = float(scale[s]["err_photo_pct"]) / 100
        for k, z, c in pts_all[s]:
            w_ = z * rot
            cen = CENTROID_RJ + c.get("size", 0) / float(scale[s]["rj_px"]) / max(c["snr"], 1) * 3
            rows.append({"photo": s, "night": night_of(r), "local_time": local_time(r).isoformat(timespec="minutes"),
                         "dot": k, "X_rj": round(w_.real, 3), "Y_rj": round(w_.imag, 3),
                         "err_photo_X_rj": round(float(np.hypot(abs(w_.real) * es, cen)), 3),
                         "err_photo_Y_rj": round(float(np.hypot(abs(w_.real) * np.radians(o["err_photo_deg"]), cen)), 3),
                         "err_site_X_rj": 0.0,
                         "err_site_Y_rj": float(f"{abs(w_.real) * np.radians(o['err_site_deg']):.2e}"),
                         "snr": c["snr"], "in_band": None,
                         "plus_x_margin_sigma": round(o["sign_margin_sigma"], 1)})

    # the dots form a band, not a perfect line: find its edge from the data (first wide gap in |Y|)
    band = band_edge([abs(p["Y_rj"]) for p in rows if p["snr"] >= STRONG_SNR])
    for p in rows:
        p["in_band"] = abs(p["Y_rj"]) < band

    orow = []
    for i, r in enumerate(recs):
        s, L, o = r["stem"], lines[r["stem"]], orient[r["stem"]]
        orow.append({"photo": s, "night": night_of(r), "local_time": local_time(r).isoformat(timespec="minutes"),
                     "gravity_down_deg": "" if down[s] is None else round(down[s], 2),
                     "A_line_deg": round(theta_a[i], 2), "A_err_deg": round(sig_a[i], 2),
                     "A_dots_on_line": L["n_on_line"],
                     "B_plusX_deg": round(theta_b[i] % 360, 2), "B_err_deg": round(sig_b[i], 2),
                     "A_minus_B_deg": round(o["A_minus_B_deg"], 2), "A_B_agree_sigma": round(o["agree_sigma"], 2),
                     "final_plusX_deg": round(o["final_deg"], 2), "err_photo_deg": round(o["err_photo_deg"], 2),
                     "final_dots_used": o["dots_used"], "final_minus_A_deg": round(o["final_minus_A_deg"], 2),
                     "err_site_deg": f"{o['err_site_deg']:.1e}",
                     "plusX_margin_sigma": round(o["sign_margin_sigma"], 1),
                     "jupiter_altitude_deg": round(float(alt[i]), 1), "parallactic_deg": round(float(q[i]), 1),
                     "line_thickness_rj": "" if L["thickness_rj"] is None else round(L["thickness_rj"], 3),
                     "same_night_group": groups[s][0]})
    write_csv(OUT2 / "orientation.csv", orow)
    write_csv(OUT2 / "positions.csv", rows)
    write_csv(OUT2 / "links.csv", links)

    T0, dec, c, drift = sol["p"]
    e = np.sqrt(np.diag(sol["cov"]))
    resid_ab = np.array([orient[s]["A_minus_B_deg"] for s in stems])
    on = [p for p in rows if p["in_band"] and p["snr"] >= STRONG_SNR]
    off = [p for p in rows if not p["in_band"] and p["snr"] >= STRONG_SNR]
    summary = {
        "method_A_dots": {"median_err_deg": float(np.median(sig_a))},
        "method_B_turning_sky": {
            "photos_with_gravity": int(has.sum()), "photos_used_in_fit": int(used.sum()),
            "scatter_per_photo_deg": sol["sigma"],
            "mirror_sense_s": sol["s"], "altitude_term_k": sol["k"],
            "jupiter_highest_at_on_2023_12_03": f"{int(T0 * 24):02d}:{(T0 * 24 % 1) * 60:04.1f}",
            "jupiter_highest_err_min": float(e[0] * 1440),
            "jupiter_declination_deg": float(dec), "jupiter_declination_err_deg": float(e[1]),
            "jupiter_drift_min_per_day": float(drift), "jupiter_drift_err": float(e[3]),
            "candidates": [{"s": c_["s"], "k": c_["k"], "rms_deg": round(c_["rms_clip30"], 2),
                            "above_horizon": c_["above_horizon"]} for c_ in sol["candidates"]],
        },
        "A_vs_B": {"rms_deg": float(np.sqrt(np.mean(resid_ab ** 2))),
                   "photos_disagree_over_3sigma": [s for s in stems if orient[s]["agree_sigma"] > 3]},
        "method_C_same_night_pairs": {"pairs": len(links), "agree_with_B_on_ends": int(agree_links)},
        "final": {"median_err_photo_deg": float(np.median([o["err_photo_deg"] for o in orient.values()])),
                  "photos_where_final_differs_from_A_over_3deg": {s: round(orient[s]["final_minus_A_deg"], 1)
                      for s in stems if abs(orient[s]["final_minus_A_deg"]) > 3},
                  "plusX_margin_min_sigma": float(min(o["sign_margin_sigma"] for o in orient.values())),
                  "photos_plusX_margin_below_3sigma": [s for s in stems if orient[s]["sign_margin_sigma"] < 3]},
        "site_30m": {"max_err_site_deg": float(max(abs(o["err_site_deg"]) for o in orient.values())),
                     "max_B_shift_deg": float(site_rel.max()), "declination_shift_deg": site_par["dec_deg"],
                     "highest_time_shift_min": site_par["transit_min"]},
        "clock_checks": clock_checks,
        "dots": {"band_half_width_rj": band, "strong_in_band": len(on), "strong_outside_band": len(off),
                 "band_rms_rj": float(np.sqrt(np.mean([p["Y_rj"] ** 2 for p in on]))),
                 "max_abs_X_rj_in_band": float(max(abs(p["X_rj"]) for p in on)),
                 "outside_band": [[p["photo"], p["X_rj"], p["Y_rj"]] for p in off]},
    }
    save_json(summary, OUT2 / "summary.json")
    print(json.dumps(summary, indent=1, ensure_ascii=False))

    final_rel = np.array([orient[s]["final_deg"] for s in stems]) - (D + 90)
    rotation_plot(t, rel_a, sig_a, has, pred_rel, sol, final_rel, OUT2 / "field_rotation.png")
    notebook_plot(recs, rows, orient, OUT2 / "notebook.png")
    strips(recs, det, scale, orient, OUT2 / "strips.jpg")


if __name__ == "__main__":
    main()
