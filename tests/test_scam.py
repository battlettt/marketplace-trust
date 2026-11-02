from datetime import date

from marketplace_trust.parsing import parse_comparables, parse_listing
from marketplace_trust.pricing import estimate_fair_price
from marketplace_trust.scam import (HIGH, LIKELY_SCAM, LOW, MEDIUM, NO_MAJOR, SUSPICIOUS, Signal,
                                    assess_listing, decide_verdict, defang)


def scan(description, location="Toronto", price=400, comps=None):
    listing = parse_listing(f"Title: Trek FX 3 bike\nPrice: ${price}\nLocation: {location}\n"
                            f"Listed: 2026-10-28\nDescription:\n{description}\n")
    estimate = None
    if comps:
        estimate = estimate_fair_price(listing, parse_comparables(comps), as_of=date(2026, 10, 28))
    return assess_listing(listing, estimate)


def titles(report):
    return [s.title for s in report.signals]


def find(report, category):
    return [s for s in report.signals if s.category == category]


CLEAN = "Good condition, recently serviced. Test rides welcome. Cash at pickup."
COMPS = "Trek FX 3 | $400 | good | 2026-10-28\n" * 4


def test_clean_listing_has_no_major_red_flags():
    report = scan(CLEAN, comps=COMPS)
    assert report.signals == []
    assert report.verdict == NO_MAJOR


# --- payment ---

def test_gift_cards_flagged_high():
    report = scan("Payment by Steam gift cards only.")
    signal = find(report, "payment")[0]
    assert signal.severity == HIGH and "gift" in signal.title.lower()
    assert signal.explanation


def test_wire_transfer_flagged_high():
    assert find(scan("Send it through Western Union please."), "payment")[0].severity == HIGH


def test_crypto_flagged_high():
    assert "crypto" in find(scan("I accept bitcoin or USDT."), "payment")[0].title.lower()


def test_etransfer_alone_is_medium():
    signal = find(scan("E-transfer or cash when you pick it up."), "payment")[0]
    assert signal.severity == MEDIUM


def test_etransfer_in_advance_is_high_twice():
    report = scan("Please e-transfer a deposit to hold it.")
    payment = find(report, "payment")
    assert [s.severity for s in payment] == [HIGH, HIGH]
    assert report.verdict == LIKELY_SCAM


def test_cash_before_seeing_flagged():
    report = scan("Send the cash before you see it, I'll leave it on the porch.")
    assert "before you see" in find(report, "payment")[0].title


def test_negated_deposit_is_not_flagged():
    assert find(scan("No deposit needed, pay when you pick it up."), "payment") == []


def test_first_come_first_served_with_cash_is_not_advance_payment():
    assert find(scan("Cash only, first come first served."), "payment") == []


# --- price ---

def test_far_below_fair_price_is_high():
    signal = find(scan(CLEAN, price=150, comps=COMPS), "price")[0]
    assert signal.severity == HIGH
    assert "$150" in signal.explanation and "$400" in signal.explanation


def test_well_below_fair_price_is_medium_and_suspicious():
    report = scan(CLEAN, price=250, comps=COMPS)
    assert find(report, "price")[0].severity == MEDIUM
    assert report.verdict == SUSPICIOUS


def test_fair_price_not_flagged():
    assert find(scan(CLEAN, price=380, comps=COMPS), "price") == []


def test_thin_data_downgrades_price_signal():
    signal = find(scan(CLEAN, price=150, comps="Trek FX 3 | $400 | good | 2026-10-28\n"), "price")[0]
    assert signal.severity == MEDIUM and "thin data" in signal.explanation


def test_no_estimate_skips_price_check_and_says_so():
    report = scan(CLEAN, price=1)
    assert find(report, "price") == []
    assert any("skipped" in n for n in report.notes)


# --- pressure ---

def test_deadline_competing_buyers_urgency_and_off_platform():
    report = scan("Today only! Lots of people interested. Need it gone asap. "
                  "WhatsApp me at 416-555-0123 or see www.example.com/pay")
    got = titles(report)
    assert any("deadline" in t for t in got)
    assert any("competing buyers" in t for t in got)
    assert any("Urgency" in t for t in got)
    off = [s for s in find(report, "pressure") if "off the platform" in s.title][0]
    assert off.severity == MEDIUM
    quoted = " ".join(off.evidence)
    assert "WhatsApp me at 416-555-0123" in quoted
    assert len(off.evidence) == 1  # nearby matches share one quote


def test_links_emails_and_phone_numbers_each_count_as_off_platform():
    for text in ("Details at www.example.com/item", "Email bob@example.org for info",
                 "Call 416 555 0123 for info"):
        report = scan(text)
        assert any("off the platform" in s.title for s in report.signals), text


