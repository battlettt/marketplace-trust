from datetime import date, timedelta

from marketplace_trust.parsing import parse_observations
from marketplace_trust.trend import FALLING, FLAT, RISING, analyze_trend, classify, linear_fit


def series(prices, step_days=30, condition=""):
    start = date(2026, 1, 1)
    lines = [f"{(start + timedelta(days=i * step_days)).isoformat()} | ${p} | {condition}"
             for i, p in enumerate(prices)]
    return parse_observations("\n".join(lines))


def test_linear_fit_exact_line():
    slope, r2 = linear_fit([0, 1, 2, 3], [10, 12, 14, 16])
    assert slope == 2 and r2 == 1.0


def test_falling_direction_and_read():
    report = analyze_trend(series([400, 380, 360, 340, 320, 300]))
    assert report.enough_data and report.direction == FALLING
    assert report.drift_per_month < -0.02
    assert "waiting may help" in report.read


def test_rising_direction_and_read():
    report = analyze_trend(series([300, 310, 325, 335, 350, 360]))
    assert report.direction == RISING
    assert "climbing" in report.read and "waiting may help" not in report.read


def test_flat_direction():
    report = analyze_trend(series([300, 302, 299, 301, 300, 298]))
    assert report.direction == FLAT
    assert "steady" in report.read


def test_noisy_data_is_flat_not_invented_trend():
    report = analyze_trend(series([300, 420, 260, 410, 250, 380, 240, 390]))
    assert report.direction == FLAT
    assert report.r_squared < 0.25


def test_classify_thresholds():
    assert classify(-0.05, 0.9) == FALLING
    assert classify(0.05, 0.9) == RISING
    assert classify(0.01, 0.9) == FLAT
    assert classify(-0.05, 0.1) == FLAT


def test_spread_min_max_median():
    report = analyze_trend(series([400, 380, 360, 340, 320, 300]))
    assert (report.minimum, report.maximum, report.median) == (300, 400, 350)
    assert report.count == 6


def test_too_few_observations_says_so():
    report = analyze_trend(series([400, 300, 200]))
    assert not report.enough_data and report.direction is None
    assert "too few" in report.read
    assert report.minimum == 200  # spread is still reported


def test_too_short_a_time_span_says_so():
    report = analyze_trend(series([400, 380, 360, 340, 320, 300], step_days=1))
    assert not report.enough_data and "too few" in report.read


def test_no_usable_observations():
    report = analyze_trend(parse_observations("2026-01-01 | n/a\n"))
    assert report.count == 0 and "No usable observations" in report.read
    assert report.notes


def test_condition_normalisation_prevents_fake_falling_trend():
    obs = parse_observations("2026-01-01 | $115 | like new\n2026-02-01 | $100 | good\n"
                             "2026-03-01 | $115 | like new\n2026-04-01 | $82 | fair\n"
                             "2026-05-01 | $100 | good\n2026-06-01 | $82 | fair\n")
    report = analyze_trend(obs)
    assert report.direction == FLAT
    assert any("normalised" in n for n in report.notes)
