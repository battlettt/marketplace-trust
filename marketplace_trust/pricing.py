"""Fair price estimation from comparables.

Each usable comparable is turned into "what this would be worth if it were
the target item, today, in the target's region" through three visible steps:

1. Condition:    price x (target multiplier / comparable multiplier)
2. Depreciation: x (1 - annual rate) ** (age in days / 365)
3. Region:       x (target region index / comparable region index)

The fair range comes from the spread of those adjusted values. With fewer
than 3 usable comparables the range is widened and confidence is low.
"""

import re
import statistics
from dataclasses import dataclass, field
from datetime import date

from .condition import MULTIPLIER, grade_condition, grade_listing

DEFAULT_RATE = 0.15
MAX_AGE_DAYS = 3 * 365
THIN_DATA = 3
THIN_WIDEN = 0.25
MIN_HALF_WIDTH = 0.08
OUTLIER_FACTOR = 2.0
REGION_SHRINK = 0.5
REGION_CLAMP = (0.85, 1.15)

# (category, annual depreciation rate, title keywords)
CATEGORY_RATES = [
    ("phone", 0.30, ["iphone", "phone", "pixel", "galaxy s", "smartphone"]),
    ("computer", 0.25, ["laptop", "macbook", "computer", "tablet", "ipad", "pc", "monitor", "gpu"]),
    ("electronics", 0.20, ["tv", "camera", "console", "playstation", "ps5", "xbox", "switch",
                           "headphones", "speaker", "drone", "lens"]),
    ("bike", 0.12, ["bike", "bicycle", "ebike", "e-bike"]),
    ("furniture", 0.10, ["sofa", "couch", "table", "chair", "desk", "dresser", "bed", "shelf"]),
    ("tools", 0.08, ["drill", "saw", "tool", "mower", "compressor"]),
    ("instrument", 0.05, ["guitar", "bass", "stratocaster", "strat", "telecaster", "les paul",
                          "piano", "keyboard", "violin", "drum", "amp", "ukulele"]),
]

STOP_WORDS = {"the", "and", "for", "with", "used", "sale", "new", "like", "good", "great",
              "condition", "excellent", "mint", "fair", "worn", "obo", "firm"}


@dataclass
class AdjustedComparable:
    comp: object
    grade: object = None
    used: bool = False
    exclusion: str = ""
    age_days: int | None = None
    condition_factor: float = 1.0
    depreciation_factor: float = 1.0
    region_factor: float = 1.0
    adjusted: float = 0.0


@dataclass
class Estimate:
    low: float | None
    mid: float | None
    high: float | None
    confidence: str
    asking: float | None
    target_grade: object
    condition_note: str
    category: str
    rate: float
    reference_date: date
    target_region: str
    region_index: dict
    region_source: str
    comps: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def used(self):
        return [c for c in self.comps if c.used]

    @property
    def has_range(self):
        return self.mid is not None

    def asking_position(self):
        """'below', 'within', or 'above' the fair range (None if unknown)."""
        if not self.has_range or self.asking is None:
            return None
        if self.asking < self.low:
            return "below"
        if self.asking > self.high:
            return "above"
        return "within"


def nice_round(value):
    """Round to a step that suits the size of the number (half rounds up)."""
    if value is None:
        return None
    step = 1 if value < 50 else 5 if value < 500 else 10 if value < 2000 else 25
    return int(value / step + 0.5) * step


def detect_category(listing):
    """Return (category, annual depreciation rate) for the listing."""
    if listing.category:
        for name, rate, _ in CATEGORY_RATES:
            if listing.category.startswith(name):
                return name, rate
    title = " " + listing.title.lower() + " "
    for name, rate, keywords in CATEGORY_RATES:
        if any(re.search(r"\b" + re.escape(k) + r"\b", title) for k in keywords):
            return name, rate
    return "general", DEFAULT_RATE


def _tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOP_WORDS and not w.isdigit()}


def looks_like_same_item(listing_title, comp_item):
    """A comparable must share at least one meaningful word with the listing title."""
    wanted = _tokens(listing_title)
    return not wanted or bool(wanted & _tokens(comp_item))


def derive_region_index(adjusted, explicit):
    """Regional price index per region (1.00 = average of all comparables).

    Explicit '@region' lines win. Otherwise an index is derived for any region
    with at least 2 comparables, when at least 2 regions are present, and is
    shrunk halfway toward 1.00 and clamped to 0.85-1.15 so a few listings
    cannot swing the estimate much.
    """
    if explicit:
        return dict(explicit), "explicit"
    by_region = {}
    for a in adjusted:
        if a.comp.region:
            by_region.setdefault(a.comp.region, []).append(a.adjusted)
    eligible = {r: v for r, v in by_region.items() if len(v) >= 2}
    if len(eligible) < 2:
        return {}, "none"
    overall = statistics.median([a.adjusted for a in adjusted])
    index = {}
    for region, values in eligible.items():
        raw = statistics.median(values) / overall
        shrunk = 1 + REGION_SHRINK * (raw - 1)
        index[region] = round(min(REGION_CLAMP[1], max(REGION_CLAMP[0], shrunk)), 3)
    return index, "derived"


