"""Listing scam detection from pasted text.

Each check returns Signal objects with a severity (HIGH, MEDIUM, LOW), a
category, a plain-English explanation, and the text that triggered it.
Signals are ordered most serious first, with payment risks ahead of
everything else at the same severity (safety first).
"""

import re
from dataclasses import dataclass, field

from .pricing import nice_round

HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"
SEVERITY_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2}
SEVERITY_POINTS = {HIGH: 3, MEDIUM: 2, LOW: 1}
CATEGORY_ORDER = ["payment", "price", "pressure", "seller", "photos"]
CATEGORY_LABEL = {
    "payment": "Risky payment",
    "price": "Too-good price",
    "pressure": "Pressure tactic",
    "seller": "Seller red flag",
    "photos": "Stolen photo / copied text",
}

LIKELY_SCAM = "LIKELY SCAM"
SUSPICIOUS = "SUSPICIOUS"
NO_MAJOR = "NO MAJOR RED FLAGS"


@dataclass
class Signal:
    severity: str
    category: str
    title: str
    explanation: str
    evidence: list = field(default_factory=list)

    def sort_key(self):
        return SEVERITY_RANK[self.severity], CATEGORY_ORDER.index(self.category)


@dataclass
class ScamReport:
    verdict: str
    signals: list
    score: int
    notes: list = field(default_factory=list)

    @property
    def payment_signals(self):
        return [s for s in self.signals if s.category == "payment"]

    def reasons(self):
        return [f"[{s.severity}] {s.title}" for s in self.signals]


def defang(text):
    """Make any link in quoted evidence non-clickable."""
    text = re.sub(r"(?i)\bhttps?://", lambda m: m.group(0).lower().replace("http", "hxxp"), text)
    text = re.sub(r"(?i)\bwww\.", "www[.]", text)
    return re.sub(r"(?i)\.(com|net|org|io|ly|co|ca|us|me|xyz|shop)\b", r"[.]\1", text)


def snippet(text, match, width=35):
    start = max(0, match.start() - width)
    end = min(len(text), match.end() + width)
    piece = " ".join(text[start:end].replace("\n", " / ").split())
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return defang(f'"{prefix}{piece}{suffix}"')


def find_all(patterns, text, gap=40):
    """Evidence snippets for every match of one or more compiled patterns.

    Matches within `gap` characters of the previous one share a snippet, so
    "Text me on WhatsApp at 403-555-0199" is quoted once, not three times.
    """
    if not isinstance(patterns, (list, tuple)):
        patterns = [patterns]
    matches = sorted((m for p in patterns for m in p.finditer(text)), key=lambda m: m.start())
    evidence, last_end = [], None
    for m in matches:
        if last_end is not None and m.start() - last_end <= gap:
            last_end = max(last_end, m.end())
            continue
        evidence.append(snippet(text, m))
        last_end = m.end()
    return evidence


def _rx(*alternatives):
    return re.compile("|".join(alternatives), re.I)


# --- payment ---------------------------------------------------------------

GIFT_CARD_RE = _rx(r"\bgift ?cards?\b", r"\b(?:itunes|apple|google play|steam|amazon|visa) (?:gift )?cards?\b")
WIRE_RE = _rx(r"\bwire transfer\b", r"\bwestern union\b", r"\bmoneygram\b", r"\bbank wire\b",
              r"\bwire (?:the |me )?(?:money|funds|payment)\b")
CRYPTO_RE = _rx(r"\bcrypto(?:currency)?\b", r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b",
                r"\busdt\b", r"\btether\b")
P2P_RE = _rx(r"\be-?transfer\b", r"\binterac\b", r"\bzelle\b", r"\bvenmo\b", r"\bcash ?app\b",
             r"\bpaypal (?:friends|f&f|family)\b", r"\bfriends (?:and|&) family\b")
