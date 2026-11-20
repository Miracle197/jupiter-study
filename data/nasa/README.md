# NASA data (used only by `scripts/check_nasa.py`)

Steps 1–5 of the project never read these files. They are used once, at the end, to check
how accurate the photo-only results are.

- Source: NASA JPL Horizons system (https://ssd.jpl.nasa.gov/horizons/), light-time corrected
  vectors of Jupiter and its four large moons as seen from the observing site in
  `data/observer.json`, projected onto the sky.
- Downloaded for the earlier version of this project by `scripts/04_ephemeris.py` on the `main`
  branch (commit `3f9e345`), copied here unchanged. This session's machine could not reach
  Horizons, so they were not downloaded again.
- Units: Jupiter equatorial radii (71,492 km). X along Jupiter's equator on the sky, + toward
  celestial east; Y along Jupiter's projected spin axis, + toward Jupiter's north; D depth,
  + farther than Jupiter.
- `ephemeris_hourly.json`: every hour from 2023-12-03 00:00 UT, 985 points.
  `ephemeris_photos.json`: at each photo's time, with Jupiter's altitude, azimuth, parallactic
  angle and the moons' status. It uses the file-name time for 2024-01-10T1811 (18:11); the
  camera clock says 20:11, so `check_nasa.py` interpolates the hourly series at the camera
  times instead (cubic; it reproduces the per-photo values to 1e-4 Rj).
