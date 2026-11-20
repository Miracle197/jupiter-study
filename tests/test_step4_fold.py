"""Step 4 redo, part 3: find the period of the outermost body by folding."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from step4_fold import scan_periods  # noqa: E402


def test_period_found_from_dots_seen_only_near_the_turning_points():
    # a body swinging to 20 Rj with P = 16.7 d; photos about once a night at the same hour,
    # with gaps; we only "see" it when |X| > 15 (closer in it is mixed up with others)
    rng = np.random.default_rng(0)
    nights = np.array([0, 1, 2, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 19, 20, 21, 23, 28, 29, 30, 32, 33, 35, 36, 37, 38])
    t = nights + 0.9 + rng.normal(0, 0.03, len(nights))
    X = 20 * np.sin(2 * np.pi * t / 16.7 + 1.0) + rng.normal(0, 0.4, len(t))
    seen = np.abs(X) > 15
    res = scan_periods(t[seen], X[seen], t_empty=t[~seen], limit=15, err=0.5 + 0.05 * np.abs(X[seen]))
    assert abs(res["best"]["period_d"] - 16.7) < 0.3
    assert abs(res["best"]["reach_rj"] - 20) < 1.5


def test_empty_photo_penalises_a_swing_that_is_far_out_when_nothing_was_seen():
    from step4_fold import fit_one
    t = np.array([0.0, 1.0, 8.35, 9.35])            # dots near both turning points of P = 16.7
    X = 20 * np.sin(2 * np.pi * t / 16.7 + np.pi / 2)
    err = np.full(4, 0.5)
    # an empty photo half a turn after t=0 for P=16.7 is near X=-20 only if the body is there;
    # here we put an empty photo at a time the right swing is near 0, and the wrong one far out
    right = fit_one(1 / 16.7, t, X, err, t_empty=np.array([4.2]), limit=15)
    assert right["chi_empty"] < 0.5
    wrong = fit_one(1 / 16.7, t, X, err, t_empty=np.array([0.5]), limit=15)   # "nothing at the turning point"
    assert wrong["chi_empty"] > 5