PAYMENT_WORD = r"\b(?:pay|send|transfer|e-?transfer|cash|money|funds)\w*"
ADVANCE_RE = _rx(
    PAYMENT_WORD + r"\s+(?:\S+\s+){0,3}?(?:first|upfront|up front|in advance|ahead of time|beforehand)\b",
    r"\b(?:upfront|up-front|advance) (?:payment|deposit)\b",
    r"\bdeposit\b",
    # a payment word followed closely by "before you see it" or "to hold it"
    PAYMENT_WORD + r"(?:\W+\w+){0,6}?\W+(?:before (?:you |we |i )?(?:can )?(?:see|seeing|view|viewing|pick"
    r"|picking|meet|meeting|inspect|inspecting|come|coming|ship|shipping|deliver|delivery|test|testing)"
    r"|to (?:hold|reserve) (?:it|the item|this))\b",
)
FIRST_COME_RE = re.compile(r"first come,? first serve[ds]?", re.I)
NEGATED_RE = re.compile(r"\b(?:no|not|never|without|don'?t|won'?t|doesn'?t)\b[^.!?]*$", re.I)


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def advance_payment_evidence(text):
    evidence = []
    for sentence in _sentences(text):
        cleaned = FIRST_COME_RE.sub(" ", sentence)
        match = ADVANCE_RE.search(cleaned)
        if match and not NEGATED_RE.search(cleaned[max(0, match.start() - 25):match.start()]):
            evidence.append(snippet(cleaned, match, width=50))
    return evidence


def check_payment(text):
    signals = []
    advance = advance_payment_evidence(text)
    if advance:
        signals.append(Signal(HIGH, "payment", "Asks for payment or a deposit before you see the item",
                              "Paying before you have seen and checked the item is the most common way "
                              "buyers lose money. Legitimate sellers let you inspect first and are paid "
                              "on the spot.", advance))
    checks = [
        (GIFT_CARD_RE, HIGH, "Asks for gift cards",
         "Gift cards are untraceable and cannot be reversed. No genuine private seller needs to be paid in gift cards."),
        (WIRE_RE, HIGH, "Asks for a wire transfer / money transfer service",
         "Wire and money-transfer payments are near impossible to recover and are a classic scam payment route."),
        (CRYPTO_RE, HIGH, "Asks for cryptocurrency",
         "Crypto payments are irreversible and anonymous. Treat any crypto-only private sale as a scam."),
    ]
    for pattern, severity, title, explanation in checks:
        evidence = find_all(pattern, text)
        if evidence:
            signals.append(Signal(severity, "payment", title, explanation, evidence))
    p2p = find_all(P2P_RE, text)
    if p2p:
        severity = HIGH if advance else MEDIUM
        detail = (" Here it is combined with paying in advance, which makes it high risk." if advance
                  else " Only consider it in person, after you have checked the item.")
        signals.append(Signal(severity, "payment", "Requests an instant bank or app transfer",
                              "E-transfers and payment apps settle instantly and are hard to reverse; "
                              "they offer no buyer protection with a stranger." + detail, p2p))
    return signals


# --- price -----------------------------------------------------------------

def check_price(estimate):
    if estimate is None or not estimate.has_range or not estimate.asking:
        return []
    ratio = estimate.asking / estimate.mid
    if ratio >= 0.7:
        return []
    severity = HIGH if ratio < 0.5 else MEDIUM
    explanation = (f"Asking ${estimate.asking:,.0f} is {1 - ratio:.0%} below the fair midpoint of "
                   f"${nice_round(estimate.mid):,}. Prices far below market are the usual bait in scams.")
    if estimate.confidence == "low":
        severity = MEDIUM if severity == HIGH else LOW
        explanation += " (Downgraded one level because the fair range rests on thin data.)"
    title = "Price is far below the fair range" if ratio < 0.5 else "Price is well below the fair range"
    return [Signal(severity, "price", title, explanation)]


# --- pressure --------------------------------------------------------------

DEADLINE_RE = _rx(r"\btoday only\b", r"\bonly today\b", r"\bends today\b", r"\b(?:by|until) tonight\b",
                  r"\btonight only\b", r"\bnext (?:hour|few hours)\b", r"\b24 hours only\b")
