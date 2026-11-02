"""Command line interface. Reads pasted text from files (or '-' for stdin)."""

import argparse
import sys

from .analysis import analyze
from .parsing import parse_date, parse_observations
from .report import listing_report, trend_report
from .samples import LISTING_SAMPLES, TREND_SAMPLE, read_sample
from .trend import analyze_trend

DESCRIPTION = """Marketplace Trust: check a pasted secondhand listing.
Works from pasted text only. Nothing is fetched and no accounts are used."""


def read_text(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def as_of_date(text):
    parsed = parse_date(text)
    if parsed is None:
        raise argparse.ArgumentTypeError(f"not a date: {text!r} (use YYYY-MM-DD)")
    return parsed


def rate(text):
    value = float(text.rstrip("%"))
    value = value / 100 if value > 1 else value
    if not 0 <= value < 1:
        raise argparse.ArgumentTypeError("depreciation must be between 0 and 1 (or 0-99%)")
    return value


def add_listing_args(parser, observations=False):
    parser.add_argument("--listing", required=True, help="file with the pasted listing ('-' for stdin)")
    parser.add_argument("--comparables", help="file with pasted comparables, one per line: "
                                              "item | price | condition | date | region")
    if observations:
        parser.add_argument("--observations", help="optional file of price observations for a trend section")
    parser.add_argument("--as-of", type=as_of_date, help="reference date for depreciation "
                                                         "(default: the listing's date, else today)")
    parser.add_argument("--depreciation", type=rate, help="annual depreciation, e.g. 0.15 or 15%% "
                                                          "(default: by category)")


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m marketplace_trust", description=DESCRIPTION)
    parser.add_argument("--demo", action="store_true", help="run built-in samples showing every feature")
    sub = parser.add_subparsers(dest="command")
    add_listing_args(sub.add_parser("price", help="fair price estimate + scam check + safety checklist"))
    add_listing_args(sub.add_parser("negotiate", help="price + scam check + negotiation coach + safety checklist"))
    add_listing_args(sub.add_parser("report", help="everything in one report (optionally with a trend)"),
                     observations=True)
    trend = sub.add_parser("trend", help="price trend watch for one category")
    trend.add_argument("--observations", required=True, help="file of 'date | price | condition' lines")
    trend.add_argument("--category", default="", help="category name for the report title")
    return parser


def run_listing(args, with_strategy):
    comparables = read_text(args.comparables) if args.comparables else ""
    observations = read_text(args.observations) if getattr(args, "observations", None) else None
    result = analyze(read_text(args.listing), comparables, observations,
                     as_of=args.as_of, rate=args.depreciation)
    strategy = result.strategy if with_strategy else None
    return listing_report(result.listing, result.estimate, result.scam, strategy, result.trend)


def run_trend(args):
    trend = analyze_trend(parse_observations(read_text(args.observations)))
    return trend_report(trend, args.category)


def run_demo():
    parts = ["MARKETPLACE TRUST DEMO: built-in sample pastes, analysed offline.\n"]
    for label, listing_file, comps_file in LISTING_SAMPLES:
        parts.append(f"\n##### SAMPLE: {label} #####\n# files: {listing_file}, {comps_file}\n")
        result = analyze(read_sample(listing_file), read_sample(comps_file))
        parts.append(listing_report(result.listing, result.estimate, result.scam, result.strategy))
    category, obs_file = TREND_SAMPLE
    parts.append(f"\n##### SAMPLE: price trend watch #####\n# file: {obs_file}\n")
    parts.append(trend_report(analyze_trend(parse_observations(read_sample(obs_file))), category))
    return "".join(parts)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.demo:
            output = run_demo()
        elif args.command in ("price", "negotiate", "report"):
            output = run_listing(args, with_strategy=args.command != "price")
        elif args.command == "trend":
            output = run_trend(args)
        else:
            parser.print_help()
            return 2
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(output)
    return 0
