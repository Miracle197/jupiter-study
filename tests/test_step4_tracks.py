"""Step 4 redo, part 2: linking dots within one night into tracks (no bodies assumed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from step4_tracks import link_night  # noqa: E402


def photo(t, *dots):
    return {"t_h": t, "dots": [{"X": x, "Y": y} for x, y in dots]}


def test_two_bodies_moving_opposite_ways_are_two_tracks():
    # A moves +0.5 Rj/h at Y=+0.3, B moves -0.3 Rj/h at Y=-0.3; both stay apart
    night = [photo(t, (2 + 0.5 * t, 0.3), (-6 - 0.3 * t, -0.3)) for t in (0, 1, 2, 3)]
    tracks = link_night(night)
    assert len(tracks) == 2
    speeds = sorted(round(tr["speed"], 2) for tr in tracks)
    assert speeds == [-0.3, 0.5]
    assert all(len(tr["points"]) == 4 for tr in tracks)


def test_crossing_bodies_are_kept_apart_by_Y():
    # A and B pass the same X between photos; only Y tells them apart
    night = [photo(t, (-5 + 0.4 * t, 0.35), (-3 - 0.4 * t, -0.35)) for t in (0, 1, 2, 3, 4)]
    tracks = link_night(night)
    assert len(tracks) == 2
    for tr in tracks:
        ys = {round(p["Y"], 2) for p in tr["points"]}
        assert len(ys) == 1, "a track must not jump from one side of the line to the other"


def test_a_missing_dot_leaves_a_gap_not_a_new_track():
    # the second body is hidden in photo 2 (e.g. in Jupiter's glare); it comes back in photo 3
    night = [photo(0, (10, 0), (5, 0.4)), photo(1, (10.1, 0), (5.3, 0.4)),
             photo(2, (10.2, 0)), photo(3, (10.3, 0), (5.9, 0.4))]
    tracks = link_night(night)
    assert len(tracks) == 2
    assert sorted(len(tr["points"]) for tr in tracks) == [3, 4]


def test_a_dot_that_appears_once_is_a_one_point_track():
    night = [photo(0, (10, 0)), photo(1, (10.1, 0), (-12, 0.2)), photo(2, (10.2, 0))]
    tracks = link_night(night)
    assert sorted(len(tr["points"]) for tr in tracks) == [1, 3]
