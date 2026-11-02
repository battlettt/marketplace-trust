"""One call that runs every feature on pasted text and returns the results."""

from dataclasses import dataclass

from .negotiation import coach
from .parsing import ComparableSet, parse_comparables, parse_listing, parse_observations
from .pricing import estimate_fair_price
from .scam import assess_listing
from .trend import analyze_trend


@dataclass
class Analysis:
    listing: object
    estimate: object
    scam: object
    strategy: object
    trend: object = None


def analyze(listing_text, comparables_text="", observations_text=None, as_of=None, rate=None):
    """Parse and analyse a pasted listing (plus optional comparables and observations)."""
    listing = parse_listing(listing_text)
    reference = as_of or listing.listed
    comparables = parse_comparables(comparables_text, reference) if comparables_text else ComparableSet()
    estimate = estimate_fair_price(listing, comparables, as_of=as_of, rate=rate)
    scam = assess_listing(listing, estimate)
    strategy = coach(listing, estimate, scam)
    trend = analyze_trend(parse_observations(observations_text, reference)) if observations_text else None
    return Analysis(listing, estimate, scam, strategy, trend)
