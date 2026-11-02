"""Negotiation coach: offer strategy and short, honest message drafts.

Offer math (A = asking price, fair range = low / mid / high):
- Walk-away: never above the top of the fair range: min(A, high).
- Target:    the fair midpoint, or the asking price if that is lower: min(A, mid).
- Opening:   85% of target, but not below 90% of the fair low (no insulting
             lowballs), and never above the target.
- If A is already at or below the fair low, there is nothing to negotiate:
  offer the asking price and spend the effort on verifying the item.
- With no fair range, offers fall back to the asking price (85% / 92% / 100%)
  and the strategy says confidence is low.
- With a LIKELY SCAM verdict the coach recommends not proceeding at all.

All amounts are rounded with pricing.nice_round and kept in order:
opening <= target <= walk-away <= asking. The drafts never use invented
competing offers or other deception, and never offer to pay before seeing
the item.
"""

from dataclasses import dataclass, field

from .pricing import nice_round
from .scam import LIKELY_SCAM, SUSPICIOUS

OPENING_OF_TARGET = 0.85
OPENING_FLOOR_OF_LOW = 0.90
NO_DATA_OPENING = 0.85
NO_DATA_TARGET = 0.92


@dataclass
class Strategy:
    asking: float | None
    opening: float | None
    target: float | None
    walk_away: float | None
    proceed: bool
    headline: str
    rationale: list = field(default_factory=list)
    drafts: dict = field(default_factory=dict)
    tips: list = field(default_factory=list)


def offer_numbers(asking, low=None, mid=None, high=None):
    """Return (opening, target, walk_away, note) using the rules in the module docstring."""
    if asking is None or asking <= 0:
        return None, None, None, "No asking price was found, so no offer numbers can be given."
    if mid is None:
        opening, target, walk = asking * NO_DATA_OPENING, asking * NO_DATA_TARGET, asking
        note = "No fair range, so offers are based on the asking price only (low confidence)."
    elif asking <= low:
        note = ("The asking price is already at or below the fair range. Offer the asking price; "
                "a lower offer risks losing a good deal, and a very low price is itself a reason "
                "to verify extra carefully.")
        return asking, asking, asking, note
    else:
        walk = min(asking, high)
        target = min(asking, mid)
        opening = min(target, max(target * OPENING_OF_TARGET, low * OPENING_FLOOR_OF_LOW))
        note = ""
    walk = min(nice_round(walk), asking)
    target = min(nice_round(target), walk)
    opening = min(nice_round(opening), target)
    return opening, target, walk, note


def money(value):
    return f"${value:,.0f}"


def _item_name(listing):
    return listing.title.strip() or "the item"


def draft_messages(listing, opening, target, walk_away, grade):
    item = _item_name(listing)
    condition = f" in {grade} condition" if grade else ""
    return {
        "opening offer": (
            f"Hi, is the {item} still available? I've compared similar listings{condition}, "
            f"and I'd like to offer {money(opening)}. I can meet at a public place in daylight and pay "
            f"once I've checked it works. Thanks!"),
        "counter-offer": (
            f"Thanks for getting back to me. I can come up to {money(target)}, which is in line with "
            f"what similar ones are listed for. If that works, I can meet at a public spot and pay "
            f"after seeing it in person."),
        "walking away": (
            f"Thanks for your time. {money(walk_away)} is the most I can do, so I'll pass for now. "
            f"If anything changes, feel free to message me. Good luck with the sale!"),
    }


def decline_message(listing):
    return (f"Thanks, but I only buy in person after seeing the item, and I pay at the meetup. "
            f"I'll pass on the {_item_name(listing)}. Good luck.")


TIPS = [
    "Lead with the evidence: mention condition and comparable prices, not personal hardship.",
    "Make one counter at most, then stand by your walk-away. Silence is fine.",
    "Bring the exact amount in cash to the meetup so you are not pushed into an app transfer.",
    "Re-check the item at the meetup. If it is worse than described, it is fair to re-price or walk.",
    "Never invent competing offers or fake deadlines; honesty keeps the deal clean.",
]


def coach(listing, estimate, scam_report):
    """Build the offer strategy and drafts from the estimate and scam verdict."""
    has_range = estimate is not None and estimate.has_range
    low, mid, high = (estimate.low, estimate.mid, estimate.high) if has_range else (None, None, None)
    opening, target, walk, note = offer_numbers(listing.price, low, mid, high)
    grade = estimate.target_grade.grade if estimate is not None else ""

    verdict = scam_report.verdict if scam_report is not None else None
    if verdict == LIKELY_SCAM:
        return Strategy(asking=listing.price, opening=None, target=None, walk_away=None, proceed=False,
                        headline="Do not negotiate. This listing is a likely scam; walk away.",
                        rationale=["Negotiating with a likely scammer only gives them more chances "
                                   "to pressure you into paying first, so no offer numbers are given.",
                                   "If you reply at all, use the short decline below and stop."],
                        drafts={"walking away": decline_message(listing)}, tips=[])

    rationale = [note] if note else []
    if opening is None:
        headline = "No offer numbers: the listing has no readable asking price."
    elif verdict == SUSPICIOUS:
        headline = ("Proceed only with caution: resolve the red flags in the scam check before "
                    f"making any offer. If they check out: open at {money(opening)}, aim for "
                    f"{money(target)}, walk away above {money(walk)}.")
    else:
        headline = f"Open at {money(opening)}, aim for {money(target)}, walk away above {money(walk)}."
    if has_range and opening is not None:
        rationale.append(f"Fair range is {money(nice_round(low))} to {money(nice_round(high))} "
                         f"(midpoint {money(nice_round(mid))}); asking is {money(listing.price)}.")
        if listing.price > high:
            rationale.append("Asking is above the fair range, so the walk-away is capped at the "
                             "top of the range.")
        if estimate.confidence == "low":
            rationale.append("The fair range rests on thin data; treat these numbers as rough.")

    drafts = draft_messages(listing, opening, target, walk, grade) if opening is not None else {}
    return Strategy(asking=listing.price, opening=opening, target=target, walk_away=walk,
                    proceed=opening is not None, headline=headline, rationale=rationale,
                    drafts=drafts, tips=list(TIPS))
