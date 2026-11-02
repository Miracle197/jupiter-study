"""Download every photo listed in data/manifest.csv from the public Drive folder.

Shooting time comes from the Drive title (the photos carry no EXIF), e.g.
"2023/12/03/21:45.HEIC" -> local time 2023-12-03 21:45 US/Pacific.
Files are renamed to a safe name and their real format is detected from the
file header, because two "HEIC" files are actually JPEGs.

Output: data/raw/<name>, data/photos.csv
"""
import csv
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
URL = "https://drive.usercontent.google.com/download?id={id}&export=download&confirm=t"


def sniff(head: bytes) -> str:
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[4:8] == b"ftyp":
        return "heic"
    return "bin"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(ROOT / "data" / "manifest.csv")))
    out, seen = [], {}
    for r in rows:
        y, m, d, hm = r["drive_title"].split(".")[0].split("/")
        stem = f"{y}-{m}-{d}T{hm.replace(':', '')}"
        seen[stem] = seen.get(stem, 0) + 1
        if seen[stem] > 1:  # duplicate Drive title
            stem += f"_{seen[stem]}"
        existing = list(RAW.glob(stem + ".*"))
        if existing and existing[0].stat().st_size == int(r["drive_size"]):
            path = existing[0]
        else:
            for attempt in range(4):
                try:
                    data = urllib.request.urlopen(URL.format(id=r["drive_id"]), timeout=120).read()
                    break
                except Exception as e:  # network hiccup: back off and retry
                    print("retry", stem, e, file=sys.stderr)
                    time.sleep(2 ** (attempt + 1))
            else:
                raise SystemExit(f"failed to download {r['drive_title']}")
            path = RAW / f"{stem}.{sniff(data[:16])}"
            path.write_bytes(data)
        size = path.stat().st_size
        ok = size == int(r["drive_size"])
        print(f"{'OK ' if ok else 'BAD'} {path.name:28s} {size:>8d}")
        out.append({
            "file": path.name,
            "local_time": f"{y}-{m}-{d} {hm}",
            "format": path.suffix[1:],
            "bytes": size,
            "size_ok": ok,
            "drive_id": r["drive_id"],
            "drive_title": r["drive_title"],
        })
    with open(ROOT / "data" / "photos.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    bad = [o for o in out if not o["size_ok"]]
    print(f"{len(out)} files, {len(bad)} size mismatches")


if __name__ == "__main__":
    main()