# --- seller ---

def test_refusal_to_meet_is_high():
    signal = find(scan("Sorry, can't meet and no viewings."), "seller")[0]
    assert signal.severity == HIGH and "Refuses" in signal.title


def test_away_seller_with_agent_is_high():
    report = scan("I'm deployed overseas, my agent will ship it.")
    assert any(s.severity == HIGH and "away" in s.title for s in find(report, "seller"))


def test_shipping_only_and_no_history():
    report = scan("Shipping only. New account so no reviews yet.")
    got = titles(report)
    assert "Shipping only, no local pickup" in got
    assert "No seller history" in got


def test_mismatched_location():
    report = scan("I'm currently in Vancouver, so pickup is tricky.", location="Toronto, ON")
    signal = [s for s in find(report, "seller") if "Location" in s.title][0]
    assert "Vancouver" in signal.evidence[0] and "Toronto" in signal.evidence[0]


def test_matching_location_not_flagged():
    report = scan("Located in Toronto near the subway.", location="Toronto, ON")
    assert not any("Location" in t for t in titles(report))


def test_copied_template_text():
    report = scan("Kindly note this is 100% legit. Dear buyer, God bless.")
    signal = [s for s in find(report, "seller") if "scripted" in s.title][0]
    assert signal.severity == MEDIUM


def test_repeated_sentences_detected():
    sentence = "This bike is in amazing shape and rides great."
    report = scan(f"{sentence} {sentence}")
    assert any("(repeated)" in e for s in report.signals for e in s.evidence)


def test_condition_inconsistency_flagged_low():
    listing = parse_listing("Title: Trek FX 3\nPrice: $400\nCondition: like new\nDescription: frame is cracked")
    est = estimate_fair_price(listing, parse_comparables(COMPS), as_of=date(2026, 10, 28))
    report = assess_listing(listing, est)
    assert any(s.severity == LOW and "Condition claims" in s.title for s in report.signals)


# --- stolen photos / copied retail text ---

def test_stock_photo_language():
    signal = find(scan("Photos are from the internet, actual item may differ."), "photos")[0]
    assert signal.severity == MEDIUM and "stock" in signal.title


def test_photo_mismatch_admitted():
    report = scan("Colour is different from the photos, picture shows a different model.")
    assert any("don't match" in s.title for s in find(report, "photos"))


def test_retail_copy_needs_two_markers():
    assert find(scan("Free shipping."), "photos") == []
    report = scan("Free shipping. In stock. Manufacturer warranty. Key features: fast.")
    assert "retail" in find(report, "photos")[0].title


# --- verdict and ordering ---

def sig(severity, category="seller"):
    return Signal(severity, category, "t", "e")


def test_verdict_rules():
    assert decide_verdict([])[0] == NO_MAJOR
    assert decide_verdict([sig(LOW)])[0] == NO_MAJOR
    assert decide_verdict([sig(MEDIUM, "payment")])[0] == NO_MAJOR
    assert decide_verdict([sig(MEDIUM, "price")])[0] == SUSPICIOUS
    assert decide_verdict([sig(MEDIUM), sig(LOW)])[0] == SUSPICIOUS
    assert decide_verdict([sig(HIGH)])[0] == SUSPICIOUS
    assert decide_verdict([sig(HIGH), sig(HIGH)])[0] == LIKELY_SCAM
    assert decide_verdict([sig(HIGH), sig(MEDIUM), sig(LOW)])[0] == LIKELY_SCAM
    assert decide_verdict([sig(MEDIUM)] * 4) == (LIKELY_SCAM, 8)


def test_signals_ordered_most_serious_first_payment_leads_ties():
    report = scan("Today only. Can't meet. Pay with gift cards. Stock photo.")
    severities = [s.severity for s in report.signals]
    assert severities == sorted(severities, key={HIGH: 0, MEDIUM: 1, LOW: 2}.get)
    assert report.signals[0].category == "payment"
    assert report.reasons()[0].startswith("[HIGH]")


def test_evidence_links_are_defanged():
    report = scan("Pay here: https://pay.example.com/x")
    evidence = " ".join(e for s in report.signals for e in s.evidence)
    assert "https://" not in evidence and "hxxps://" in evidence
    assert defang("www.scam.com") == "www[.]scam[.]com"


def test_advance_payment_needs_payment_word_before_the_condition():
    assert find(scan("Please message before coming to pick up, cash only."), "payment") == []
    assert find(scan("Pay $50 to hold it for you."), "payment")[0].severity == HIGH
