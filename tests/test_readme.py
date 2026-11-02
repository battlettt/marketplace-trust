"""README excerpts must match what the tool really prints."""

import re
from pathlib import Path

from marketplace_trust.cli import run_demo
from marketplace_trust.parsing import parse_observations
from marketplace_trust.report import trend_report
from marketplace_trust.samples import SAMPLE_DIR, read_sample
from marketplace_trust.trend import analyze_trend

README = Path(__file__).resolve().parent.parent / "README.md"


def test_readme_excerpts_match_real_output():
    trend = trend_report(analyze_trend(parse_observations(read_sample("switch_observations.txt"))),
                         "Nintendo Switch OLED")
    samples = "".join(p.read_text(encoding="utf-8") for p in sorted(SAMPLE_DIR.iterdir()))
    real = run_demo() + trend + samples
    for block in re.findall(r"```text\n(.*?)```", README.read_text(encoding="utf-8"), re.S):
        if block.startswith("marketplace_trust/"):
            continue  # the layout tree
        for line in block.splitlines():
            if line.strip() and "..." not in line:
                assert line in real, f"README line not in real output: {line!r}"


def test_readme_documents_every_command():
    text = README.read_text(encoding="utf-8")
    for command in ("price", "negotiate", "report", "trend", "--demo"):
        assert f"python -m marketplace_trust {command}" in text, command
