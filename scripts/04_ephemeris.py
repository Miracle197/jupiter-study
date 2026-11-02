"""Predicted positions of the Galilean moons from JPL Horizons.

For each photo time (and hourly over the whole period, for the animation) we
fetch light-time corrected vectors of Jupiter and its four big moons as seen
from the observing site in data/observer.json, then project them onto the sky.

Coordinates are in Jupiter equatorial radii (Rj = 71,492 km):
  X  along Jupiter's equator as projected on the sky (+X toward celestial east)
  Y  along Jupiter's projected spin axis (+Y toward Jupiter's north pole)
  D  depth, + = farther than Jupiter (behind it), - = in front
Also gives the sky position angle of Jupiter's pole, Jupiter's altitude and the
parallactic angle at the site, and moon status (visible / occulted / transit /
eclipsed by Jupiter's shadow).

Output: data/ephemeris_photos.json, data/ephemeris_hourly.json
"""
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time

ROOT = Path(__file__).resolve().parent.parent
API = "https://ssd.jpl.nasa.gov/api/horizons.api"
RJ = 71492.0          # equatorial radius, km
FLAT = 66854.0 / RJ   # polar / equatorial radius
MOONS = {"Io": "501", "Europa": "502", "Ganymede": "503", "Callisto": "504"}
UTC_OFFSET_H = 8      # PST (Dec-Jan) -> UTC


def horizons_vectors(target, center, extra):
    q = {"format": "json", "COMMAND": f"'{target}'", "CENTER": f"'{center}'",
         "MAKE_EPHEM": "YES", "EPHEM_TYPE": "VECTORS", "VEC_TABLE": "1",
         "REF_PLANE": "FRAME", "REF_SYSTEM": "ICRF", "OUT_UNITS": "KM-S",
         "VEC_CORR": "LT", "CSV_FORMAT": "YES", "TIME_TYPE": "UT"}
    q.update(extra)
    url = API + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            txt = json.load(urllib.request.urlopen(url, timeout=120))["result"]
            break
        except Exception:
            time.sleep(2 ** (attempt + 1))
    else:
        raise SystemExit(f"Horizons request failed for {target}")
    body = txt.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    rows = [line.split(",") for line in body]
    jd = np.array([float(r[0]) for r in rows])
    xyz = np.array([[float(r[2]), float(r[3]), float(r[4])] for r in rows])
    return jd, xyz


def fetch(center, extra):
    out = {}
    for name, code in [("Jupiter", "599")] + list(MOONS.items()):
        jd, xyz = horizons_vectors(code, center, extra)
        out[name] = xyz
    return jd, out


def jupiter_pole(jd):
    T = (jd - 2451545.0) / 36525.0  # IAU 2015 pole of Jupiter
    ra = np.radians(268.056595 - 0.006499 * T)
    dec = np.radians(64.495303 + 0.002413 * T)
    return np.stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], -1)


def project(jd, obs, sun):
    """Return per-time frame info and per-moon X, Y, D, status."""
    J = obs["Jupiter"]
    dist = np.linalg.norm(J, axis=1)
    los = J / dist[:, None]
    z = np.array([0, 0, 1.0])
    e_east = np.cross(z, los)
    e_east /= np.linalg.norm(e_east, axis=1)[:, None]
    e_north = np.cross(los, e_east)
    p = jupiter_pole(jd)
    q = p - (p * los).sum(1)[:, None] * los
    q /= np.linalg.norm(q, axis=1)[:, None]
    ux = np.cross(q, los)  # projected equator, + toward east
    pa_pole = np.degrees(np.arctan2((q * e_east).sum(1), (q * e_north).sum(1))) % 360
    sub_obs_lat = np.degrees(np.arcsin(-(p * los).sum(1)))
    ang_radius = np.degrees(RJ / dist) * 3600
    s_hat = sun["Jupiter"] / np.linalg.norm(sun["Jupiter"], axis=1)[:, None]
    moons = {}
    for m in MOONS:
        r = obs[m] - J
        X, Y, D = (r * ux).sum(1) / RJ, (r * q).sum(1) / RJ, (r * los).sum(1) / RJ
        rs = sun[m] - sun["Jupiter"]
        along = (rs * s_hat).sum(1)
        perp = np.linalg.norm(rs - along[:, None] * s_hat, axis=1) / RJ
        on_disk = np.hypot(X, Y / FLAT) < 1.0
        status = np.where(on_disk & (D > 0), "occulted",
                 np.where(on_disk & (D < 0), "transit",
                 np.where((along > 0) & (perp < 1.0), "eclipsed", "visible")))
        moons[m] = {"X": X, "Y": Y, "D": D, "status": status,
                    "east": (r * e_east).sum(1) / RJ, "north": (r * e_north).sum(1) / RJ}
    return {"pa_pole": pa_pole, "sub_obs_lat": sub_obs_lat, "ang_radius_arcsec": ang_radius,
            "dist_km": dist, "los": los}, moons


