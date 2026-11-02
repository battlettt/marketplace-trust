import re
from datetime import date

from marketplace_trust.negotiation import coach, offer_numbers
from marketplace_trust.parsing import parse_comparables, parse_listing
from marketplace_trust.pricing import estimate_fair_price, nice_round
from marketplace_trust.scam import LIKELY_SCAM, NO_MAJOR, SUSPICIOUS, ScamReport

COMPS = "Widget Pro | $400 | good | 2026-10-28\n" * 4  # fair range 368 / 400 / 432


def run(price, verdict=NO_MAJOR, comps=COMPS):
    listing = parse_listing(f"Title: Widget Pro\nPrice: ${price}\nCondition: good\nListed: 2026-10-28")
    estimate = estimate_fair_price(listing, parse_comparables(comps), as_of=date(2026, 10, 28))
    return coach(listing, estimate, ScamReport(verdict=verdict, signals=[], score=0))


def test_offer_math_when_asking_above_fair_range():
    # walk = min(500, 432) -> 430; target = min(500, 400) = 400; opening = max(340, 331.2) = 340
    assert offer_numbers(500, 368, 400, 432)[:3] == (340, 400, 430)


def test_offer_math_when_asking_inside_fair_range():
    # walk = 420 (asking); target = 400; opening = 340
    assert offer_numbers(420, 368, 400, 432)[:3] == (340, 400, 420)


def test_opening_never_insults_below_ninety_percent_of_fair_low():
    opening, target, walk, _ = offer_numbers(1000, 900, 950, 1000)
    assert opening == 810  # max(0.85 * 950 = 807.5, 0.9 * 900 = 810) = 810
    opening, _, _, _ = offer_numbers(1000, 950, 960, 1000)
    assert opening == 860  # 0.9 * 950 = 855 -> 860 beats 0.85 * 960 = 816


def test_asking_below_fair_low_means_offer_asking():
    opening, target, walk, note = offer_numbers(300, 368, 400, 432)
    assert opening == target == walk == 300
    assert "verify" in note


def test_no_fair_range_falls_back_to_asking():
    opening, target, walk, note = offer_numbers(200)
    assert (opening, target, walk) == (170, 185, 200)
    assert "low confidence" in note


def test_no_asking_price_gives_no_numbers():
    assert offer_numbers(None)[:3] == (None, None, None)


def test_offers_always_ordered_and_never_above_asking():
    for asking in (55, 99, 310, 367, 401, 433, 777, 1999, 4321):
        for low, mid, high in ((50, 60, 70), (300, 400, 500), (1500, 2000, 2500)):
            opening, target, walk, _ = offer_numbers(asking, low, mid, high)
            assert opening <= target <= walk <= asking, (asking, low, opening, target, walk)
            assert walk <= nice_round(high)  # never pay above the top of the fair range


def test_coach_with_clean_listing_gives_numbers_and_three_drafts():
    strategy = run(500)
    assert (strategy.opening, strategy.target, strategy.walk_away) == (340, 400, 430)
    assert strategy.proceed
    assert set(strategy.drafts) == {"opening offer", "counter-offer", "walking away"}
    assert "$340" in strategy.drafts["opening offer"]
    assert "$400" in strategy.drafts["counter-offer"]
    assert "$430" in strategy.drafts["walking away"]
    assert any("capped" in r for r in strategy.rationale)


def test_coach_suspicious_keeps_numbers_but_warns():
    strategy = run(500, verdict=SUSPICIOUS)
    assert strategy.headline.startswith("Proceed only with caution")
    assert strategy.opening == 340


def test_coach_likely_scam_says_walk_away_with_no_numbers():
    strategy = run(150, verdict=LIKELY_SCAM)
    assert not strategy.proceed
    assert strategy.opening is None and strategy.walk_away is None
    assert "Do not negotiate" in strategy.headline
    assert list(strategy.drafts) == ["walking away"]


def test_drafts_are_short_polite_and_never_deceptive_or_pay_first():
    drafts = list(run(500).drafts.values()) + list(run(150, verdict=LIKELY_SCAM).drafts.values())
    banned = ["deposit", "e-transfer", "gift card", "wire", "crypto", "in advance", "another buyer",
              "other offer", "someone else", "send you the money", "pay now"]
    for text in drafts:
        lowered = text.lower()
        for word in banned:
            assert word not in lowered, (word, text)
        assert len(text) < 320
        assert re.search(r"thank", lowered)


def test_drafts_offer_payment_only_after_seeing_the_item():
    drafts = run(500).drafts
    assert "once I've checked it works" in drafts["opening offer"]
    assert "after seeing it in person" in drafts["counter-offer"]
