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
| 2 | Same orientation: turn the line of dots horizontal | ✅ done |
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

A first observation: almost every dot stays within 26 Rj of Jupiter (one dot on Dec 12 is at 33 Rj; see step 2).

## Step 2: same orientation

**Problem**: the phone was turned a different way for every photo, and the
view may be mirrored.

**Galileo's first finding: the dots always lie on one straight line.** In each
photo, find the line through Jupiter that passes closest to the dots (brighter
dots count more) and turn the photo so that line is horizontal. Each dot then
has X = distance along the line and Y = distance across it, in Jupiter radii.

**Results**:
- The line is very thin: 161 bright dots lie on it with an rms distance of only
  **0.25 Rj**, while they reach up to 26 Rj along it.
- The line angle is well measured: median ±0.8° per photo (up to ±3.6° for
  photos with a single dot).
- 29 bright dots are off the line (hollow circles). Most are only 0.5–1.3 Rj
  off (shake doubles or a slightly wrong Jupiter centre). A few may be
  **background stars**: the dot ~20 Rj out and 3 Rj off on Dec 5, and the dot
  at +5.5 Rj, 1.3 Rj off, in all three Jan 10 photos (it stays put for 4 hours
  and turns with the sky, so it is not a lens reflection). The 33 Rj dot on
  Dec 12 also needs a look. To be decided later from how they move.

**Which end is which**: the line has two ends. Photos of the same night (up to
3 hours apart) are paired through their dot patterns; the rotation of the
match says which end of one photo's line is which end of the other's. This
links 5 groups, 22 photos (Dec 3, Dec 4, Jan 8, Jan 9, Jan 10), each with a
common direction. Every other photo is alone in its group and its "+X" end is
arbitrary for now (flagged).

Without knowing where Jupiter was in the sky (that needs an ephemeris), a
single photo cannot tell east from west. I tried **atmospheric dispersion**
(the air acts like a prism: Jupiter's side toward the zenith turns bluer, the
side toward the horizon redder) to find "up". The red-blue offset is indeed
larger when Jupiter is low, but its direction is dominated by eyepiece colour
error and phone processing and does not agree between photos of the same
night, so it is not used. East/west is left for a later step, from the motion.

**Errors** (`output/step2/positions.csv`):

| Source | Why |
|---|---|
| Photo `err_photo_X_rj` / `err_photo_Y_rj` | step 1 scale + dot and Jupiter centring + line angle |
| Site `err_site_rj` | 0. This step only uses what is inside the photo (the line, the distances), which does not depend on where the camera stood. The site would only enter when turning photos to a "north up" sky frame, which also needs Jupiter's position in the sky |

**Galileo-style notebook** (one row per photo; same colour = same group,
common direction; grey = direction unknown; hollow = bright dot off the line):

![notebook](output/step2/notebook.png)

The dots already move within one night: on Jan 8 the leftmost dot goes from
-4 to -7.5 Rj, and on Jan 9 the two dots near +4 Rj close in on each other.

The real photos, turned and cut to a strip along the line: `output/step2/strips.jpg`.

## Layout

```
data/raw/                 the 58 original photos (file name = local time)
data/observer.json        observing site
scripts/common.py         photo list, EXIF, decoding
scripts/detect.py         find Jupiter and dots
scripts/step1_scale.py    step 1
scripts/step2_orient.py   step 2
output/step1/             step 1 results
  scale.csv               1 Rj in pixels for each photo, both error bars
  pairs.csv               same-night dot-pattern matches
  detections.json         Jupiter and dots in pixels
  ruler_check.png         the three rulers compared
  same_scale.jpg          all photos on one scale
output/step2/             step 2 results
  orientation.csv         line angle, group, flip for each photo
  positions.csv           X, Y (Rj) of every dot with both error bars
  links.csv               photo pairs used to match line ends
  notebook.png            Galileo-style notebook
  strips.jpg              photos turned, cut to strips
```

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/step1_scale.py      # about 2-3 minutes
.venv/bin/python scripts/step2_orient.py     # about 3-4 minutes
```

The first run decodes the photos into `cache/` (about 650 MB, not in git).

The previous version (analysis using NASA ephemerides) is in the git history
(commit `4d0c22b`).
