import re

from marketplace_trust.analysis import analyze
from marketplace_trust.report import listing_report
from marketplace_trust.safety import CORE_CHECKLIST, PAYMENT_WARNINGS, checklist
from marketplace_trust.samples import LISTING_SAMPLES, read_sample

LINK_RE = re.compile(r"https?://|www\.\w", re.I)


def reports():
    for _, listing_file, comps_file in LISTING_SAMPLES:
        result = analyze(read_sample(listing_file), read_sample(comps_file))
        yield result, listing_report(result.listing, result.estimate, result.scam, result.strategy)


def bare_report(listing_text):
    result = analyze(listing_text)
    return listing_report(result.listing, result.estimate, result.scam, result.strategy)


def test_core_checklist_covers_required_points():
    text = " ".join(CORE_CHECKLIST).lower()
    for phrase in ("public place", "daylight", "bring someone", "verify the item works",
                   "matches the listing", "only after verification", "cash"):
        assert phrase in text, phrase
    warnings = " ".join(PAYMENT_WARNINGS).lower()
    for phrase in ("e-transfer", "in advance", "gift cards", "wire"):
        assert phrase in warnings, phrase


def test_checklist_always_starts_with_core_items():
    assert checklist()[:4] == CORE_CHECKLIST


def test_every_report_contains_checklist_and_payment_warnings():
    samples = [r for _, r in reports()] + [bare_report("Old chair, $20")]
    for report in samples:
        assert "MEETUP SAFETY CHECKLIST" in report
        assert "Meet in a public place, in daylight." in report
        assert "Bring someone with you" in report
        assert "Never e-transfer or send app payments in advance to a stranger." in report
        assert "Never pay with gift cards." in report
        assert "Never wire money" in report
        assert "Meetup rule:" in report.split("1. FAIR PRICE ESTIMATE")[0]


def test_sections_appear_in_required_order():
    for _, report in reports():
        positions = [report.index(h) for h in ("1. FAIR PRICE ESTIMATE", "2. SCAM CHECK",
                                               "3. NEGOTIATION COACH", "4. MEETUP SAFETY CHECKLIST")]
        assert positions == sorted(positions)


def test_payment_danger_is_at_the_top_of_scam_section_and_in_glance():
    for result, report in reports():
        if not result.scam.payment_signals:
            continue
        scam_section = report.split("2. SCAM CHECK")[1].split("3. NEGOTIATION COACH")[0]
        assert scam_section.index("PAYMENT SAFETY") < scam_section.index("Reasons, most serious first")
        assert "!! PAYMENT DANGER" in report.split("1. FAIR PRICE ESTIMATE")[0]
        break
    else:
        raise AssertionError("expected a sample with payment signals")


def test_report_contains_no_live_links_even_when_listing_has_them():
    report = bare_report("Title: Phone\nPrice: $100\nDescription: pay at https://pay.example.com "
                         "or www.example.net/checkout")
    assert not LINK_RE.search(report)


def test_report_never_encourages_risky_payment():
    risky = re.compile(r"\b(?:send|pay|transfer)\b[^.\n]{0,40}\b(?:deposit|gift card|wire|crypto|"
                       r"bitcoin|in advance|upfront)\b", re.I)
    for _, report in reports():
        # Quoted seller text (found: "...") is evidence, not advice, so it is removed first.
        advice = re.sub(r'found: "[^"]*"', "", report)
        for line in advice.splitlines():
            if risky.search(line):
                assert re.search(r"\b(?:never|asks? for|requests?|before you see|not)\b", line, re.I), line


def test_price_estimate_reasoning_is_shown_not_a_single_number():
    result, report = next(reports())
    section = report.split("1. FAIR PRICE ESTIMATE")[1].split("2. SCAM CHECK")[0]
    assert "Comparables used" in section
    assert "adjusted = price x condition (cond) x depreciation (depr) x region (regn)" in section
    assert "How each comparable was adjusted" in section
    assert "Regional index" in section and "depreciation" in section
    assert " to " in section.splitlines()[2]  # a range, not a point
