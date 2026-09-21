import random

import pytest

from app.application.services.candle_continuity import missing_open_ranges


def test_sparse_multi_year_interval_does_not_enumerate_empty_minutes():
    last = 10 * 366 * 24 * 60 * 60_000
    assert list(missing_open_ranges(iter([0, last]), start=0, end=last, step=60_000)) == [(60_000, last - 60_000)]


def test_exclusions_split_gaps_and_ignore_duplicates_and_off_grid_timestamps():
    assert list(missing_open_ranges([0, 0, 61, 300], start=0, end=600, step=60,
        excluded=[(120, 180), (180, 240), (420, 480)])) == [(60, 60), (360, 360), (540, 600)]


def test_unordered_input_is_rejected():
    with pytest.raises(ValueError, match="ordered"):
        list(missing_open_ranges([60, 0], start=0, end=120, step=60))


def test_empty_reversed_and_fully_excluded_ranges():
    assert list(missing_open_ranges([], start=120, end=60, step=60)) == []
    assert list(missing_open_ranges([], start=0, end=120, step=60, excluded=[(-60, 300)])) == []
    assert list(missing_open_ranges([], start=0, end=120, step=60)) == [(0, 120)]


def test_range_scan_matches_expected_missing_minutes_across_random_partitions():
    rng = random.Random(914)
    expected_grid = set(range(0, 6000, 60))
    for _ in range(200):
        actual = sorted(rng.sample(sorted(expected_grid), rng.randrange(101)))
        exclusions = [tuple(sorted(rng.sample(range(-120, 6300, 30), 2))) for _ in range(4)]
        expected = {value for value in expected_grid - set(actual)
                    if not any(start <= value <= end for start, end in exclusions)}
        result = list(missing_open_ranges(iter(actual), start=0, end=5940, step=60, excluded=exclusions))
        expanded = [value for start, end in result for value in range(start, end + 1, 60)]
        assert set(expanded) == expected
        assert len(expanded) == len(set(expanded))