def _reference_date(listing, as_of):
    return as_of or listing.listed or date.today()


def _prepare(comp, listing, target, ref, rate):
    a = AdjustedComparable(comp=comp)
    if comp.error:
        a.exclusion = comp.error
        return a
    if comp.price <= 0:
        a.exclusion = "price is zero"
        return a
    if not looks_like_same_item(listing.title, comp.item):
        a.exclusion = "does not look like the same item"
        return a
    if comp.when is not None:
        a.age_days = (ref - comp.when).days
        if a.age_days < 0:
            a.exclusion = "dated after the reference date"
            return a
        if a.age_days > MAX_AGE_DAYS:
            a.exclusion = "older than 3 years"
            return a
    a.grade = grade_condition(comp.condition_text)
    a.condition_factor = MULTIPLIER[target.grade] / MULTIPLIER[a.grade.grade]
    a.depreciation_factor = (1 - rate) ** ((a.age_days or 0) / 365)
    a.adjusted = comp.price * a.condition_factor * a.depreciation_factor
    a.used = True
    return a


def _apply_regions(candidates, index, target_region):
    target_idx = index.get(target_region, 1.0)
    for a in candidates:
        comp_idx = index.get(a.comp.region, 1.0) if a.comp.region else target_idx
        a.region_factor = target_idx / comp_idx
        a.adjusted = a.comp.price * a.condition_factor * a.depreciation_factor * a.region_factor


def _drop_outliers(candidates):
    if len(candidates) < 4:
        return
    median = statistics.median(a.adjusted for a in candidates)
    for a in candidates:
        if a.adjusted > median * OUTLIER_FACTOR or a.adjusted < median / OUTLIER_FACTOR:
            a.used = False
            a.exclusion = f"outlier (more than {OUTLIER_FACTOR:g}x away from the median)"


def _range(values):
    mid = statistics.median(values)
    n = len(values)
    if n < THIN_DATA:
        low = min(mid * (1 - THIN_WIDEN), min(values))
        high = max(mid * (1 + THIN_WIDEN), max(values))
        return low, mid, high, "low"
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    low = min(q1, mid * (1 - MIN_HALF_WIDTH))
    high = max(q3, mid * (1 + MIN_HALF_WIDTH))
    tight = (q3 - q1) / mid <= 0.25
    confidence = "high" if n >= 5 and tight else "medium"
    return low, mid, high, confidence


def estimate_fair_price(listing, comparable_set, as_of=None, rate=None):
    """Estimate a fair price range for the listing from pasted comparables."""
    ref = _reference_date(listing, as_of)
    category, category_rate = detect_category(listing)
    rate = category_rate if rate is None else rate
    target, condition_note = grade_listing(listing)

    adjusted = [_prepare(c, listing, target, ref, rate) for c in comparable_set.comparables]
    candidates = [a for a in adjusted if a.used]
    index, source = derive_region_index(candidates, comparable_set.region_index) if candidates else ({}, "none")
    _apply_regions(candidates, index, listing.region)
    _drop_outliers(candidates)
    values = [a.adjusted for a in candidates if a.used]

    notes = []
    if any(a.used and a.age_days is None for a in adjusted):
        notes.append("Some comparables had no date, so no depreciation was applied to them.")
    if index and listing.region and listing.region not in index:
        notes.append(f"No regional index for '{listing.region}'; it is treated as an average market (1.00).")

    estimate = Estimate(low=None, mid=None, high=None, confidence="none", asking=listing.price,
                        target_grade=target, condition_note=condition_note, category=category,
                        rate=rate, reference_date=ref, target_region=listing.region,
                        region_index=index, region_source=source, comps=adjusted, notes=notes)
    if not values:
        notes.append("No usable comparables, so no fair range can be given. Paste a few "
                     "similar listings (item | price | condition | date | region).")
        return estimate
    estimate.low, estimate.mid, estimate.high, estimate.confidence = _range(values)
    if len(values) < THIN_DATA:
        notes.append(f"Only {len(values)} usable comparable(s): the range is widened to "
                     f"+/-{THIN_WIDEN:.0%} and confidence is low. Paste more comparables to tighten it.")
    return estimate
