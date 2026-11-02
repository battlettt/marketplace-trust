from marketplace_trust.condition import MULTIPLIER, grade_condition, grade_listing
from marketplace_trust.parsing import parse_listing


def test_explicit_labels():
    assert grade_condition("like new").grade == "like new"
    assert grade_condition("Fair").grade == "fair"
    assert grade_condition("worn").grade == "worn"
    assert grade_condition("New").grade == "like new"


def test_phrase_rules_for_each_grade():
    assert grade_condition("Mint, still sealed").grade == "like new"
    assert grade_condition("Works great, well maintained").grade == "good"
    assert grade_condition("some scuffs and a dent").grade == "fair"
    assert grade_condition("screen cracked, for parts").grade == "worn"


def test_longest_phrase_wins_over_its_parts():
    # "minor scratches" is good; plain "scratches" is fair.
    assert grade_condition("minor scratches on the lid").grade == "good"
    assert grade_condition("scratches on the lid").grade == "fair"


def test_negated_phrases_are_ignored():
    grade = grade_condition("No scratches, not broken, works perfectly")
    assert grade.grade == "good"
    assert ("scratches", "fair") not in grade.matched


def test_most_severe_grade_wins():
    assert grade_condition("Excellent, but some wear on the corners").grade == "fair"


def test_no_language_assumes_good_and_says_so():
    grade = grade_condition("blue, 15 inch")
    assert grade.grade == "good" and grade.assumed
    assert "assumed" in grade.explain()


def test_multipliers_are_ordered():
    assert MULTIPLIER["like new"] > MULTIPLIER["good"] > MULTIPLIER["fair"] > MULTIPLIER["worn"]
    assert MULTIPLIER["good"] == 1.0


def test_listing_description_can_downgrade_the_condition_field():
    listing = parse_listing("Title: Laptop\nCondition: like new\nDescription: Hinge is cracked.")
    grade, note = grade_listing(listing)
    assert grade.grade == "worn"
    assert "cracked" in note


def test_listing_field_kept_when_description_agrees():
    listing = parse_listing("Title: Laptop\nCondition: good\nDescription: Works great.")
    grade, note = grade_listing(listing)
    assert grade.grade == "good" and note == ""
