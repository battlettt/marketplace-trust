from datetime import date

from marketplace_trust.parsing import (normalize_region, parse_comparables, parse_date, parse_listing,
                                       parse_observations, parse_price)


def test_parse_price_forms():
    assert parse_price("$1,200") == 1200
    assert parse_price("asking 350 obo") == 350
    assert parse_price("$1.2k") == 1200
    assert parse_price("$49.99") == 49.99
    assert parse_price("free") == 0
    assert parse_price("no price here") is None


def test_parse_price_freeform_ignores_years():
    assert parse_price("Trek bike 2021 for $400", require_dollar=True) == 400
    assert parse_price("Trek bike 2021", require_dollar=True) is None


def test_parse_date_forms():
    ref = date(2026, 10, 28)
    assert parse_date("2026-10-01") == date(2026, 10, 1)
    assert parse_date("2026/09") == date(2026, 9, 1)
    assert parse_date("3 weeks ago", ref) == date(2026, 10, 7)
    assert parse_date("yesterday", ref) == date(2026, 10, 27)
    assert parse_date("a month ago", ref) == date(2026, 9, 28)
    assert parse_date("sometime") is None
    assert parse_date("2026-13-40") is None


def test_normalize_region():
    assert normalize_region("Toronto, ON") == "toronto"
    assert normalize_region("") == ""


def test_parse_listing_keyed_fields_and_multiline_description():
    listing = parse_listing(
        "Title: Desk lamp\nPrice: $40\nCondition: good\nLocation: Ottawa, ON\nListed: 2026-10-01\n"
        "Description:\nLine one.\nLine two.\nSeller notes: cash only\n")
    assert listing.title == "Desk lamp"
    assert listing.price == 40
    assert listing.condition_text == "good"
    assert listing.region == "ottawa"
    assert listing.listed == date(2026, 10, 1)
    assert listing.description == "Line one.\nLine two."
    assert listing.seller_notes == "cash only"


def test_parse_listing_freeform():
    listing = parse_listing("Mountain bike 2019\nGreat shape, asking $250, pickup only.")
    assert listing.title == "Mountain bike 2019"
    assert listing.price == 250
    assert "pickup only" in listing.description


def test_full_text_joins_wrapped_lines():
    listing = parse_listing("Title: x\nDescription:\nmy courier\nwill deliver it")
    assert "my courier will deliver it" in listing.full_text


def test_parse_comparables_fields_header_errors_and_region_index():
    text = ("item | price | condition | date | region\n"
            "# a comment\n"
            "@region Toronto 1.05\n"
            "Trek FX 3 | $400 | good | 2026-10-01 | Toronto, ON\n"
            "Trek FX 3 | $380\n"
            "Trek FX 3 | ask me | good\n"
            "Trek FX 3 | $300 | good | someday\n"
            "just some text with no separators\n")
    result = parse_comparables(text)
    comps = result.comparables
    assert result.region_index == {"toronto": 1.05}
    assert len(comps) == 5
    assert comps[0].price == 400 and comps[0].region == "toronto" and comps[0].when == date(2026, 10, 1)
    assert comps[1].price == 380 and comps[1].when is None and not comps[1].error
    assert comps[2].error == "no readable price"
    assert "unreadable date" in comps[3].error
    assert "form" in comps[4].error


def test_parse_observations_pipe_and_space_forms():
    obs = parse_observations("date | price | condition\n2026-01-01 | $300 | good\n2026-02-01 $280 fair\n"
                             "2026-03-01 | n/a\n")
    assert len(obs) == 3
    assert obs[0].price == 300 and obs[0].condition_text == "good"
    assert obs[1].price == 280 and obs[1].condition_text == "fair" and obs[1].when == date(2026, 2, 1)
    assert obs[2].error == "no readable price"

