"""Decode HEIC/JPEG photos to PNG (full size) and JPEG previews.

Output:
  data/processed/full/<stem>.png     full-resolution, EXIF orientation applied
  web/img/<stem>.jpg                 1200px-long-side preview used by the demo
"""
import csv
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()
ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "data" / "processed" / "full"
PREV = ROOT / "web" / "img"


def main():
    FULL.mkdir(parents=True, exist_ok=True)
    PREV.mkdir(parents=True, exist_ok=True)
    for r in csv.DictReader(open(ROOT / "data" / "photos.csv")):
        src = ROOT / "data" / "raw" / r["file"]
        stem = src.stem
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        im.save(FULL / f"{stem}.png")
        p = im.copy()
        p.thumbnail((1200, 1200))
        p.save(PREV / f"{stem}.jpg", quality=85)
        print(stem, im.size)


if __name__ == "__main__":
    main()
