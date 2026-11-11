"""Build the demo page's data from steps 1-3 (everything comes from the photos).

Output (demo/):
  data.json            numbers for every chart and every photo
  view.html            the page with its own head, for viewing through a local server
  src/<photo>.jpg      the original photo around Jupiter (not turned), with confirmed dots in data.json
  native/<photo>.jpg   step 1: the same window of sensor pixels around Jupiter in every photo (sizes differ)
  norm/<photo>.jpg     step 1: every photo scaled so Jupiter has the same size
  jup/<photo>.jpg      step 1: close-up of Jupiter, to show where its edge was measured
The page itself is demo/index.html.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import field_rotation
from common import OUT, RAW, ROOT, ImageOps, photo_list

DEMO = ROOT / "demo"
SRC_HALF_RJ, SRC_PX = 28, 720          # source-photo cut-out: +-28 Rj around Jupiter, shown 720 px wide
NATIVE_WINDOW = 2400                   # step 1 "as taken": the same sensor-pixel window around Jupiter in every photo
NORM_HALF_RJ, NORM_PX = 34, 360        # step 1 "same Jupiter": +-34 Rj (room to apply the step 3 correction)
JUP_HALF_RJ, JUP_PX = 4, 360           # step 1 close-up of Jupiter's edge
T_REF = datetime(2023, 12, 3)


def rows(path):
    return list(csv.DictReader(open(path)))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    for sub in ("src", "native", "norm", "jup"):
        (DEMO / sub).mkdir(parents=True, exist_ok=True)
    recs = {r["stem"]: r for r in photo_list()}
    det = json.load(open(OUT / "step1" / "detections.json"))
    scale = {r["photo"]: r for r in rows(OUT / "step1" / "scale.csv")}
    orient = {r["photo"]: r for r in rows(OUT / "step2" / "orientation.csv")}
    s2 = json.load(open(OUT / "step2" / "summary.json"))
    s3 = json.load(open(OUT / "step3" / "summary.json"))
    bodies = json.load(open(OUT / "step3" / "bodies.json"))
    ps_rows = rows(OUT / "step3" / "photo_scale.csv")
    pscale = {r["photo"]: float(r["scale_correction"]) for r in ps_rows}
    pfitted = {r["photo"]: r["fitted"] == "True" for r in ps_rows}
    asg = {(r["photo"], int(r["dot"])): r["body"] for r in rows(OUT / "step3" / "assignments.csv")}
    stems = sorted(orient, key=lambda s: orient[s]["local_time"])

    # --- the turning-sky curve (method B of step 2), refitted the same way as step 2 ---
    lat = np.radians(json.load(open(ROOT / "data" / "observer.json"))["lat_deg"])
    t = np.array([(datetime.fromisoformat(orient[s]["local_time"]) - T_REF).total_seconds() / 86400 for s in stems])
    down = np.array([num(orient[s]["gravity_down_deg"]) if orient[s]["gravity_down_deg"] else -90.0 for s in stems])
    has = np.array([orient[s]["gravity_down_deg"] != "" for s in stems])
    rel_a = np.array([float(orient[s]["A_line_deg"]) for s in stems]) - (down + 90)
    sol = field_rotation.fit(t[has], rel_a[has], lat)
    T0, dec, c, drift = sol["p"]
    H = field_rotation.SIDEREAL * (t - T0 - drift * (t - field_rotation.REF_DAY) / 1440)
    H = (H - np.round(H)) * 24
    hh = np.linspace(H.min() - 0.3, H.max() + 0.3, 240)
    d, Hr = np.radians(dec), np.radians(hh * 15)
    q = np.degrees(np.arctan2(np.sin(Hr), np.tan(lat) * np.cos(d) - np.sin(d) * np.cos(Hr)))
    h = np.degrees(np.arcsin(np.sin(lat) * np.sin(d) + np.cos(lat) * np.cos(d) * np.cos(Hr)))
    curve = c + sol["s"] * q + sol["k"] * h
    final_rel = np.array([float(orient[s]["final_plusX_deg"]) for s in stems]) - (down + 90)
    at = np.interp(H, hh, curve)
    y = at + (final_rel - at + 180) % 360 - 180

    # --- dots per photo ---
    dots = {s: [] for s in stems}
    for r in rows(OUT / "step2" / "positions.csv"):
        if r["strong"] != "True":
            continue
        dots[r["photo"]].append({
            "X": float(r["X_rj"]), "Y": float(r["Y_rj"]),
            "eX": float(r["err_photo_X_rj"]), "eY": float(r["err_photo_Y_rj"]),
            "sY": float(r["err_site_Y_rj"]), "band": r["in_band"] == "True",
            "body": asg.get((r["photo"], int(r["dot"])), "") or "",
        })

    photos = []
    for i, s in enumerate(stems):
        r, o, sc = recs[s], orient[s], scale[s]
        photos.append({
            "id": s, "t": round(float(t[i]), 5), "time": o["local_time"], "night": o["night"],
            "camera": r["camera"] or "", "zoom35": r["focal35_mm"],
            "rj_px": float(sc["rj_px"]), "scale_err_pct": float(sc["err_photo_pct"]),
            "scale_site_pct": float(sc["err_site_pct"]), "linked": int(sc["photos_linked"]),
            "scale_fix": pscale.get(s, 1.0), "scale_fitted": pfitted.get(s, False),
            "gravity_down": num(o["gravity_down_deg"]),
            "A": float(o["A_line_deg"]), "A_err": float(o["A_err_deg"]),
            "B": float(o["B_plusX_deg"]), "B_err": float(o["B_err_deg"]),
            "final": float(o["final_plusX_deg"]), "final_err": float(o["err_photo_deg"]),
            "final_site": float(o["err_site_deg"]), "margin": float(o["plusX_margin_sigma"]),
            "alt": float(o["jupiter_altitude_deg"]), "par": float(o["parallactic_deg"]),
            "H": round(float(H[i]), 4), "rel": round(float(y[i]), 3), "has_gravity": bool(has[i]),
            "dots": dots[s],
            "src": src_box(det[s], float(sc["rj_px"])),
            "w": r["w"], "h": r["h"],
            "r_edge": round(det[s]["jupiter"]["r_edge"], 1), "r_blob": round(det[s]["jupiter"]["r_sat"], 1),
            "double": det[s]["jupiter"].get("double"),
            "native_window": round(NATIVE_WINDOW * min(r["w"], r["h"]) / 3024, 1),
            "pdots": [{"x": round(c["x"], 1), "y": round(c["y"], 1), "found_by": c.get("found_by", "detector")}
                      for c in det[s]["dots"] if c.get("confirmed")],
        })
        make_images(r, det[s], float(sc["rj_px"]), float(o["final_plusX_deg"]))

    ruler = [{"dots": float(p["ratio_dots"]), "edge": float(p["ratio_jupiter"]),
              "blob": float(p["ratio_jupiter_blob"]), "zoom": num(p["ratio_zoom"]), "a": p["a"], "b": p["b"]}
             for p in rows(OUT / "step1" / "pairs.csv")]

    data = {
        "photos": photos,
        "ruler": ruler,
        "ruler_summary": json.load(open(OUT / "step1" / "summary.json")),
        "sky": {"curve": [[round(a, 3), round(b, 3)] for a, b in zip(hh, curve)],
                "fit": s2["method_B_turning_sky"], "A_vs_B": s2["A_vs_B"],
                "C": s2["method_C_same_night_pairs"], "final": s2["final"], "site": s2["site_30m"],
                "clock": s2["clock_checks"], "band": s2["dots"],
                # the curve = c + s * (tilt of the sky) + k * (Jupiter's altitude), for the page to draw its two parts
                "model": {"lat_deg": float(np.degrees(lat)), "dec_deg": float(dec), "c_deg": float(c),
                          "s": int(sol["s"]), "k": int(sol["k"])}},
        "bodies": bodies,
        "motion": {k: v for k, v in s3.items() if k != "bodies"},
        "step1": {"native_window_px": NATIVE_WINDOW, "norm_half_rj": NORM_HALF_RJ, "jup_half_rj": JUP_HALF_RJ},
    }
    json.dump(data, open(DEMO / "data.json", "w"), ensure_ascii=False, separators=(",", ":"))
    # index.html is written for claude.ai, which adds the page head; view.html is the same page for a local server
    head = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n')
    (DEMO / "view.html").write_text(head + (DEMO / "index.html").read_text(encoding="utf-8") + "\n</body>\n</html>\n",
                                    encoding="utf-8")
    print("demo data:", DEMO / "data.json", f"{(DEMO / 'data.json').stat().st_size / 1024:.0f} KB")


def src_box(det, rj):
    """Square cut-out of the original photo around Jupiter (pixels of the photo, not turned)."""
    j = det["jupiter"]
    half = SRC_HALF_RJ * rj
    return {"x0": round(j["x"] - half, 1), "y0": round(j["y"] - half, 1), "size": round(2 * half, 1), "px": SRC_PX}


def make_images(rec, det, rj, angle):
    im = ImageOps.exif_transpose(Image.open(RAW / rec["file"])).convert("RGB")
    b = src_box(det, rj)
    square(im, b["x0"] + b["size"] / 2, b["y0"] + b["size"] / 2, b["size"] / 2, SRC_PX, 0.7).save(
        DEMO / "src" / f"{rec['stem']}.jpg", quality=80)
    j = det["jupiter"]
    # step 1 pictures: as taken (same sensor window), same Jupiter size, and a close-up of the edge
    win = NATIVE_WINDOW * min(rec["w"], rec["h"]) / 3024
    square(im, j["x"], j["y"], win / 2, 300, 0.7).save(DEMO / "native" / f"{rec['stem']}.jpg", quality=78)
    square(im, j["x"], j["y"], NORM_HALF_RJ * rj, NORM_PX, 0.7).save(DEMO / "norm" / f"{rec['stem']}.jpg", quality=78)
    square(im, j["x"], j["y"], JUP_HALF_RJ * rj, JUP_PX, 1.0).save(DEMO / "jup" / f"{rec['stem']}.jpg", quality=85)


def square(im, cx, cy, half, px, gamma):
    """Square cut-out centred on (cx, cy), half-width in photo pixels, resized to px.

    Only the part inside the photo is cut and shrunk; it is then placed on a
    black square. (Cutting the full square first can make a huge image when
    the square reaches far outside a zoomed-in photo.)
    """
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
    bx0, by0 = max(0, int(round(x0))), max(0, int(round(y0)))
    bx1, by1 = min(im.width, int(round(x1))), min(im.height, int(round(y1)))
    k = px / (2 * half)
    out = Image.new("RGB", (px, px), (0, 0, 0))
    if bx1 > bx0 and by1 > by0:
        part = im.crop((bx0, by0, bx1, by1))
        w, h = max(1, round((bx1 - bx0) * k)), max(1, round((by1 - by0) * k))
        out.paste(part.resize((w, h), Image.LANCZOS), (round((bx0 - x0) * k), round((by0 - y0) * k)))
    return out if gamma == 1.0 else out.point(lambda v: int(255 * (v / 255) ** gamma))


if __name__ == "__main__":
    main()
