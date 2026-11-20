"""Step 4 redo, part 5: joint fit helpers."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from step4_joint import fit_body, assign, tilt, rival_scores  # noqa: E402


def test_fit_body_recovers_period_and_reach():
    rng = np.random.default_rng(3)
    t = np.sort(rng.uniform(0, 40, 50)); X = 8 * np.sin(2 * np.pi * t / 3.55 + 0.4) + rng.normal(0, 0.2, 50)
    r = fit_body(1 / 3.55 + 0.0005, t, X)
    assert abs(1 / r["f"] - 3.55) < 0.005 and abs(np.hypot(r["a"], r["b"]) - 8) < 0.3


def test_two_bodies_predicted_on_the_same_spot_share_one_dot():
    B = [(1 / 1.77, 5.0, 0.0), (1 / 3.55, 0.0, 0.0)]          # second one sits at X = 0 always
    t = np.array([0.0]); X = np.array([0.1])                   # first one at X = 0 too at t = 0
    assert assign(B, t, X) == [[0, 1]]


def test_tilt_sees_a_circle_seen_almost_edge_on():
    t = np.linspace(0, 10, 60); f = 1 / 3.0
    Y = -0.4 * np.cos(2 * np.pi * f * t)                      # X = 8 sin(...), Y follows cos(...)
    r = tilt((f, 8.0, 0.0), t, Y)
    assert abs(r["B_rj"] + 0.4) < 0.01


def test_one_turn_more_per_day_rival_is_listed_with_a_positive_period():
    t = np.sort(np.random.default_rng(0).uniform(0, 30, 40)); X = 5 * np.sin(2 * np.pi * t / 1.77)
    periods = [r["period_d"] for r in rival_scores(1 / 1.77, t, X)]
    assert all(p > 0 for p in periods) and any(abs(p - 1 / abs(1 / 1.77 - 1)) < 0.05 for p in periods)
