"""Build the demo page's data from steps 1-3 (everything comes from the photos).

Output (demo/):
  data.json            numbers for every chart and every photo
  view.html            the page with its own head, for viewing through a local server
  img/<photo>.jpg      the original photo, small
  src/<photo>.jpg      the original photo around Jupiter (not turned), with confirmed dots in data.json
  strip/<photo>.jpg    the photo turned so the line is horizontal, cut to a strip
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
STRIP_HALF_X, STRIP_HALF_Y, STRIP_PX_PER_RJ = 26, 3.5, 20
SRC_HALF_RJ, SRC_PX = 28, 720          # source-photo cut-out: +-28 Rj around Jupiter, shown 720 px wide
T_REF = datetime(2023, 12, 3)


def rows(path):
    return list(csv.DictReader(open(path)))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    (DEMO / "img").mkdir(parents=True, exist_ok=True)
    (DEMO / "strip").mkdir(parents=True, exist_ok=True)
    (DEMO / "src").mkdir(parents=True, exist_ok=True)
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
                "clock": s2["clock_checks"], "band": s2["dots"]},
        "bodies": bodies,
        "motion": {k: v for k, v in s3.items() if k != "bodies"},
        "strip": {"half_x": STRIP_HALF_X, "half_y": STRIP_HALF_Y, "px_per_rj": STRIP_PX_PER_RJ},
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
    small = im.copy()
    small.thumbnail((420, 420))
    small.save(DEMO / "img" / f"{rec['stem']}.jpg", quality=80)
    b = src_box(det, rj)
    cut = im.crop((int(round(b["x0"])), int(round(b["y0"])), int(round(b["x0"] + b["size"])), int(round(b["y0"] + b["size"]))))
    cut = cut.resize((SRC_PX, SRC_PX), Image.LANCZOS).point(lambda v: int(255 * (v / 255) ** 0.7))
    cut.save(DEMO / "src" / f"{rec['stem']}.jpg", quality=80)
    j = det["jupiter"]
    R = int(np.hypot(STRIP_HALF_X, STRIP_HALF_Y) * rj) + 2
    crop = im.crop((int(j["x"]) - R, int(j["y"]) - R, int(j["x"]) + R, int(j["y"]) + R))
    crop = crop.rotate(-angle, resample=Image.BICUBIC)
    cc = crop.size[0] / 2
    crop = crop.crop((int(cc - STRIP_HALF_X * rj), int(cc - STRIP_HALF_Y * rj),
                      int(cc + STRIP_HALF_X * rj), int(cc + STRIP_HALF_Y * rj)))
    W, Hh = 2 * STRIP_HALF_X * STRIP_PX_PER_RJ, int(2 * STRIP_HALF_Y * STRIP_PX_PER_RJ)
    crop = crop.resize((W, Hh), Image.LANCZOS).point(lambda v: int(255 * (v / 255) ** 0.6))
    crop.save(DEMO / "strip" / f"{rec['stem']}.jpg", quality=78)


if __name__ == "__main__":
    main()
