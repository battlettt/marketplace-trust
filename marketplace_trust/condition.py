"""Condition grading: map free-text condition language to one of four grades.

Rules, in order:
1. Phrases are matched longest first, so "minor scratches" (good) is consumed
   before "scratches" (fair) can match.
2. A phrase preceded by a negation ("no scratches", "not broken") is ignored.
3. When several grades match, the most severe one wins. Buyers should price
   for the worst thing the seller admits to.
4. No condition language at all means "good" is assumed, and the grade says so.
"""

import re
from dataclasses import dataclass, field

GRADES = ("like new", "good", "fair", "worn")

# Price multiplier relative to an item in "good" condition.
MULTIPLIER = {"like new": 1.15, "good": 1.00, "fair": 0.82, "worn": 0.62}
SEVERITY = {grade: rank for rank, grade in enumerate(GRADES)}

PHRASES = {
    "worn": [
        "for parts", "parts only", "not working", "doesn't work", "does not work",
        "doesnt work", "broken", "cracked", "heavy wear", "heavily used", "well worn",
        "worn", "needs repair", "needs work", "water damage", "poor condition", "poor",
        "heavy rust", "rusted through", "torn", "missing parts", "sold as is", "as-is", "dead pixels",
        "battery dead", "won't turn on",
    ],
    "fair": [
        "fair condition", "fair shape", "some wear", "visible wear", "signs of wear", "normal wear", "scratches",
        "scratched", "scuffs", "scuffed", "dents", "dented", "dent", "faded", "minor damage",
        "stains", "stained", "rust", "rusty", "chipped", "wobbly", "cosmetic damage", "needs cleaning",
        "needs a tune up", "needs a tune-up",
    ],
    "good": [
        "good condition", "good shape", "good working order", "great condition", "very good", "works perfectly",
        "works great", "works well", "fully working", "fully functional", "light wear",
        "minor wear", "minor scratches", "minor scratch", "small scratch", "light scratches",
        "minor scuffs", "light scuffs", "well maintained", "well kept", "lightly used",
        "gently used", "recently serviced", "tuned up",
    ],
    "like new": [
        "like new", "mint", "brand new", "new in box", "sealed", "unopened", "never used",
        "barely used", "excellent", "pristine", "open box", "used once", "still in plastic",
        "flawless", "new condition", "as new", "worn once",
    ],
}

# A bare condition field like "New" or "Used - fair" maps directly.
EXPLICIT_LABELS = {"new": "like new", "used": "good"}

NEGATION_RE = re.compile(r"\b(?:no|not|without|zero|never|nothing)\s+(?:\w+\s+)?$")


@dataclass
class ConditionGrade:
    grade: str
    matched: list = field(default_factory=list)  # (phrase, grade) pairs
    assumed: bool = False

    @property
    def multiplier(self):
        return MULTIPLIER[self.grade]

    def explain(self):
        if self.assumed:
            return "no condition language found, assumed 'good'"
        phrases = ", ".join(f"'{p}'" for p, _ in self.matched)
        return f"graded '{self.grade}' from {phrases}"


def _phrase_table():
    pairs = [(phrase, grade) for grade, phrases in PHRASES.items() for phrase in phrases]
    return sorted(pairs, key=lambda pair: -len(pair[0]))


PHRASE_TABLE = _phrase_table()


def find_condition_phrases(text):
    """Return (phrase, grade) pairs found in text, longest phrases first."""
    remaining = " " + (text or "").lower() + " "
    found = []
    for phrase, grade in PHRASE_TABLE:
        pattern = re.compile(r"(?<![\w'])" + re.escape(phrase) + r"(?![\w'])")
        while True:
            match = pattern.search(remaining)
            if not match:
                break
            negated = NEGATION_RE.search(remaining[max(0, match.start() - 20):match.start()])
            if not negated and (phrase, grade) not in found:
                found.append((phrase, grade))
            remaining = remaining[:match.start()] + " " * len(phrase) + remaining[match.end():]
    return found


def grade_condition(text):
    """Grade free text into 'like new', 'good', 'fair', or 'worn'."""
    label = (text or "").strip().lower()
    if label in GRADES:
        return ConditionGrade(label, [(label, label)])
    if label in EXPLICIT_LABELS:
        return ConditionGrade(EXPLICIT_LABELS[label], [(label, EXPLICIT_LABELS[label])])
    found = find_condition_phrases(text)
    if not found:
        return ConditionGrade("good", assumed=True)
    worst = max((grade for _, grade in found), key=SEVERITY.get)
    return ConditionGrade(worst, found)


def grade_listing(listing):
    """Grade a listing from its condition field and description together.

    Returns (grade, inconsistency) where inconsistency is a short note when the
    condition field claims a better grade than the description admits.
    """
    field_grade = grade_condition(listing.condition_text) if listing.condition_text else None
    body_grade = grade_condition("\n".join([listing.title, listing.description, listing.seller_notes]))
    if field_grade is None:
        return body_grade, ""
    if body_grade.assumed or SEVERITY[body_grade.grade] <= SEVERITY[field_grade.grade]:
        return field_grade, ""
    worse = [p for p, g in body_grade.matched if SEVERITY[g] > SEVERITY[field_grade.grade]]
    note = (f"condition field says '{field_grade.grade}' but the description mentions "
            + ", ".join(f"'{p}'" for p in worse))
    return ConditionGrade(body_grade.grade, field_grade.matched + body_grade.matched), note
