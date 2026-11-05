"""How the sky turns in the photos over a night (method B of step 2).

The phone recorded which way was down for every photo (iPhone gravity
sensor), and it was held almost upright every time. Yet the line of dots turns
a lot during a night, the same way every night. What turns is the sky: as the
Earth spins, Jupiter climbs and sinks, and the sky around it turns relative to
the horizon (the parallactic angle q). The telescope adds a turn that follows
how high it points (altitude h), as when the eyepiece sticks out sideways.

Model, for the angle of the line in a photo measured from the phone's own
"up" (gravity):
    angle = c + s * q(H) + k * h(H)            (s, k = +1 or -1, or k = 0)
    H = hour angle = 360 deg * 1.0027379 * (t - T0 - drift * days)
q and h follow from the observing latitude (the only use of the site), the
hour angle H, and Jupiter's declination dec. Unknowns fitted from the photos:
T0 (clock time Jupiter is highest), dec, drift (Jupiter's own slow motion
among the stars, minutes per day), c, and the choice of s and k. The fit
must keep Jupiter above the horizon in every photo (it was photographed).

1.0027379 is how much faster the stars turn than the clock (they come back
3.94 minutes earlier each day); nothing about Jupiter is assumed.
"""
import numpy as np
from scipy.optimize import least_squares

SIDEREAL = 1.00273790935
REF_DAY = 18.0          # drift is counted from this day (mid-series) to decorrelate it from T0


def q_h(t, T0, dec, drift, lat):
    """Parallactic angle and altitude (deg) at times t (days)."""
    H = 2 * np.pi * SIDEREAL * (t - T0 - drift * (t - REF_DAY) / 1440)
    d = np.radians(dec)
    q = np.arctan2(np.sin(H), np.tan(lat) * np.cos(d) - np.sin(d) * np.cos(H))
    h = np.arcsin(np.sin(lat) * np.sin(d) + np.cos(lat) * np.cos(d) * np.cos(H))
    return np.degrees(q), np.degrees(h)


def wrap180(x):
    """Angle difference for an undirected line: into [-90, 90)."""
    return (np.asarray(x) + 90) % 180 - 90


def model(p, s, k, t, lat):
    T0, dec, c, drift = p
    q, h = q_h(t, T0, dec, drift, lat)
    return c + s * q + k * h


def _fit_one(t, rel, lat, s, k, start=None):
    def res(p):
        return wrap180(rel - model(p, s, k, t, lat))

    if start is None:                      # coarse grid, then least squares
        best = None
        for T0 in np.arange(0, 1, 1 / 96):
            for dec in np.arange(-60, 61, 4):
                q, h = q_h(t, T0, dec, 0, lat)
                if h.min() < 0:
                    continue
                x = np.radians(2 * (rel - s * q - k * h))
                c = np.degrees(np.arctan2(np.sin(x).mean(), np.cos(x).mean())) / 2
                r = wrap180(rel - (c + s * q + k * h))
                cost = np.sum(np.minimum(r ** 2, 30 ** 2))
                if best is None or cost < best[0]:
                    best = (cost, [T0, dec, c, 0.0])
        if best is None:
            return None
        start = best[1]
    f = least_squares(res, start, loss="soft_l1", f_scale=8)
    return f.x, res(f.x)


def fit(t, rel, lat):
    """Try every (s, k); keep the best one with Jupiter above the horizon.

    Returns the chosen solution plus a table of all candidates.
    """
    cands = []
    for s in (1, -1):
        for k in (-1, 0, 1):
            out = _fit_one(t, rel, lat, s, k)
            if out is None:
                continue
            p, r = out
            _, h = q_h(t, p[0], p[1], p[3], lat)
            cands.append({"s": s, "k": k, "p": p, "rms_clip30": float(np.sqrt(np.mean(np.minimum(r ** 2, 900)))),
                          "above_horizon": bool(h.min() > 0)})
    cands.sort(key=lambda c: (not c["above_horizon"], c["rms_clip30"]))
    best = cands[0]
    s, k = best["s"], best["k"]
    # clean least-squares fit on the photos that agree (robust cut at 3.5 sigma)
    p = best["p"]
    for _ in range(3):
        r = wrap180(rel - model(p, s, k, t, lat))
        sig = 1.4826 * np.median(np.abs(r))
        ok = np.abs(r) < max(3.5 * sig, 6)
        f = least_squares(lambda pp: wrap180(rel[ok] - model(pp, s, k, t[ok], lat)), p)
        p = f.x
    r = wrap180(rel - model(p, s, k, t, lat))
    sigma = float(np.sqrt(np.sum(r[ok] ** 2) / (ok.sum() - 4)))
    cov = np.linalg.inv(f.jac.T @ f.jac) * sigma ** 2
    return {"s": s, "k": k, "p": p, "cov": cov, "sigma": sigma, "used": ok, "resid": r, "candidates": cands}


def leave_one_out(t, rel, lat, sol, has):
    """Prediction for each photo from a fit that does not use that photo."""
    pred, err = np.zeros(len(t)), np.zeros(len(t))
    s, k = sol["s"], sol["k"]
    for i in range(len(t)):
        m = sol["used"] & has
        m[i] = False
        f = least_squares(lambda pp: wrap180(rel[m] - model(pp, s, k, t[m], lat)), sol["p"])
        pred[i] = model(f.x, s, k, t[i:i + 1], lat)[0]
        # parameter uncertainty carried to this photo (numerical gradient)
        g = np.array([(model(f.x + dp, s, k, t[i:i + 1], lat)[0] - pred[i]) / 1e-6
                      for dp in np.eye(4) * 1e-6])
        err[i] = float(np.sqrt(sol["sigma"] ** 2 + g @ sol["cov"] @ g))
    return pred, err


def site_shift(t, rel, lat, sol, dlat):
    """Change of every predicted angle when the latitude moves by dlat (rad)."""
    s, k, m = sol["s"], sol["k"], sol["used"]
    out = []
    for d in (dlat, -dlat):
        f = least_squares(lambda pp: wrap180(rel[m] - model(pp, s, k, t[m], lat + d)), sol["p"])
        out.append(model(f.x, s, k, t, lat + d) - model(sol["p"], s, k, t, lat))
        out.append(np.array([f.x[1] - sol["p"][1], (f.x[0] - sol["p"][0]) * 1440]))
    shift = np.maximum(np.abs(out[0]), np.abs(out[2]))
    par = np.maximum(np.abs(out[1]), np.abs(out[3]))
    return shift, {"dec_deg": float(par[0]), "transit_min": float(par[1])}
