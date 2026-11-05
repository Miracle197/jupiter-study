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
| 2 | Same orientation: line horizontal, same end on the same side in all photos | ✅ done |
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
- Note: the ±3.5% comes only from photo pairs close in time on the same night.
  Differences in focus and seeing between nights are not in it, so the real
  single-photo error may be larger. It can be measured again once the orbits
  are fitted (each body should always reach the same greatest distance).

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

A first observation: almost every dot stays within 26 Rj of Jupiter (one dot on Dec 12 is at 33 Rj).

## Step 2: same orientation

**Problem**: the phone was turned differently for each photo and the sky itself
turns during the night, so the line of dots points a different way in every
photo. The line also has two ends, which must be matched up.

**Galileo's first finding: the dots always lie on one straight line.** Three
independent methods find it and are compared:

| Method | How | Strength | Limit |
|---|---|---|---|
| A Dots | in each photo, the line through Jupiter closest to the dots | precise angle (median ±0.8°) | cannot tell the two ends apart |
| B Gravity + turning sky | the iPhone recorded which way was down; measured from there, the line turns the same way every night, so one fitted curve predicts its direction in every photo, **including which end is which** | puts every photo on the same end | ±3.9° per photo |
| C Same-night pairs | photos up to 3 h apart matched through their dot patterns | direct, reliable | only links photos of one night; used to check B |

![turning sky](output/step2/field_rotation.png)

**What B found** (left): the phone stayed almost upright (within about 10°),
yet the line turns by over 100° in a night, and every night of December and
January falls on the same curve. What turns is the sky: as Jupiter rises and
sets, the sky turns relative to the horizon (the parallactic angle), and the
telescope adds a turn that follows its altitude. Fitting the curve gives, from
the photos alone:

- Jupiter was highest at **21:20 ± 2 min** on Dec 3, declination **+13.8° ± 0.7°**, and came back 0.56 ± 0.11 min per day earlier than the stars (its own motion among them)
- the sense of the turning says the view is **not mirrored**; with the altitude term, it looks like a reflector with the eyepiece sticking out sideways
- the Jan 10 photo named 18:11 has camera time 20:11. With the camera time the prediction is 4° off; with the file-name time, 55°. **The camera time is right**

**Cross-checks**:
- A vs B (B from a fit without that photo): rms 5.1° over 58 photos, none beyond 3 sigma (right panel)
- C checks B: on all **32/32** same-night pairs, B matches the ends correctly
- every photo's +X end is known with a margin of at least 3.3 sigma
- the gravity axes are checked too: correct axes 3.8° rms, left-right flipped 7.1°, no gravity 5.3°

**Final direction**: the most likely angle given A's dots and B's prediction
together. A far dot fixes the angle much better than a near one (0.25 Rj off
the line is 0.7° at 20 Rj but 3.6° at 4 Rj), so dots are weighted by distance;
only bright dots are used (faint dots near Jupiter are mostly glare ripples).
B picks the +X end. Median error ±0.9°. Three photos change by 3–8° compared
with A alone (on Dec 5 the near and far dots disagree; B sides with the far one).

**A band, not a line**: once turned, the distances of the dots from the line
have a clear gap between 1.6 and 3.1 Rj. Within it (±2.3 Rj) are 185 bright
dots that move along with the whole system; outside, only 5 scattered dots.
The band's rms width is 0.41 Rj.

**Which end is +X**: +X is the same end of the sky in every photo. Whether it
is east or west depends on whether the telescope shows the sky upright or
upside down, which the photos do not show.

**Errors** (`output/step2/orientation.csv`, `positions.csv`):

| Source | Size | Why |
|---|---|---|
| Photo `err_photo_deg` | median ±0.9° | angle from A and B combined; positions add the step 1 scale error |
| Site `err_site_deg` | at most 6e-6° | B uses the latitude. Refitting with it moved by 30 m changes the predicted angle by at most 0.0002°, the declination by 0.0004°, the transit time by 0.0001 min; B is only part of the final angle |

**Galileo-style notebook** (one row per photo, +X the same end in all; hollow =
bright dot outside the band):

![notebook](output/step2/notebook.png)

Motion over several nights now shows: from Dec 3 to 5 the leftmost dot stays
at -20 to -25 Rj; on Jan 8–9 the dot at -19 Rj moves in to -13 Rj.

The real photos, turned and cut to a strip along the line: `output/step2/strips.jpg`.

## Layout

```
data/raw/                 the 58 original photos (file name = local time)
data/observer.json        observing site
scripts/common.py         photo list, EXIF, decoding
scripts/detect.py         find Jupiter and dots
scripts/step1_scale.py    step 1
scripts/step2_orient.py   step 2
scripts/field_rotation.py step 2 method B: the turning-sky model
output/step1/             step 1 results
  scale.csv               1 Rj in pixels for each photo, both error bars
  pairs.csv               same-night dot-pattern matches
  detections.json         Jupiter and dots in pixels
  ruler_check.png         the three rulers compared
  same_scale.jpg          all photos on one scale
output/step2/             step 2 results
  orientation.csv         per photo: methods A, B, final direction, both errors, Jupiter altitude
  positions.csv           X, Y (Rj) of every dot with both error bars
  links.csv               method C pairs and whether B agrees
  summary.json            turning-sky fit, method comparisons, site effect
  field_rotation.png      the turning-sky curve and A minus B
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
