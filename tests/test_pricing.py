from datetime import date

from marketplace_trust.parsing import parse_comparables, parse_listing
from marketplace_trust.pricing import (DEFAULT_RATE, detect_category, estimate_fair_price,
                                       looks_like_same_item, nice_round)

REF = date(2026, 10, 28)


def listing(condition="good", region="Toronto", title="Widget Pro"):
    return parse_listing(f"Title: {title}\nPrice: $100\nCondition: {condition}\nLocation: {region}\n"
                         f"Listed: {REF.isoformat()}\n")


def estimate(comps_text, **kwargs):
    lst = kwargs.pop("lst", None) or listing()
    return estimate_fair_price(lst, parse_comparables(comps_text, REF), **kwargs)


def close(a, b, tol=0.01):
    return abs(a - b) <= tol


def test_comparables_same_condition_same_day_give_median():
    est = estimate("Widget Pro | $100 | good | 2026-10-28\n"
                   "Widget Pro | $110 | good | 2026-10-28\n"
                   "Widget Pro | $90 | good | 2026-10-28\n")
    assert est.mid == 100
    assert est.confidence == "medium"
    assert len(est.used) == 3
    assert est.low <= 92 and est.high >= 108  # at least +/-8%


def test_condition_adjusts_each_comparable_to_target_grade():
    est = estimate("Widget Pro | $115 | like new | 2026-10-28\n"
                   "Widget Pro | $82 | fair | 2026-10-28\n"
                   "Widget Pro | $62 | worn | 2026-10-28\n")
    for a in est.used:
        assert close(a.adjusted, 100), a.adjusted
    like_new = est.used[0]
    assert like_new.grade.grade == "like new" and close(like_new.condition_factor, 1 / 1.15)


def test_target_condition_scales_the_estimate():
    comps = "Widget Pro | $100 | good | 2026-10-28\n" * 3
    worn = estimate(comps, lst=listing(condition="worn"))
    assert close(worn.mid, 62)


def test_depreciation_over_time():
    est = estimate("Widget Pro | $100 | good | 2025-10-28\n" * 3, rate=0.20)
    a = est.used[0]
    assert a.age_days == 365
    assert close(a.depreciation_factor, 0.80)
    assert close(est.mid, 80)


def test_category_rate_used_by_default():
    lst = listing(title="iPhone 13 phone")
    assert detect_category(lst) == ("phone", 0.30)
    assert detect_category(listing(title="Widget Pro")) == ("general", DEFAULT_RATE)
    est = estimate("iPhone 13 | $100 | good | 2025-10-28\n" * 3, lst=lst)
    assert close(est.mid, 70)


def test_category_field_overrides_title():
    lst = parse_listing("Title: Widget\nCategory: Furniture\nPrice: $5")
    assert detect_category(lst) == ("furniture", 0.10)


def test_explicit_regional_index_adjusts_comparables():
    est = estimate("@region Toronto 1.10\n@region Halifax 0.90\n"
                   "Widget Pro | $90 | good | 2026-10-28 | Halifax\n" * 3)
    a = est.used[0]
    assert est.region_source == "explicit"
    assert close(a.region_factor, 1.10 / 0.90)
    assert close(est.mid, 110)


def test_derived_regional_index_is_shrunk_and_clamped():
    comps = ("Widget Pro | $120 | good | 2026-10-28 | Toronto\n" * 2
             + "Widget Pro | $80 | good | 2026-10-28 | Halifax\n" * 2)
    est = estimate(comps)
    assert est.region_source == "derived"
    # overall median 100; Toronto raw 1.20 -> shrunk 1.10; Halifax raw 0.80 -> shrunk 0.90
    assert est.region_index == {"toronto": 1.1, "halifax": 0.9}
    halifax = [a for a in est.used if a.comp.region == "halifax"][0]
    assert close(halifax.adjusted, 80 * 1.1 / 0.9)


def test_no_regional_data_means_no_adjustment():
    est = estimate("Widget Pro | $100 | good | 2026-10-28 | Toronto\n"
                   "Widget Pro | $100 | good | 2026-10-28 | Halifax\n"
                   "Widget Pro | $100 | good | 2026-10-28\n")
    assert est.region_index == {}
    assert all(a.region_factor == 1.0 for a in est.used)


def test_thin_data_widens_range_and_says_low_confidence():
    est = estimate("Widget Pro | $100 | good | 2026-10-28\n"
                   "Widget Pro | $100 | good | 2026-10-28\n")
    assert est.confidence == "low"
    assert close(est.low, 75) and close(est.high, 125)
    assert any("confidence is low" in n for n in est.notes)


def test_single_comparable_is_still_low_confidence():
    est = estimate("Widget Pro | $200 | good | 2026-10-28\n")
    assert est.confidence == "low" and est.mid == 200


def test_no_usable_comparables_gives_no_number():
    est = estimate("Something Else | $100 | good | 2026-10-28\n")
    assert not est.has_range and est.mid is None
    assert est.confidence == "none"
    assert est.comps[0].exclusion == "does not look like the same item"
    assert any("No usable comparables" in n for n in est.notes)


def test_exclusions_old_future_outlier_and_errors():
    est = estimate("Widget Pro | $100 | good | 2026-10-20\n"
                   "Widget Pro | $105 | good | 2026-10-20\n"
                   "Widget Pro | $95 | good | 2026-10-20\n"
                   "Widget Pro | $400 | good | 2026-10-20\n"
                   "Widget Pro | $100 | good | 2022-01-01\n"
                   "Widget Pro | $100 | good | 2026-12-01\n"
                   "Widget Pro | free? | good\n")
    reasons = {a.comp.line_no: a.exclusion for a in est.comps if not a.used}
    assert "outlier" in reasons[4]
    assert reasons[5] == "older than 3 years"
    assert reasons[6] == "dated after the reference date"
    assert reasons[7] == "no readable price"
    assert len(est.used) == 3


def test_high_confidence_needs_five_tight_comparables():
    est = estimate("".join(f"Widget Pro | ${p} | good | 2026-10-28\n" for p in (98, 100, 102, 99, 101)))
    assert est.confidence == "high"


def test_asking_position():
    est = estimate("Widget Pro | $200 | good | 2026-10-28\n" * 3)
    assert est.asking == 100 and est.asking_position() == "below"


def test_same_item_check():
    assert looks_like_same_item("Trek FX 3 hybrid", "trek fx3")
    assert not looks_like_same_item("Trek FX 3 hybrid", "Specialized Sirrus")


def test_nice_round_steps():
    assert nice_round(37.4) == 37
    assert nice_round(352) == 350
    assert nice_round(357.5) == 360
    assert nice_round(1234) == 1230
    assert nice_round(2612) == 2600
