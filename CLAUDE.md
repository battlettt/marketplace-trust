# CLAUDE.md - Marketplace Trust

## What this is
A marketplace trust suite for secondhand buying and selling: fair price
estimation from comparables with condition grading, depreciation, and
regional adjustment; listing scam detection (too-good prices, pressure
tactics, risky payment methods, seller red flags); a negotiation coach
with offer strategy and message drafts; a meetup safety checklist; and
a price trend watch for a category.

## Principles
- Pasted text only. No scraping, no marketplace accounts, no network
  calls to marketplaces.
- Price estimates show their reasoning: comparables, condition, and
  adjustments, not a single unexplained number.
- Safety first: risky payment methods and meetup risks are flagged
  prominently, never buried.
- Python standard library only for the core. No dependencies to install.

## Build, test, run
- Run: `python -m marketplace_trust` (see README for commands)
- Tests: plain asserts, runnable with or without pytest:
  `python -m pytest`
- Keep pricing, scam detection, negotiation, and reporting separate so
  each can be tested alone.

## Conventions
- Small functions, clear names, minimal abstraction.
- Every feature ships with tests and a README section.
- A browser demo is optional; if built, it must run offline and match
  the CLI's numbers exactly.
