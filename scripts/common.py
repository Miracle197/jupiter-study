"""Shared helpers: the list of photos, what the camera recorded, decoded pixels.

The only input of the whole project is data/raw/ (58 phone photos taken through
a telescope eyepiece). Nothing here uses any outside astronomical data.
"""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "cache"          # decoded pixels, regenerated on demand (not in git)
OUT = ROOT / "output"


def _ratio(v):
    return float(v) if v is not None else None


def photo_list():
    """One record per photo: file, time, and what the camera wrote in EXIF."""
    recs = []
    for f in sorted(RAW.iterdir()):
        if f.suffix.lower() not in (".heic", ".jpg", ".jpeg"):
            continue
        im = Image.open(f)
        ex = im.getexif()
        ifd = ex.get_ifd(0x8769)
        w, h = ImageOps.exif_transpose(im).size
        name_time = datetime.strptime(f.stem[:15], "%Y-%m-%dT%H%M")
        exif_time = ifd.get(0x9003)
        exif_time = datetime.strptime(exif_time, "%Y:%m:%d %H:%M:%S") if exif_time else None
        recs.append({
            "stem": f.stem,
            "file": f.name,
            "w": w, "h": h,
            "camera": ex.get(0x0110),
            "exposure_s": _ratio(ifd.get(0x829A)),
            "iso": ifd.get(0x8827),
            "focal35_mm": ifd.get(0xA405),       # 35 mm-equivalent focal length, includes digital zoom
            "digital_zoom": _ratio(ifd.get(0xA404)) or (1.0 if ifd.get(0xA405) else None),
            "name_time": name_time.isoformat(timespec="minutes"),
            "exif_time": exif_time.isoformat() if exif_time else None,
        })
    return recs


def apple_gravity(path):
    """Gravity measured by the iPhone when the photo was taken, or None.

    Apple stores it in its EXIF maker note (tag 0x0008, "AccelerationVector"):
    three signed rationals in units of g, in the phone's frame (x to the right
    and y to the top of the phone held upright, z out of the screen).
    """
    import struct
    ifd = Image.open(path).getexif().get_ifd(0x8769)
    mn = ifd.get(0x927C)
    if not mn or not mn.startswith(b"Apple iOS"):
        return None
    n = struct.unpack(">H", mn[14:16])[0]
    for k in range(n):
        tag, typ, cnt, off = struct.unpack(">HHII", mn[16 + 12 * k:28 + 12 * k])
        if tag == 0x0008 and typ == 10 and cnt == 3:
            v = struct.unpack(">6i", mn[off:off + 24])
            return [v[0] / v[1], v[2] / v[3], v[4] / v[5]]
    return None


def local_time(rec):
    """Clock time of the photo (EXIF when the camera wrote it, else the file name)."""
    return datetime.fromisoformat(rec["exif_time"] or rec["name_time"])


def night_of(rec):
    """Observing night label: photos after midnight belong to the evening before."""
    t = local_time(rec)
    d = t.date() if t.hour >= 12 else (t.date().fromordinal(t.date().toordinal() - 1))
    return d.isoformat()


def relative_magnification(rec):
    """Pixels per unit angle on the sky, up to one unknown constant (the eyepiece).

    Phone held to an eyepiece: an object at angle a on the sky lands at
    f_phone * M_eyepiece * a on the sensor. The 35 mm-equivalent focal length
    already includes the phone's digital zoom and refers to the full 4032x3024
    frame. A square crop keeps the pixel size (short side stays 3024); a photo
    saved smaller (resized JPEG) shrinks in proportion to its short side.
    """
    if not rec["focal35_mm"]:
        return None
    return rec["focal35_mm"] * min(rec["w"], rec["h"]) / 3024.0


def gray(rec):
    """Brightness image (0-255 float), EXIF rotation applied. Cached as .npy."""
    CACHE.mkdir(exist_ok=True)
    p = CACHE / f"{rec['stem']}.gray.npy"
    if p.exists():
        return np.load(p).astype(float)
    im = ImageOps.exif_transpose(Image.open(RAW / rec["file"])).convert("L")
    a = np.asarray(im, np.uint8)
    np.save(p, a)
    return a.astype(float)


def rgb_preview(rec, long_side=1200):
    im = ImageOps.exif_transpose(Image.open(RAW / rec["file"])).convert("RGB")
    im.thumbnail((long_side, long_side))
    return im


def save_json(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1, ensure_ascii=False)
