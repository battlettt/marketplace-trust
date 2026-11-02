"""Price trend watch for one category, from pasted observations over time.

Direction comes from a least-squares line through (day, price):
- change per 30 days as a share of the median price is the drift;
- |drift| under 2% a month, or a noisy fit (R^2 under 0.25), reads as flat.
Prices with a condition are normalised to 'good' first so a run of worn
items does not look like a falling market.
"""

import statistics
from dataclasses import dataclass, field

from .condition import MULTIPLIER, grade_condition

MIN_OBSERVATIONS = 5
MIN_SPAN_DAYS = 14
FLAT_DRIFT = 0.02
MIN_R_SQUARED = 0.25

RISING, FALLING, FLAT = "rising", "falling", "flat"


@dataclass
class TrendReport:
    enough_data: bool
    count: int
    direction: str | None = None
    drift_per_month: float | None = None
    r_squared: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    median: float | None = None
    first_date: object = None
    last_date: object = None
    read: str = ""
    notes: list = field(default_factory=list)


def linear_fit(xs, ys):
    """Return (slope, r_squared) for a least-squares line."""
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in ys)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    if sxx == 0:
        return 0.0, 0.0
    slope = sxy / sxx
    r_squared = (sxy * sxy) / (sxx * syy) if syy else 1.0
    return slope, r_squared


def classify(drift, r_squared):
    if abs(drift) < FLAT_DRIFT or r_squared < MIN_R_SQUARED:
        return FLAT
    return RISING if drift > 0 else FALLING


def plain_read(direction, drift, r_squared):
    if direction == FALLING:
        return (f"Prices for this category are drifting down (about {abs(drift):.0%} a month). "
                "If you're not in a hurry, waiting may help, and sellers may accept lower offers.")
    if direction == RISING:
        return (f"Prices for this category are climbing (about {drift:.0%} a month). "
                "Waiting is unlikely to help; a fair deal now is reasonable.")
    if abs(drift) >= FLAT_DRIFT:
        return ("Prices move around but there's no consistent trend in this data. Timing won't "
                "help much; focus on condition and the fair range.")
    return ("Prices for this category are steady. There's no timing advantage; focus on "
            "condition and the fair range.")


def analyze_trend(observations):
    """Report direction, spread, and a plain-English read, or say data is too thin."""
    usable = [o for o in observations if not o.error and o.price and o.price > 0]
    notes = [f"Line {o.line_no} skipped: {o.error}." for o in observations if o.error]
    report = TrendReport(enough_data=False, count=len(usable), notes=notes)
    if not usable:
        report.read = "No usable observations were found, so there is no trend to report."
        return report

    prices = []
    normalised = False
    for o in usable:
        if o.condition_text:
            prices.append(o.price / MULTIPLIER[grade_condition(o.condition_text).grade])
            normalised = True
        else:
            prices.append(o.price)
    report.minimum, report.maximum = min(o.price for o in usable), max(o.price for o in usable)
    report.median = statistics.median(o.price for o in usable)
    dates = [o.when for o in usable]
    report.first_date, report.last_date = min(dates), max(dates)
    span = (report.last_date - report.first_date).days

    if len(usable) < MIN_OBSERVATIONS or span < MIN_SPAN_DAYS:
        report.read = (f"Only {len(usable)} observation(s) over {span} day(s). That's too few to call "
                       f"a trend (need at least {MIN_OBSERVATIONS} over {MIN_SPAN_DAYS}+ days), so no "
                       "direction is given.")
        return report

    xs = [(d - report.first_date).days for d in dates]
    slope, r_squared = linear_fit(xs, prices)
    drift = slope * 30 / statistics.median(prices)
    report.enough_data = True
    report.direction = classify(drift, r_squared)
    report.drift_per_month = drift
    report.r_squared = r_squared
    report.read = plain_read(report.direction, drift, r_squared)
    if normalised:
        report.notes.append("Prices with a condition were normalised to 'good' before fitting the trend.")
    return report