COMPETING_RE = _rx(
    r"\b(?:many|lots of|several|multiple|other|few) (?:people|buyers|offers)\b",
    r"\b(?:someone|another buyer|other buyers?) (?:is |are )?(?:coming|interested|wants|waiting)\b",
    r"\balready (?:have|got) (?:\w+ )?offers?\b",
    r"\bfirst (?:person )?to pay\b",
)
URGENCY_RE = _rx(r"\bact (?:fast|now)\b", r"\bhurry\b", r"\bwon'?t last\b", r"\burgent(?:ly)?\b",
                 r"\basap\b", r"\bmust (?:sell|go) (?:today|now|asap|this week)\b",
                 r"\bneed (?:it |this )?gone (?:today|now|asap|fast)\b",
                 r"\bneed (?:the )?money (?:today|fast|asap|now)\b", r"\bquick sale\b")
OFF_PLATFORM_RE = _rx(r"\bwhats ?app\b", r"\btelegram\b", r"\bwechat\b", r"\bsignal app\b",
                      r"\btext me\b", r"\bcall me\b", r"\bemail me\b", r"\bcontact me (?:at|on|via)\b",
                      r"\b(?:off|outside) (?:of )?(?:the |this )?(?:app|platform|site)\b",
                      r"\bmy (?:number|cell|email) is\b")
