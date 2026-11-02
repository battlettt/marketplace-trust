"""Plain-text report formatting. No analysis happens here, only layout.

Section order is fixed: fair price, scam check, negotiation, meetup safety,
and (when observations are given) the trend watch. An 'at a glance' header
puts the verdict and any payment danger first.
"""

import textwrap

from .negotiation import money
from .pricing import THIN_DATA, nice_round
from .safety import checklist, payment_warnings

WIDTH = 78
RULE = "=" * WIDTH


def wrap(text, indent=2, hang=None):
    hang = indent if hang is None else hang
    return textwrap.fill(text, WIDTH, initial_indent=" " * indent,
                         subsequent_indent=" " * hang, break_long_words=False)


def heading(title):
    return ["", RULE, title, RULE]


def format_range(estimate):
    return (f"{money(nice_round(estimate.low))} to {money(nice_round(estimate.high))} "
            f"(midpoint {money(nice_round(estimate.mid))}, confidence: {estimate.confidence})")


def glance(listing, estimate, scam_report):
    lines = heading(f"MARKETPLACE TRUST REPORT: {listing.title or 'untitled listing'}")
    lines.append("AT A GLANCE")
    if scam_report is not None:
        lines.append(f"  Scam verdict:  {scam_report.verdict}")
    if estimate is not None:
        fair = format_range(estimate) if estimate.has_range else "not available (no usable comparables)"
        lines.append(f"  Fair range:    {fair}")
    if listing.price is not None:
        position = estimate.asking_position() if estimate is not None else None
        suffix = f", {position} the fair range" if position else ""
        lines.append(f"  Asking price:  {money(listing.price)}{suffix}")
    if scam_report is not None and scam_report.payment_signals:
        lines.append(wrap("!! PAYMENT DANGER: " + "; ".join(s.title.lower() for s in scam_report.payment_signals)
                          + ".", hang=6))
    lines.append("  Meetup rule:   public place, daylight, bring someone, verify before paying.")
    return lines


def comparable_table(estimate):
    used = estimate.used
    lines = [f"  Comparables used ({len(used)}):",
             f"  {'#':>2} {'item':<20} {'price':>7} {'condition':<9} {'age':>5} "
             f"{'cond':>5} {'depr':>5} {'regn':>5} {'adjusted':>8}"]
    for n, a in enumerate(used, start=1):
        age = f"{a.age_days}d" if a.age_days is not None else "n/a"
        factors = " ".join(f"x{f:.2f}" for f in (a.condition_factor, a.depreciation_factor, a.region_factor))
        lines.append(f"  {n:>2} {a.comp.item[:20]:<20} {money(a.comp.price):>7} {a.grade.grade:<9} "
                     f"{age:>5} {factors} {money(a.adjusted):>8}")
    lines.append("  adjusted = price x condition (cond) x depreciation (depr) x region (regn)")
    return lines


def comparable_reasoning(estimate):
    lines = ["  How each comparable was adjusted:"]
    for n, a in enumerate(estimate.used, start=1):
        target = estimate.target_grade.grade
        parts = [f"condition {a.grade.explain()}"]
        if a.grade.grade != target:
            parts[0] += f", target is '{target}' so x{a.condition_factor:.2f}"
        if a.age_days is not None:
            parts.append(f"{a.age_days} days old at {estimate.rate:.0%}/yr so x{a.depreciation_factor:.2f}")
        else:
            parts.append("no date so no depreciation")
        if abs(a.region_factor - 1) > 1e-9:
            parts.append(f"region '{a.comp.region}' to '{estimate.target_region}' so x{a.region_factor:.2f}")
        lines.append(wrap(f"{n}. {a.comp.item}: " + "; ".join(parts) + ".", indent=4, hang=7))
    return lines


def price_section(estimate):
    lines = heading("1. FAIR PRICE ESTIMATE (with reasoning)")
    if estimate.has_range:
        lines.append(f"  Fair price range: {format_range(estimate)}")
    else:
        lines.append("  Fair price range: not available")
    if estimate.asking is not None:
        position = estimate.asking_position()
        lines.append(f"  Asking price:     {money(estimate.asking)}"
                     + (f" ({position} the fair range)" if position else ""))
    lines.append(wrap(f"Target condition: {estimate.target_grade.explain()}.", hang=4))
    lines.append(wrap(f"Category:         {estimate.category}, depreciation {estimate.rate:.0%} per "
                      f"year (reference date {estimate.reference_date.isoformat()})", hang=4))
    if estimate.region_index:
        index = ", ".join(f"{r} {v:.2f}" for r, v in sorted(estimate.region_index.items()))
        source = "set in the comparables file" if estimate.region_source == "explicit" else \
            "derived from the comparables (shrunk halfway to 1.00, capped at 0.85-1.15)"
        lines.append(wrap(f"Regional index:   {index}; {source}. Target region: "
                          f"'{estimate.target_region or 'unknown'}'.", hang=4))
    else:
        lines.append(wrap("Regional index:   none (needs 2+ comparables in each of 2+ regions, "
                          "or '@region' lines), so no regional adjustment.", hang=4))
    if estimate.used:
        lines.append("")
        lines += comparable_table(estimate)
        lines.append("")
        lines += comparable_reasoning(estimate)
        lines.append("")
        if len(estimate.used) >= THIN_DATA:
            lines.append(wrap("Range: middle half (interquartile) of the adjusted values around "
                              "their median, at least +/-8% wide.", hang=4))
        else:
            lines.append(wrap("Range: median of the adjusted values, widened to +/-25% because "
                              "the data is thin.", hang=4))
    excluded = [a for a in estimate.comps if not a.used]
    if excluded:
        lines.append(f"  Excluded comparables ({len(excluded)}):")
        for a in excluded:
            lines.append(wrap(f"- line {a.comp.line_no} '{a.comp.item[:40]}': {a.exclusion}", indent=4, hang=6))
    for note in estimate.notes:
        lines.append(wrap(f"Note: {note}", hang=4))
    return lines


