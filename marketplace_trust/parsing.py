"""Parse pasted text: listings, comparable listings, and price observations.

Everything here works on plain strings the user pasted. Nothing is fetched.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

DOLLAR_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s?(k\b)?", re.I)
NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s?(k\b)?", re.I)
FREE_RE = re.compile(r"^\s*free\s*$", re.I)

ISO_DATE_RE = re.compile(r"\b(\d{4})[-/.](\d{1,2})(?:[-/.](\d{1,2}))?\b")
RELATIVE_DATE_RE = re.compile(r"\b(\d+|a|an|one)\s*(day|week|month|year)s?\s+ago\b", re.I)

LISTING_KEYS = {
    "title": "title",
    "item": "title",
    "price": "price",
    "asking": "price",
    "asking price": "price",
    "condition": "condition",
    "location": "location",
    "city": "location",
    "region": "region",
    "category": "category",
    "listed": "listed",
    "posted": "listed",
    "date": "listed",
    "payment": "payment",
    "payment methods": "payment",
    "description": "description",
    "details": "description",
    "seller notes": "seller_notes",
    "seller": "seller_notes",
    "notes": "seller_notes",
    "photos": "photos",
}
KEY_LINE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]{0,20}?)\s*:\s*(.*)$")


@dataclass
class Listing:
    title: str = ""
    price: float | None = None
    condition_text: str = ""
    location: str = ""
    region: str = ""
    category: str = ""
    listed: date | None = None
    payment: str = ""
    description: str = ""
    seller_notes: str = ""
    photos: str = ""
    raw: str = ""

    @property
    def full_text(self):
        """All the seller-written text, one line per field, used for scam scanning.

        Line wraps inside a field are joined so phrases split across lines still match.
        """
        parts = [self.title, self.condition_text, self.payment, self.description,
                 self.seller_notes, self.photos]
        return "\n".join(" ".join(p.split()) for p in parts if p)


@dataclass
class Comparable:
    item: str
    price: float | None
    condition_text: str = ""
    when: date | None = None
    region: str = ""
    line_no: int = 0
    error: str = ""


@dataclass
class Observation:
    when: date | None
    price: float | None
    condition_text: str = ""
    line_no: int = 0
    error: str = ""


@dataclass
class ComparableSet:
    comparables: list = field(default_factory=list)
    region_index: dict = field(default_factory=dict)


def _amount(match):
    whole, cents, k = match.group(1), match.group(2), match.group(3)
    value = float(whole.replace(",", ""))
    if cents:
        value += float("0." + cents)
    if k:
        value *= 1000
    return value


def parse_price(text, require_dollar=False):
    """Return the first price in text as a float, or None.

    "$1,200", "1200", "$1.2k" and "free" are understood. With require_dollar,
    only "$"-prefixed amounts count (used for freeform text, where a year like
    "2021" must not be mistaken for a price).
    """
    if text is None:
        return None
    if FREE_RE.match(text):
        return 0.0
    match = DOLLAR_RE.search(text)
    if match is None and not require_dollar:
        match = NUMBER_RE.search(text)
    return _amount(match) if match else None


def normalize_region(text):
    """'Toronto, ON' -> 'toronto'. Empty string when unknown."""
    if not text:
        return ""
    return text.split(",")[0].strip().lower()


def parse_date(text, reference=None):
    """Parse '2026-10-03', '2026/10', or '3 weeks ago' (relative to reference)."""
    if not text:
        return None
    match = ISO_DATE_RE.search(text)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3) or 1)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    lowered = text.strip().lower()
    reference = reference or date.today()
    if lowered == "today":
        return reference
    if lowered == "yesterday":
        return reference - timedelta(days=1)
    match = RELATIVE_DATE_RE.search(text)
    if match:
        count = match.group(1).lower()
        count = 1 if count in ("a", "an", "one") else int(count)
        days = {"day": 1, "week": 7, "month": 30, "year": 365}[match.group(2).lower()]
        return reference - timedelta(days=count * days)
    return None


def parse_listing(text):
    """Parse a pasted listing.

    Preferred shape is 'Key: value' lines (Title, Price, Condition, Location,
    Category, Listed, Payment, Description, Seller notes). Description and
    notes may span many lines. Freeform text also works: the first line is
    the title and the first "$" amount is the price.
    """
    fields = {}
    current = None
    for line in text.splitlines():
        match = KEY_LINE_RE.match(line)
        key = LISTING_KEYS.get(match.group(1).strip().lower()) if match else None
        if key:
            current = key
            fields[key] = (fields.get(key, "") + "\n" + match.group(2)).strip()
        elif current:
            fields[current] = (fields[current] + "\n" + line).strip()
        else:
            fields["description"] = (fields.get("description", "") + "\n" + line).strip()

    listing = Listing(raw=text)
    listing.title = fields.get("title", "")
    listing.condition_text = fields.get("condition", "")
    listing.location = fields.get("location", "")
    listing.region = normalize_region(fields.get("region") or fields.get("location", ""))
    listing.category = fields.get("category", "").strip().lower()
    listing.payment = fields.get("payment", "")
    listing.description = fields.get("description", "")
    listing.seller_notes = fields.get("seller_notes", "")
    listing.photos = fields.get("photos", "")
    listing.listed = parse_date(fields.get("listed", ""))

    if not listing.title:
        lines = [l.strip() for l in listing.description.splitlines() if l.strip()]
        if lines:
            listing.title = lines[0]
            listing.description = "\n".join(lines[1:])
    if "price" in fields:
        listing.price = parse_price(fields["price"])
    else:
        listing.price = parse_price(text, require_dollar=True)
    return listing


def _split_fields(line):
    if "|" in line:
        return [p.strip() for p in line.split("|")]
    if "\t" in line:
        return [p.strip() for p in line.split("\t")]
    return None


REGION_INDEX_RE = re.compile(r"^@region\s+(.+?)\s*[=\s]\s*([0-9]*\.?[0-9]+)\s*$", re.I)


def parse_comparables(text, reference=None):
    """Parse pasted comparables, one per line: item | price | condition | date | region.

    Trailing fields may be left off. Lines starting with '#' are comments. An
    optional header line is skipped. '@region Toronto 1.05' sets an explicit
    regional price index (1.00 = average market).
    """
    result = ComparableSet()
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        index_match = REGION_INDEX_RE.match(stripped)
        if index_match:
            result.region_index[normalize_region(index_match.group(1))] = float(index_match.group(2))
            continue
        parts = _split_fields(stripped)
        if parts is None:
            result.comparables.append(Comparable(item=stripped, price=None, line_no=line_no,
                                                 error="not in 'item | price | condition | date | region' form"))
            continue
        parts += [""] * (5 - len(parts))
        item, price_text, condition, when_text, region = parts[:5]
        price = parse_price(price_text)
        if price is None and not result.comparables and item.lower() in ("item", "title", "name"):
            continue  # header row
        comp = Comparable(item=item, price=price, condition_text=condition,
                          when=parse_date(when_text, reference), region=normalize_region(region),
                          line_no=line_no)
        if price is None:
            comp.error = "no readable price"
        elif when_text and comp.when is None:
            comp.error = f"unreadable date '{when_text}'"
        result.comparables.append(comp)
    return result


OBS_FALLBACK_RE = re.compile(r"^(\S+)\s+(\$?\s?[\d,]+(?:\.\d{1,2})?k?)\s*(.*)$", re.I)


def parse_observations(text, reference=None):
    """Parse pasted price observations, one per line: date | price | condition (optional).

    'date price condition' separated by spaces also works.
    """
    observations = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = _split_fields(stripped)
        if parts is None:
            match = OBS_FALLBACK_RE.match(stripped)
            parts = list(match.groups()) if match else [stripped, ""]
        parts += [""] * (3 - len(parts))
        when_text, price_text, condition = parts[:3]
        when = parse_date(when_text, reference)
        price = parse_price(price_text)
        if when is None and price is None and not observations:
            continue  # header row
        obs = Observation(when=when, price=price, condition_text=condition, line_no=line_no)
        if when is None:
            obs.error = "no readable date"
        elif price is None:
            obs.error = "no readable price"
        observations.append(obs)
    return observations
