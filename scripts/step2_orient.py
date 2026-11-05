"""Step 2: turn every photo so the dots lie along one horizontal line.

What Galileo noticed first: the little stars next to Jupiter are always on one
straight line through it. Every photo here was taken with the phone turned a
different way, so that line points in a different direction in each photo.

1. Line: the direction through Jupiter that passes closest to the most dots
   (brighter dots count more). Dots far off it are kept but flagged.
2. Turn: rotate each photo so the line is horizontal. Positions become
   X = distance along the line, Y = distance across it, both in Jupiter radii
   (step 1 scale).
3. Which end is which: the line has two ends. Photos of the same night are
   linked through their dot patterns (as in step 1, here up to 3 hours apart);
   the rotation found by the match tells which end of one photo's line is
   which end of the other's. Linked photos get a common direction.
   Between groups that are not linked, nothing in a single photo tells east
   from west without knowing where Jupiter stood in the sky, so each group
   keeps an arbitrary "+X" end (flagged). A later step can settle it from the
   motion of the dots.

Errors, kept separate:
  err_photo  scale (step 1) + dot centroid + Jupiter centre + line angle
  err_site   camera position within 30 m: nothing in this step depends on it
             (the line and the distances are measured inside the photo), so 0.
             It would only enter if the photos were turned to a sky frame
             (north up), which needs Jupiter's position in the sky.

Output (output/step2/):
  orientation.csv   per photo: line angle, group, sign, line thickness
  positions.csv     per dot: X, Y (Rj) and both errors
  notebook.png      Galileo-style sketch: one row per photo
  strips.jpg        the real photos turned and cut to a strip along the line
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, RAW, ImageOps, local_time, night_of, photo_list, save_json
from step1_scale import dot_vectors, match

OUT1, OUT2 = OUT / "step1", OUT / "step2"
MIN_SNR_LINE = 15       # dots used to find the line (weighted by brightness)
MAX_R = 35              # Rj: farther dots are foreground lights, not near Jupiter
MAX_GAP_MIN = 180       # same-night links for deciding which end is which
CENTROID_RJ = 0.05      # Jupiter centre + dot centroid floor (Rj)
LINE_THICK_RJ = 0.25    # measured rms distance of dots from the line (see summary.json)


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


def notebook_plot(recs, rows, orient, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(recs)
    fig, ax = plt.subplots(figsize=(10, 0.24 * n + 1.2))
    groups = sorted({orient[r["stem"]]["group"] for r in recs})
    multi = {g for g in groups if sum(orient[r["stem"]]["group"] == g for r in recs) > 1}
    cmap = plt.get_cmap("tab10")
    colors = {g: cmap(i % 10) for i, g in enumerate(sorted(multi))}
    for i, r in enumerate(recs):
        y = n - 1 - i
        ax.plot(0, y, "o", ms=7, color="k")
        g = orient[r["stem"]]["group"]
        for p in rows:
            if p["photo"] != r["stem"]:
                continue
            ms = 3 + min(p["snr"], 200) / 30
            if p["on_line"]:
                ax.plot(p["X_rj"], y, "*", ms=ms, color=colors.get(g, "0.3"))
            elif p["snr"] >= 40:                       # bright but off the line: kept, shown hollow
                ax.plot(p["X_rj"], y, "o", ms=ms * 0.7, mfc="none", mec="0.5", mew=0.8)
        ax.text(-31, y, r["stem"][2:].replace("T", " "), va="center", ha="right", fontsize=7, family="monospace")
        if g in multi:
            ax.text(31, y, f"G{g}", va="center", fontsize=7, color=colors[g])
    ax.set_xlim(-31, 31)
    ax.set_ylim(-1, n)
    ax.set_yticks([])
    ax.set_xlabel("position along the line (Jupiter radii)")
    ax.set_title("All photos turned so the dots lie on a horizontal line\n"
                 "same colour/label = same night, ends matched; grey = +X end not known yet; hollow = bright dot off the line", fontsize=9)
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
        dr.text((4, y0), f"{s}   group {o['group']}" + ("" if o["group_size"] > 1 else "  (+X end unknown)"),
                fill=(190, 190, 200), font=font)
        if o["theta_deg"] is None:
            continue
        im = ImageOps.exif_transpose(Image.open(RAW / r["file"])).convert("RGB")
        R = int(np.hypot(half_x, half_y) * rj) + 2
        crop = im.crop((int(j["x"]) - R, int(j["y"]) - R, int(j["x"]) + R, int(j["y"]) + R))
        ang = o["theta_deg"] + (180 if o["sign"] < 0 else 0)
        crop = crop.rotate(-ang, resample=Image.BICUBIC)   # PIL turns counter-clockwise: undo the line angle
        c = crop.size[0] / 2
        crop = crop.crop((int(c - half_x * rj), int(c - half_y * rj), int(c + half_x * rj), int(c + half_y * rj)))
        crop = crop.resize((W, H), Image.LANCZOS).point(lambda v: int(255 * (v / 255) ** 0.6))
        sheet.paste(crop, (0, y0 + lab_h))
        for k in range(-25, 26, 5):
            x = W / 2 + k * px_per_rj
            dr.line([(x, y0 + lab_h + H - 4), (x, y0 + lab_h + H)], fill=(90, 110, 160))
    sheet.save(path, quality=88)


def main():
    OUT2.mkdir(parents=True, exist_ok=True)
    recs = sorted(photo_list(), key=local_time)
    det, scale = load_step1()

    lines, pts_all = {}, {}
    for r in recs:
        s = r["stem"]
        pts = dots_rj(det[s], float(scale[s]["rj_px"]))
        pts_all[s] = pts
        lines[s] = fit_line(pts)

    signs, links = link_signs(recs, det, scale, lines)
    sizes = {}
    for g, _ in signs.values():
        sizes[g] = sizes.get(g, 0) + 1
    # number the linked groups 1, 2, ... first (in time order), single photos after them
    order = sorted(sizes, key=lambda g: (sizes[g] == 1, g))
    new = {g: i + 1 for i, g in enumerate(order)}
    signs = {s: (new[g], sg) for s, (g, sg) in signs.items()}
    sizes = {new[g]: n for g, n in sizes.items()}

    orient, rows = {}, []
    for r in recs:
        s = r["stem"]
        L = lines[s]
        g, sg = signs[s]
        orient[s] = {"group": g, "group_size": sizes[g], "sign": sg,
                     "theta_deg": None if L is None else float(np.degrees(L["theta"]))}
        if L is None:
            continue
        rot = np.exp(-1j * L["theta"]) * sg
        es = float(scale[s]["err_photo_pct"]) / 100
        for k, z, c in pts_all[s]:
            w = z * rot
            on = abs(w.imag) < 0.4 + 0.03 * abs(w)
            cen = CENTROID_RJ + c.get("size", 0) / float(scale[s]["rj_px"]) / max(c["snr"], 1) * 3
            err_x = float(np.hypot(abs(w.real) * es, cen))
            err_y = float(np.hypot(abs(w.real) * L["sig_theta"], cen))
            rows.append({"photo": s, "night": night_of(r), "local_time": local_time(r).isoformat(timespec="minutes"),
                         "dot": k, "X_rj": round(w.real, 3), "Y_rj": round(w.imag, 3),
                         "err_photo_X_rj": round(err_x, 3), "err_photo_Y_rj": round(err_y, 3),
                         "err_site_rj": 0.0, "snr": c["snr"], "on_line": bool(on),
                         "group": g, "plus_x_known_within_group": sizes[g] > 1})

    with open(OUT2 / "orientation.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["photo", "night", "line_angle_deg", "err_angle_deg", "dots_on_line", "line_thickness_rj",
                     "group", "group_size", "flip", "err_site_deg"])
        for r in recs:
            s, L, o = r["stem"], lines[r["stem"]], orient[r["stem"]]
            wr.writerow([s, night_of(r),
                         "" if L is None else round(np.degrees(L["theta"]), 2),
                         "" if L is None else round(np.degrees(L["sig_theta"]), 2),
                         0 if L is None else L["n_on_line"],
                         "" if L is None or L["thickness_rj"] is None else round(L["thickness_rj"], 3),
                         o["group"], o["group_size"], o["sign"] < 0, 0.0])
    with open(OUT2 / "positions.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    with open(OUT2 / "links.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(links[0]))
        wr.writeheader()
        wr.writerows(links)

    on = [p for p in rows if p["on_line"] and p["snr"] >= 40]
    off = [p for p in rows if not p["on_line"] and p["snr"] >= 40]
    thick = np.array([abs(p["Y_rj"]) for p in on])
    groups_multi = sorted({o["group"] for o in orient.values() if o["group_size"] > 1})
    summary = {
        "photos": len(recs),
        "strong_dots_on_line": len(on), "strong_dots_off_line": len(off),
        "line_half_thickness_rms_rj": float(np.sqrt(np.mean(thick ** 2))),
        "line_half_thickness_rms_rj_beyond_5rj": float(np.sqrt(np.mean(
            np.array([abs(p["Y_rj"]) for p in on if abs(p["X_rj"]) > 5]) ** 2))),
        "max_abs_X_rj": float(max(abs(p["X_rj"]) for p in on)),
        "linked_groups": len(groups_multi),
        "photos_in_linked_groups": sum(o["group_size"] > 1 for o in orient.values()),
        "end_links": len(links),
        "median_err_angle_deg": float(np.median([np.degrees(L["sig_theta"]) for L in lines.values() if L])),
    }
    save_json(summary, OUT2 / "summary.json")
    print(json.dumps(summary, indent=1))
    for p in off:
        print("  off-line strong dot:", p["photo"], p["X_rj"], p["Y_rj"], p["snr"])

    notebook_plot(recs, rows, orient, OUT2 / "notebook.png")
    strips(recs, det, scale, orient, OUT2 / "strips.jpg")


if __name__ == "__main__":
    main()
