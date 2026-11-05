# jupiter-study: what if I were Galileo?

**English** · [中文](README.zh-CN.md)

All I have are 58 phone photos of Jupiter taken through a telescope eyepiece
(2023-12-03 to 2024-01-11, Riverside, California). Pretend I am the first
person to look at Jupiter through a telescope, in 1610: no NASA data, no idea
that the dots next to Jupiter are moons, no idea that they move back and forth
periodically. Work everything out from the photos, one step at a time.

**Allowed**: the photos, what the camera wrote into them (time, zoom), and the
observing site given by the photographer (`data/observer.json`: 33.976683° N,
117.310320° W, known to within 30 m).
**Not used**: any ephemeris, orbit, moon name, size of or distance to Jupiter.

## Progress

| Step | What | Status |
|---|---|---|
| 1 | Put every photo on the same scale | ✅ done |
| 2 | Put every photo in the same orientation (rotation, mirror) | next |
| 3 | … | |

## Step 1: same scale

**Problem**: every photo has a different magnification. Jupiter is 20 px in
radius in one photo and 130 px in another, so "how far is a dot from Jupiter"
cannot be compared directly.

**The ruler is Jupiter itself** (Galileo also measured in Jupiter diameters).
Every distance is in Jupiter radii (Rj). Jupiter and the dots are in the same
photo, so whatever changes the magnification changes both together.

**How big is Jupiter**: Jupiter is badly overexposed and the white blob grows
with exposure. So its edge is not the edge of the blob but the radius where the
ring-averaged brightness falls fastest: the blurred real limb.

**Checking the ruler with no outside data**: photos from the same night, taken
within 90 minutes, show almost the same pattern of dots. Lining up the two
patterns gives the true scale ratio of the two photos. Over 16 such pairs:

| Ruler | Difference from the dot patterns (rms) |
|---|---|
| Jupiter edge (steepest drop) | **5.3%** |
| Jupiter white blob | 6.7% |
| Phone zoom (EXIF) | 9.2% |

![ruler check](output/step1/ruler_check.png)

**Findings**:
- The phone zoom is not reliable. On Jan 9 the zoom stayed at 5x all night, yet
  the real scale changed by 0.89–1.20x between neighbouring photos (the phone
  moved or refocused). Two photos taken 1 second apart on Dec 24, same zoom,
  differ by about 10%.
- The Jupiter edge alone is good to about **±3.5%** per photo.
- Photos linked through their dots on the same night (22 of them) are averaged
  together, which brings their error down to 1.7–2.5%.

**Two separate error bars** (`output/step1/scale.csv`):

| Source | Size | Why |
|---|---|---|
| Photo `err_photo_pct` | 1.7–3.5% | Jupiter edge, dot positions, dots moving between the two photos |
| Site `err_site_pct` | < 1e-7 % | The scale is (dot offset angle) / (Jupiter radius angle), both seen from the same spot at the same moment. Moving the camera 30 m changes both almost equally; the ratio changes by less than 5e-10 |

The site error does not matter here; it is worked out separately in the
orientation step.

**Not known yet**: because Jupiter is overexposed, the steepest-drop edge may be
larger than the real edge by one fixed factor, the same for all photos. It does
not affect comparing photos or the periods to be found later, but it cannot be
pinned down without outside data.

**All photos on one scale** (blue rings = 5, 10, 15, 20, 25 Rj; yellow = dots
found; orientation not fixed yet):

![same scale](output/step1/same_scale.jpg)

A first observation: every dot stays within 25 Rj of Jupiter.

## Layout

```
data/raw/                 the 58 original photos (file name = local time)
data/observer.json        observing site
scripts/common.py         photo list, EXIF, decoding
scripts/detect.py         find Jupiter and dots
scripts/step1_scale.py    step 1
output/step1/             step 1 results
  scale.csv               1 Rj in pixels for each photo, both error bars
  pairs.csv               same-night dot-pattern matches
  detections.json         Jupiter and dots in pixels
  ruler_check.png         the three rulers compared
  same_scale.jpg          all photos on one scale
```

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/step1_scale.py      # about 2-3 minutes
```

The first run decodes the photos into `cache/` (about 650 MB, not in git).

The previous version (analysis using NASA ephemerides) is in the git history
(commit `4d0c22b`).