PHONE_RE = re.compile(r"(?<!\d)\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
LINK_RE = re.compile(r"(?i)\bhttps?://\S+|\bwww\.\S+|\b[\w-]+\.(?:com|net|org|io|ly|xyz|shop)/\S*")


def check_pressure(text):
    signals = []
    evidence = find_all(DEADLINE_RE, text)
    if evidence:
        signals.append(Signal(MEDIUM, "pressure", "Artificial deadline (\"today only\")",
                              "A hard deadline is meant to stop you from checking the item or "
                              "the seller. A genuine seller can wait a day.", evidence))
    evidence = find_all(COMPETING_RE, text)
    if evidence:
        signals.append(Signal(MEDIUM, "pressure", "Claims of competing buyers",
                              "Talk of other buyers or 'first to pay gets it' is used to rush you into "
                              "paying before you verify. Don't let it change your process.", evidence))
    evidence = find_all(URGENCY_RE, text)
    if evidence:
        signals.append(Signal(LOW, "pressure", "Urgency language",
                              "Urgency on its own is common, but combined with other flags it is a "
                              "pressure tactic. Take your time.", evidence))
    evidence = find_all([OFF_PLATFORM_RE, PHONE_RE, EMAIL_RE, LINK_RE], text)
    if evidence:
        signals.append(Signal(MEDIUM, "pressure", "Tries to move the conversation off the platform",
                              "Moving to text, email, WhatsApp, or an outside link removes the "
                              "platform's records and protections. Keep messages on the platform and "
                              "never open payment links.", evidence))
    return signals


# --- seller ----------------------------------------------------------------

NO_HISTORY_RE = _rx(r"\bnew (?:account|profile|here)\b",
                    r"\bjust (?:joined|signed up|made (?:this|an?) (?:account|profile))\b",
                    r"\bno (?:reviews|ratings|feedback|history)\b",
                    r"\b(?:don'?t|do not) have (?:any )?(?:reviews|ratings|feedback)\b")
REFUSE_SHOW_RE = _rx(
    r"\b(?:can'?t|cannot|won'?t|unable to|not able to|will not) (?:meet|show|do (?:a )?(?:viewing|meetup|video call)|video ?call|send (?:more )?(?:photos|pictures))\b",
    r"\bno (?:meetups?|meet[- ]ups?|viewings?|inspections?|test rides?|testing)\b",
)
AWAY_RE = _rx(r"\bout of the country\b", r"\boverseas\b", r"\bdeployed\b",
              r"\bon (?:a )?(?:deployment|mission|offshore)\b", r"\bworking offshore\b",
              r"\bmy (?:agent|shipping agent|courier|cousin|brother|sister|assistant) will (?:deliver|bring|ship|send)\b")
SHIP_ONLY_RE = _rx(r"\b(?:shipping|delivery|courier|ship) only\b", r"\bwill ship (?:it )?(?:to you )?after payment\b",
                   r"\bonly (?:ship|deliver)\b")
TEMPLATE_RE = _rx(r"\bkindly\b", r"\bdear (?:buyer|customer|sir|madam|friend)\b", r"\bgod bless\b",
                  r"\b100% (?:genuine|legit|original|real)\b", r"\bno scam\b", r"\bnot a scam\b")
LOCATION_CLAIM_RE = re.compile(
    r"\b(?i:located in|based in|i(?:'m| am) (?:currently |now )?(?:in|living in)|pick ?up (?:is )?in|"
    r"ships? from|shipping from|moved to)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)")


def repeated_sentences(text):
    seen, repeats = set(), []
    for sentence in _sentences(text):
        key = " ".join(sentence.lower().split())
        if len(key) >= 25:
            if key in seen and key not in repeats:
                repeats.append(key)
            seen.add(key)
    return repeats


def location_mismatches(listing):
    if not listing.location:
        return []
    home = listing.location.lower()
    evidence = []
    for match in LOCATION_CLAIM_RE.finditer(listing.full_text):
        place = match.group(1).strip()
        if place.lower() not in home and home.split(",")[0].strip() not in place.lower():
            evidence.append(snippet(listing.full_text, match) + f" vs listed location '{listing.location}'")
    return evidence


def check_seller(listing, condition_note=""):
    text = listing.full_text
    signals = []
    evidence = find_all(REFUSE_SHOW_RE, text)
    if evidence:
        signals.append(Signal(HIGH, "seller", "Refuses to meet or show the item",
                              "If you can't see the item before paying, you have no way to know it "
                              "exists. Walk away from any seller who won't let you inspect it.", evidence))
    evidence = find_all(AWAY_RE, text)
    if evidence:
        signals.append(Signal(HIGH, "seller", "Seller says they are away and someone else will deliver",
                              "'I'm overseas / deployed / my agent will ship it' is a classic script "
                              "for collecting payment on an item that doesn't exist.", evidence))
    evidence = find_all(SHIP_ONLY_RE, text)
    if evidence:
        signals.append(Signal(MEDIUM, "seller", "Shipping only, no local pickup",
                              "For a local marketplace sale, shipping-only means paying before you "
                              "see anything. Prefer local pickup with inspection.", evidence))
    evidence = find_all(NO_HISTORY_RE, text)
    if evidence:
        signals.append(Signal(MEDIUM, "seller", "No seller history",
                              "A brand new account with no reviews can't be checked. Be extra strict "
                              "about meeting in person and inspecting first.", evidence))
    evidence = location_mismatches(listing)
    if evidence:
        signals.append(Signal(MEDIUM, "seller", "Location details don't match",
                              "The text mentions a different place than the listed location. Scam "
                              "listings are often posted far from where the 'seller' really is.", evidence))
    repeats = repeated_sentences(text)
    markers = {m.group(0).lower() for m in TEMPLATE_RE.finditer(text)}
    evidence = find_all(TEMPLATE_RE, text) + [f'"{r}" (repeated)' for r in repeats]
    if evidence:
        severity = MEDIUM if len(markers) + len(repeats) >= 2 else LOW
        signals.append(Signal(severity, "seller", "Copied or scripted listing text",
                              "Phrases like 'kindly', 'dear buyer', '100% legit', or repeated "
                              "sentences are common in scam templates reused across many listings.", evidence))
    if condition_note:
        signals.append(Signal(LOW, "seller", "Condition claims don't agree",
                              "The " + condition_note + ". Ask for photos of the damage and price "
                              "for the worse condition."))
    return signals


# --- photos / copied retail text ------------------------------------------

STOCK_PHOTO_RE = _rx(
    r"\bstock (?:photo|image|pic|picture)s?\b",
    r"\b(?:photo|picture|pic|image)s? (?:are |is )?(?:from|off) (?:the )?(?:internet|web|google|website|manufacturer|amazon)\b",
    r"\b(?:photo|picture|pic|image)s? (?:are |is )?(?:for )?(?:reference|illustration)(?: only| purposes)?\b",
    r"\bnot (?:the )?actual (?:item|photo|picture|product)\b",
    r"\b(?:actual|real) (?:item|product) (?:may )?(?:differ|look different)\b",
    r"\bsimilar to (?:the )?(?:photo|picture|image)\b",
    r"\brepresentative (?:photo|image|picture)\b",
)
PHOTO_MISMATCH_RE = _rx(
    r"\b(?:photo|picture|pic|image)s? (?:shows?|is of) (?:a |an )?(?:different|older|newer|another)\b",
    r"\bcolou?r (?:is )?(?:different|differs) (?:from|than) (?:the )?(?:photo|picture|pic)s?\b",
    r"\bnot the (?:same|exact) (?:item|model|one|unit) (?:as |in )?(?:the )?(?:photo|picture|pic)s?\b",
    r"\b(?:photo|picture|pic)s? (?:is |are )?(?:from|of) (?:my|a) (?:old|previous|other)\b",
)
RETAIL_RE = _rx(r"\badd to cart\b", r"\bbuy now\b", r"\bfree shipping\b", r"\bin stock\b", r"\bsku\b",
                r"\bmanufacturer'?s? warranty\b", r"\bsatisfaction guaranteed\b", r"\blimited time offer\b",
                r"\border now\b", r"\bclick (?:here|the link)\b", r"\bkey features\s*:", r"\bspecifications\s*:",
                r"\bwhat'?s in the box\b", r"®|™", r"\bmsrp\b", r"\bships within\b")


def check_photos(text):
    signals = []
    evidence = find_all(STOCK_PHOTO_RE, text)
    if evidence:
        signals.append(Signal(MEDIUM, "photos", "Uses stock or borrowed photos",
                              "Photos that aren't of the actual item hide its real condition, or "
                              "that the seller doesn't have it. Ask for a photo with today's date "
                              "written on paper next to the item.", evidence))
    evidence = find_all(PHOTO_MISMATCH_RE, text)
    if evidence:
        signals.append(Signal(MEDIUM, "photos", "Description admits the photos don't match the item",
                              "If the photos show a different item, you don't know what you are buying. "
                              "Insist on seeing the actual item.", evidence))
    markers = {m.group(0).lower() for m in RETAIL_RE.finditer(text)}
    if len(markers) >= 2:
        signals.append(Signal(MEDIUM, "photos", "Text looks copied from a retail listing",
                              "Shop phrases (" + ", ".join(sorted(markers)) + ") suggest the text, and "
                              "likely the photos, were lifted from a store page rather than written "
                              "by someone holding the item."))
    return signals


# --- verdict ---------------------------------------------------------------

def decide_verdict(signals):
    """Aggregate signals into a verdict.

    LIKELY SCAM: 2+ HIGH signals, or 1 HIGH plus a total score of 6+, or score 8+.
    SUSPICIOUS:  any HIGH, a MEDIUM too-good-price signal, or score 3+.
    Otherwise:   NO MAJOR RED FLAGS.
    Points: HIGH 3, MEDIUM 2, LOW 1.
    """
    score = sum(SEVERITY_POINTS[s.severity] for s in signals)
    highs = sum(1 for s in signals if s.severity == HIGH)
    if highs >= 2 or (highs >= 1 and score >= 6) or score >= 8:
        return LIKELY_SCAM, score
    key_medium = any(s.severity == MEDIUM and s.category == "price" for s in signals)
    if highs >= 1 or key_medium or score >= 3:
        return SUSPICIOUS, score
    return NO_MAJOR, score


def assess_listing(listing, estimate=None):
    """Run every scam check and return a ScamReport, most serious first."""
    text = listing.full_text
    condition_note = estimate.condition_note if estimate is not None else ""
    signals = (check_payment(text) + check_price(estimate) + check_pressure(text)
               + check_seller(listing, condition_note) + check_photos(text))
    signals.sort(key=Signal.sort_key)
    verdict, score = decide_verdict(signals)
    notes = []
    if estimate is None or not estimate.has_range:
        notes.append("No fair range was available, so the too-good-price check was skipped.")
    return ScamReport(verdict=verdict, signals=signals, score=score, notes=notes)
