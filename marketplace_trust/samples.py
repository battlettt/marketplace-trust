"""Built-in sample pastes used by --demo and the README."""

from pathlib import Path

SAMPLE_DIR = Path(__file__).parent / "sample_data"

LISTING_SAMPLES = [
    ("A fair local deal", "bike_listing.txt", "bike_comparables.txt"),
    ("A likely scam", "phone_listing.txt", "phone_comparables.txt"),
    ("Thin comparable data", "guitar_listing.txt", "guitar_comparables.txt"),
]
TREND_SAMPLE = ("Nintendo Switch OLED", "switch_observations.txt")


def read_sample(name):
    return (SAMPLE_DIR / name).read_text(encoding="utf-8")
