# jupiter-study

**English** · [中文](README.zh-CN.md)

Analysis of Jupiter's Galilean moons from 58 phone photos taken through a telescope eyepiece
(2023-12-03 to 2024-01-11, 31 nights, Riverside, CA). Every photo's moons are identified, converted to
coordinates in Jupiter radii (Rj), compared with the NASA JPL Horizons ephemeris, and shown in an
interactive bilingual web demo (photo viewer + 3D model + charts).

**Live demo:** <https://claude.ai/artifact/Ns4TTLjMFeWVSMh17i4Xvv> (add `#en` or `#zh` to the link to pick the language; the page also has a language button).

## Results

| Quantity | From the photos | True value |
|---|---|---|
| Io period | 1.768 ± 0.001 d | 1.769 d |
| Europa period | 3.551 ± 0.002 d | 3.551 d |
| Ganymede period | 7.149 ± 0.006 d | 7.155 d |
| Callisto period | 16.70 ± 0.03 d | 16.69 d |
| Kepler's third law slope, log a / log P | 0.671 | 2/3 |
| Jupiter's mass (glare-corrected) | 1.80 × 10²⁷ kg | 1.90 × 10²⁷ kg |

- 186 moon positions identified (219 were predicted visible; most of the rest sit too close to Jupiter's glare).
- Angles between moons: a single photo measures them to about ±3.6°. That confirms the four moons are nearly coplanar, but it cannot resolve the < 0.5° differences between their orbits.
- Photo times: the file names, read as Pacific Standard Time, fit the ephemeris best with a shift of only +5 minutes.
- Every photo is mirrored, and within a night the image turns by "parallactic angle + altitude". Both point to an **alt-azimuth mount with a star diagonal**. From the photo orientation alone the site was estimated at 32–41° N, 114–121° W; the real site (33.98° N, 117.31° W) falls inside that range.

## Galileo mode: no ephemeris

What if you were the first to see these dots, as Galileo was in January 1610, and did not know they were moons?
`scripts/07_galileo.py` repeats the analysis using only the photos and their times. The ephemeris is used only at the end, to grade the result.

1. **They belong to Jupiter**: keep only dots on one line through Jupiter (203 of 536 candidate dots).
2. **Ruler**: Jupiter's disk, as Galileo measured in Jupiter diameters.
3. **Count them**: distances pile up at each body's greatest elongation. Four peaks (4.5 / 7.4 / 11.7 / 19.1 Rj) mean four bodies, numbered I–IV from the inside out.
4. **Periods**: sine fits from the outermost ring inward, then a search in which each ring keeps the period that best explains all dots. Once-a-night photos make a period and its "one extra turn per day" aliases look alike. The nights with 8 photos (8 and 9 January) tell them apart.
5. **Kepler's third law**: slope 0.661 (theory 2/3).

Two versions:
- **Standard (east known):** every Galileo sketch marks east and west. Our photographer did not record it, so that one fact per photo is borrowed from the calibration.
- **Challenge (east unknown):** each night's east/west orientation is searched together with the orbits. It was right on 98% of nights.

| Ring | Standard | Challenge | True |
|---|---|---|---|
| I | 1.768 d | 1.768 d | 1.769 d (Io) |
| II | 3.550 d | 3.550 d | 3.551 d (Europa) |
| III | 7.144 d | 7.145 d | 7.155 d (Ganymede) |
| IV | 16.678 d | 16.678 d | 16.689 d (Callisto) |

Of the dots on the line, 146 went to the right moon, 12 to the wrong one, and 23 noise dots were taken for moons.

## Layout

```
data/manifest.csv          Drive file IDs, original names, sizes
data/raw/                  original photos (HEIC/JPEG; file name = local time)
data/photos.csv            download log and parsed capture times
data/observer.json         observing site
data/detections.json       Jupiter and candidate dots per photo
data/ephemeris_*.json      JPL Horizons ephemeris (photo times + hourly)
data/positions.csv         each identified moon: pixels, self-calibrated Rj, ephemeris-aligned Rj, ephemeris
data/photo_fits.json       per-photo scale, rotation, mirror flip, glare factor
data/results.json          period fits, Kepler, angles, time check, field rotation
scripts/01_download.py ... 06_analysis.py   pipeline (run 07 before 06)
scripts/07_galileo.py      Galileo mode: finds the moons without any moon ephemeris
data/galileo.json          Galileo-mode results
tools/annotate.html        small tool for manual corrections (bilingual)
web/                       interactive demo (index.html + js/ + data.json + img/), Chinese/English
```

## Running

```bash
pip install -r requirements.txt
```

```bash
for s in 01_download 02_decode 03_detect 04_ephemeris 05_calibrate 07_galileo 06_analysis; do python3 scripts/$s.py; done
```

Step 3 (detection) takes 3–4 minutes; step 4 needs access to `ssd.jpl.nasa.gov`.

View the demo through a local web server (browsers block reading data.json from a file):

```bash
python3 -m http.server -d web 8000
```

Then open http://localhost:8000 (or http://localhost:8000/#en for English).

## Observing site

`data/observer.json` holds the site given by the photographer: 33° 58' 36.1" N, 117° 18' 37.2" W
(elevation ≈ 320 m, estimated). To change it, edit `lat_deg`, `lon_deg` (west is negative) and `elevation_m`,
then re-run steps 4–6. The site barely changes the moons' positions relative to Jupiter (< 0.001 Rj), but it sets
Jupiter's altitude and airmass weights and the image-rotation check.

## Manual corrections

From the repository root run `python3 -m http.server 8000`, open http://localhost:8000/tools/annotate.html,
click on the photo to place a moon, download `annotations.json` into `data/`, then re-run steps 5–6.

## Method

1. **Find the dots**: Jupiter is the brightest saturated blob; its disk edge is where the radial brightness falls fastest. Moons are local peaks after removing the glare; long streaks (diffraction spikes) are rejected.
2. **Identify the moons**: the ephemeris pattern is scaled and rotated (with one mirror setting for all photos) onto the photo to match the most dots.
3. **Two coordinate sets**:
   - self-calibrated (`X_self`): Jupiter's disk radius is the ruler and the moon line gives the direction. It does not use the ephemeris scale and feeds the periods and Kepler's law;
   - ephemeris-aligned (`X_fit`): the best ephemeris match, used for residuals and the demo overlays.
4. **Glare factor**: the overexposed Jupiter appears 17% larger than its true disk on average. This affects radii and mass only, not periods or the Kepler slope.