def site_info(jd, los, site):
    loc = EarthLocation(lat=site["lat_deg"] * u.deg, lon=site["lon_deg"] * u.deg,
                        height=site["elevation_m"] * u.m)
    t = Time(jd, format="jd", scale="utc")
    ra = np.arctan2(los[:, 1], los[:, 0])
    dec = np.arcsin(los[:, 2])
    c = SkyCoord(ra=ra * u.rad, dec=dec * u.rad, frame="icrs")
    aa = c.transform_to(AltAz(obstime=t, location=loc))
    lst = t.sidereal_time("apparent", longitude=loc.lon).rad
    H = lst - ra
    phi = np.radians(site["lat_deg"])
    par = np.degrees(np.arctan2(np.sin(H), np.tan(phi) * np.cos(dec) - np.sin(dec) * np.cos(H)))
    alt = aa.alt.deg
    airmass = np.where(alt > 0, 1 / np.sin(np.radians(alt + 244 / (165 + 47 * np.maximum(alt, 0) ** 1.1))), np.nan)
    return alt, aa.az.deg, par, airmass


def main():
    site = json.load(open(ROOT / "data" / "observer.json"))
    center = "coord@399"
    geo = {"COORD_TYPE": "GEODETIC",
           "SITE_COORD": f"'{site['lon_deg'] % 360:.5f},{site['lat_deg']:.5f},{site['elevation_m'] / 1000:.4f}'"}

    photos = list(csv.DictReader(open(ROOT / "data" / "photos.csv")))
    utc = [datetime.strptime(p["local_time"], "%Y-%m-%d %H:%M") + timedelta(hours=UTC_OFFSET_H) for p in photos]
    jds = Time(utc, scale="utc").jd
    tl = {"TLIST": " ".join(f"'{j:.6f}'" for j in jds), **geo}
    jd, obs = fetch(center, tl)
    _, sun = fetch("500@10", {"TLIST": tl["TLIST"]})
    frame, moons = project(jd, obs, sun)
    alt, az, par, airmass = site_info(jd, frame["los"], site)

    out = {"site": site, "utc_offset_h": UTC_OFFSET_H, "photos": {}}
    for i, p in enumerate(photos):
        stem = Path(p["file"]).stem
        out["photos"][stem] = {
            "local_time": p["local_time"], "utc": utc[i].isoformat() + "Z", "jd": float(jd[i]),
            "pa_pole_deg": float(frame["pa_pole"][i]), "sub_obs_lat_deg": float(frame["sub_obs_lat"][i]),
            "jupiter_radius_arcsec": float(frame["ang_radius_arcsec"][i]),
            "alt_deg": float(alt[i]), "az_deg": float(az[i]), "parallactic_deg": float(par[i]),
            "airmass": None if np.isnan(airmass[i]) else float(airmass[i]),
            "moons": {m: {k: (str(v[i]) if k == "status" else float(v[i])) for k, v in moons[m].items()}
                      for m in MOONS},
        }
        print(f"{stem} alt={alt[i]:5.1f} PA={frame['pa_pole'][i]:6.1f} "
              + " ".join(f"{m[:2]}={moons[m]['X'][i]:+6.2f}{'' if moons[m]['status'][i]=='visible' else '(' + moons[m]['status'][i][0] + ')'}" for m in MOONS))
    json.dump(out, open(ROOT / "data" / "ephemeris_photos.json", "w"), indent=1)

    # hourly series for the animation
    rng = {"START_TIME": "'2023-12-03 00:00'", "STOP_TIME": "'2024-01-13 00:00'", "STEP_SIZE": "'1h'"}
    jd_h, obs_h = fetch(center, {**rng, **geo})
    _, sun_h = fetch("500@10", rng)
    fr_h, mo_h = project(jd_h, obs_h, sun_h)
    hourly = {"jd0": float(jd_h[0]), "step_h": 1, "n": len(jd_h),
              "pa_pole": np.round(fr_h["pa_pole"], 3).tolist(),
              "moons": {m: {k: np.round(mo_h[m][k], 4).tolist() for k in ("X", "Y", "D")} for m in MOONS}}
    json.dump(hourly, open(ROOT / "data" / "ephemeris_hourly.json", "w"))
    print("hourly samples:", len(jd_h))


if __name__ == "__main__":
    main()