def scam_section(scam_report):
    lines = heading(f"2. SCAM CHECK: {scam_report.verdict}")
    if scam_report.payment_signals:
        lines.append("  !! PAYMENT SAFETY: READ FIRST !!")
        for s in scam_report.payment_signals:
            lines.append(wrap(f"[{s.severity}] {s.title}", indent=4, hang=6))
        for warning in payment_warnings():
            lines.append(wrap(f"- {warning}", indent=4, hang=6))
        lines.append("")
    if not scam_report.signals:
        lines.append(wrap("No red flags found in the pasted text. Still follow the meetup checklist "
                          "below: scammers can write clean listings."))
    else:
        lines.append("  Reasons, most serious first:")
        for n, s in enumerate(scam_report.signals, start=1):
            lines.append(wrap(f"{n}. [{s.severity}] {s.title} ({s.category})", indent=4, hang=7))
            lines.append(wrap(s.explanation, indent=7))
            for quote in s.evidence[:3]:
                lines.append(wrap(f"found: {quote}", indent=7, hang=14))
    for note in scam_report.notes:
        lines.append(wrap(f"Note: {note}", hang=4))
    return lines


def negotiation_section(strategy):
    lines = heading("3. NEGOTIATION COACH")
    lines.append(wrap(strategy.headline))
    if strategy.opening is not None:
        lines.append(f"    Opening offer:   {money(strategy.opening)}")
        lines.append(f"    Target price:    {money(strategy.target)}")
        lines.append(f"    Walk-away price: {money(strategy.walk_away)} (don't pay more than this)")
    for reason in strategy.rationale:
        lines.append(wrap(f"- {reason}", indent=4, hang=6))
    if strategy.drafts:
        lines.append("")
        lines.append("  Message drafts:")
        for name, text in strategy.drafts.items():
            lines.append(f"    [{name}]")
            lines.append(wrap(text, indent=6))
    lines.append("")
    lines.append("  Tips:")
    for tip in strategy.tips:
        lines.append(wrap(f"- {tip}", indent=4, hang=6))
    lines.append(wrap("- Never pay before you have seen and checked the item, whatever the price.",
                      indent=4, hang=6))
    return lines


def safety_section(estimate, scam_report):
    lines = heading("4. MEETUP SAFETY CHECKLIST (always follow)")
    for item in checklist(estimate, scam_report):
        lines.append(wrap(f"[ ] {item}", hang=6))
    lines.append("  Payment safety:")
    for warning in payment_warnings():
        lines.append(wrap(f"- {warning}", indent=4, hang=6))
    return lines


def trend_section(trend):
    lines = heading("5. PRICE TREND WATCH")
    if trend.count:
        lines.append(f"  Observations:  {trend.count} from {trend.first_date.isoformat()} "
                     f"to {trend.last_date.isoformat()}")
        lines.append(f"  Spread:        min {money(trend.minimum)}, median {money(trend.median)}, "
                     f"max {money(trend.maximum)}")
    if trend.enough_data:
        lines.append(f"  Direction:     {trend.direction.upper()} ({trend.drift_per_month:+.1%} per month, "
                     f"fit R^2 {trend.r_squared:.2f})")
    else:
        lines.append("  Direction:     not enough data")
    lines.append(wrap(f"Read: {trend.read}", hang=4))
    for note in trend.notes:
        lines.append(wrap(f"Note: {note}", hang=4))
    return lines


def render(lines):
    return "\n".join(lines).strip("\n") + "\n"


def listing_report(listing, estimate, scam_report, strategy=None, trend=None):
    """Full report for a listing. strategy and trend sections are optional."""
    lines = glance(listing, estimate, scam_report)
    lines += price_section(estimate)
    lines += scam_section(scam_report)
    if strategy is not None:
        lines += negotiation_section(strategy)
    lines += safety_section(estimate, scam_report)
    if trend is not None:
        lines += trend_section(trend)
    return render(lines)


def trend_report(trend, category=""):
    title = f"PRICE TREND WATCH{': ' + category if category else ''}"
    lines = heading(title)
    lines += trend_section(trend)[4:]
    return render(lines)
