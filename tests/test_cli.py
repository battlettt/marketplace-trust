import contextlib
import io
import subprocess
import sys
from pathlib import Path

from marketplace_trust.cli import main
from marketplace_trust.samples import SAMPLE_DIR

ROOT = Path(__file__).resolve().parent.parent


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


def sample(name):
    return str(SAMPLE_DIR / name)


def test_demo_shows_all_five_features():
    code, out = run("--demo")
    assert code == 0
    for heading in ("1. FAIR PRICE ESTIMATE", "2. SCAM CHECK", "3. NEGOTIATION COACH",
                    "4. MEETUP SAFETY CHECKLIST", "PRICE TREND WATCH"):
        assert heading in out, heading
    assert "LIKELY SCAM" in out and "NO MAJOR RED FLAGS" in out
    assert "confidence: low" in out
    assert "Direction:     FALLING" in out


def test_price_command_has_estimate_scam_and_checklist_but_no_coach():
    code, out = run("price", "--listing", sample("bike_listing.txt"),
                    "--comparables", sample("bike_comparables.txt"))
    assert code == 0
    assert "1. FAIR PRICE ESTIMATE" in out and "2. SCAM CHECK" in out
    assert "MEETUP SAFETY CHECKLIST" in out
    assert "NEGOTIATION COACH" not in out


def test_negotiate_command_includes_coach():
    code, out = run("negotiate", "--listing", sample("bike_listing.txt"),
                    "--comparables", sample("bike_comparables.txt"))
    assert code == 0 and "3. NEGOTIATION COACH" in out and "[counter-offer]" in out


def test_report_command_with_observations_adds_trend_last():
    code, out = run("report", "--listing", sample("bike_listing.txt"),
                    "--comparables", sample("bike_comparables.txt"),
                    "--observations", sample("switch_observations.txt"))
    assert code == 0
    assert out.index("4. MEETUP SAFETY CHECKLIST") < out.index("5. PRICE TREND WATCH")


def test_trend_command():
    code, out = run("trend", "--observations", sample("switch_observations.txt"), "--category", "Switch")
    assert code == 0 and "PRICE TREND WATCH: Switch" in out and "Spread:" in out


def test_options_as_of_and_depreciation_change_the_numbers():
    _, base = run("price", "--listing", sample("bike_listing.txt"),
                  "--comparables", sample("bike_comparables.txt"))
    _, later = run("price", "--listing", sample("bike_listing.txt"),
                   "--comparables", sample("bike_comparables.txt"),
                   "--as-of", "2027-06-01", "--depreciation", "30%")
    flat = " ".join(later.split())
    assert "reference date 2027-06-01" in flat and "depreciation 30% per year" in flat
    assert base != later


def test_listing_without_comparables_still_reports():
    code, out = run("negotiate", "--listing", sample("guitar_listing.txt"))
    assert code == 0 and "not available" in out and "MEETUP SAFETY CHECKLIST" in out


def test_missing_file_is_a_clean_error():
    code, _ = run("price", "--listing", "/nonexistent/listing.txt")
    assert code == 1


def test_no_command_prints_help():
    code, out = run()
    assert code == 2 and "usage" in out.lower()


def test_module_entry_point_and_stdin():
    listing = (SAMPLE_DIR / "phone_listing.txt").read_text()
    proc = subprocess.run([sys.executable, "-m", "marketplace_trust", "price", "--listing", "-"],
                          input=listing, capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "PAYMENT SAFETY" in proc.stdout
