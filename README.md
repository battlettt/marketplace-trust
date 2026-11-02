# Marketplace Trust

A trust toolkit for secondhand marketplace buyers. Paste a listing, plus a few
comparable listings if you have them, and get a full trust report:

1. **Fair price estimate**: a price *range* built from comparables, with the
   reasoning shown (condition grading, depreciation, regional adjustment).
2. **Scam check**: too-good prices, pressure tactics, risky payment methods,
   seller red flags, and stolen-photo / copied-text signals, with a verdict.
3. **Negotiation coach**: opening offer, target, walk-away price, and short,
   honest message drafts.
4. **Meetup safety checklist**: always included, never buried.
5. **Price trend watch**: direction and spread for a category from pasted
   price observations.

**Pasted text only.** Nothing is fetched, no marketplace is scraped, and no
accounts are used. The tool works fully offline on Python 3.10+ with the
standard library only. There is nothing to install.

## Quick start

```sh
python -m marketplace_trust --demo
```

This runs the built-in samples in `marketplace_trust/sample_data/`: a fair
local deal, a likely scam, a listing with thin comparable data, and a price
trend. Together they show all five features.

## Commands

| Command | What you get |
| --- | --- |
| `python -m marketplace_trust price --listing L --comparables C` | Fair price estimate, scam check, meetup checklist |
| `python -m marketplace_trust negotiate --listing L --comparables C` | The same, plus the negotiation coach |
| `python -m marketplace_trust report --listing L --comparables C [--observations O]` | Everything, plus a trend section when observations are given |
| `python -m marketplace_trust trend --observations O [--category NAME]` | Price trend watch for one category |
| `python -m marketplace_trust --demo` | Built-in samples for all five features |

Options for `price`, `negotiate`, and `report`:

- `--listing -` reads the listing from stdin, so you can paste straight in:
  `python -m marketplace_trust negotiate --listing - --comparables comps.txt`, then
  paste and press Ctrl-D.
- `--comparables` is optional. Without it the report says no fair range is
  available instead of making one up.
- `--as-of YYYY-MM-DD` sets the reference date for depreciation. By default
  this is the listing's `Listed:` date, or today if the listing has none.
- `--depreciation 0.15` (or `15%`) overrides the annual depreciation rate,
  which otherwise depends on the category.

Every report uses the same section order: at a glance, 1. fair price,
2. scam check, 3. negotiation (for `negotiate` and `report`), 4. meetup
safety, and 5. trend (when `--observations` is given).

## Input formats

### Listing

Use `Key: value` lines. Description and seller notes can run over several
lines. Recognised keys are `Title`, `Price`, `Condition`, `Location` (or
`Region`), `Category`, `Listed`, `Payment`, `Description`, `Seller notes`,
and `Photos`. Every key is optional.

```text
Title: Trek FX 3 hybrid bike, 2021, size M
Price: $395
Condition: good
Location: Toronto, ON
Listed: 2026-10-28
Payment: Cash at pickup
Description:
Selling my Trek FX 3 hybrid. Good condition, recently serviced (new chain and
brake pads). Minor scratches on the top tube, otherwise clean. Happy for you
to take a test ride before you decide.
Seller notes:
Pickup near Union Station. Can meet at the police station lobby on weekends.
```

Freeform text works too. The first line becomes the title and the first `$`
amount becomes the price.

### Comparables

Use one line per comparable: `item | price | condition | date | region`.
Trailing fields can be left off. Lines starting with `#` are comments, and a
header row is skipped. Dates can be `2026-09-15`, `2026/09`, or `3 weeks ago`.

```text
# item | price | condition | date | region
Trek FX 3 Disc 2021 | $520 | like new | 2026-09-15 | Toronto
Trek FX 3 hybrid | $430 | good | 2026-08-02 | Toronto
Trek FX 3 2020 | $380 | some scratches | 2026-06-20 | Toronto
Trek FX 3 | $400 | good condition | 2026-10-01 | Ottawa
Trek FX 3 Disc | $360 | fair | 2026-07-11 | Ottawa
Trek FX 2 hybrid | $330 | good | 2025-11-30 | Ottawa
Trek FX 3 frame only | $90 | for parts | 2026-09-01 | Toronto
Specialized Sirrus 3.0 | $450 | good | 2026-09-10 | Toronto
Trek FX 3 | $650 | brand new | 2023-05-01 | Toronto
```

To set regional price levels yourself (1.00 = average market), add lines like
`@region Toronto 1.05`.

### Price observations (trend watch)

Use one line per observation: `date | price | condition`. The condition is
optional. `2026-03-02 $340 good` (space separated) also works.

```text
# Nintendo Switch OLED
2026-03-02 | $340 | good
2026-03-20 | $325 | good
2026-04-11 | $330 |
2026-05-03 | $310 | good
...
2026-10-12 | $260 | good
```

## 1. Fair price estimate

```sh
python -m marketplace_trust price \
  --listing marketplace_trust/sample_data/bike_listing.txt \
  --comparables marketplace_trust/sample_data/bike_comparables.txt
```

Each usable comparable is converted to "what this would cost if it were the
target item, today, in the target's region". The conversion takes three
visible steps:

1. **Condition.** The comparable and the target are each graded `like new`,
   `good`, `fair`, or `worn`. The price is scaled by
   `target multiplier / comparable multiplier`, where the multipliers are
   like new 1.15, good 1.00, fair 0.82, and worn 0.62.
2. **Depreciation.** `x (1 - annual rate) ^ (age in days / 365)`. The rate
   depends on the category: phones 30%, computers 25%, electronics 20%, bikes
   12%, furniture 10%, tools 8%, instruments 5%, anything else 15%. The
   category comes from `Category:` or from title keywords.
3. **Region.** `x target index / comparable index`. You can set indexes with
   `@region` lines. Otherwise they are derived from the comparables when at
   least 2 regions each have 2 or more comparables: each region's median is
   compared with the overall median, shrunk halfway toward 1.00, and capped
   at 0.85 to 1.15 so a few listings can't swing the result.

**Condition grading rules.** Condition phrases are matched longest first, so
"minor scratches" (good) wins over "scratches" (fair). Negated phrases such
as "no scratches" or "not broken" are ignored. When several grades match,
the most severe one wins. If there is no condition language at all, the item
is assumed to be `good` and the report says so. If the listing's
`Condition:` field claims better than its description admits (for example
"like new" next to "hinge is cracked"), the worse grade is used and the
mismatch is flagged.

**Comparables that are excluded**, each with its reason shown:

- an unreadable price or date
- no shared meaningful word with the listing title ("does not look like the
  same item")
- older than 3 years, or dated after the reference date
- outliers more than 2x away from the median (checked when there are 4 or
  more comparables)

**The range** is the interquartile spread of the adjusted values around
their median, at least +/-8% wide. Confidence is *high* with 5 or more tight
comparables and *medium* with 3 or more. **Thin data is handled honestly**:
with fewer than 3 usable comparables the range is widened to +/-25% and
confidence is *low*. With none, no number is given at all.

Worked example (excerpt):

```text
  Fair price range: $395 to $465 (midpoint $430, confidence: high)
  Asking price:     $395 (within the fair range)
  Target condition: graded 'good' from 'good'.
  Category:         bike, depreciation 12% per year (reference date
    2026-10-28)
  Regional index:   ottawa 0.97, toronto 1.01; derived from the comparables
    (shrunk halfway to 1.00, capped at 0.85-1.15). Target region: 'toronto'.

  Comparables used (6):
   # item                   price condition   age  cond  depr  regn adjusted
   1 Trek FX 3 Disc 2021     $520 like new    43d x0.87 x0.99 x1.00     $445
   2 Trek FX 3 hybrid        $430 good        87d x1.00 x0.97 x1.00     $417
   3 Trek FX 3 2020          $380 fair       130d x1.22 x0.96 x1.00     $443
   4 Trek FX 3               $400 good        27d x1.00 x0.99 x1.04     $412
   5 Trek FX 3 Disc          $360 fair       109d x1.22 x0.96 x1.04     $440
   6 Trek FX 2 hybrid        $330 good       332d x1.00 x0.89 x1.04     $306
  adjusted = price x condition (cond) x depreciation (depr) x region (regn)
  ...
  Excluded comparables (3):
    - line 8 'Trek FX 3 frame only': outlier (more than 2x away from the
      median)
    - line 9 'Specialized Sirrus 3.0': does not look like the same item
    - line 10 'Trek FX 3': older than 3 years
```

The guitar sample (`guitar_listing.txt` + `guitar_comparables.txt`) shows the
thin-data case: 2 usable comparables, a range of `$495 to $820`, and
`confidence: low`.

## 2. Scam check

```sh
python -m marketplace_trust price \
  --listing marketplace_trust/sample_data/phone_listing.txt \
  --comparables marketplace_trust/sample_data/phone_comparables.txt
```

The sample scam listing:

```text
Title: iPhone 15 Pro 256GB - BRAND NEW SEALED
Price: $350
Condition: Brand new
Location: Calgary, AB
Listed: 2026-10-27
Payment: E-transfer only
Description:
Brand new iPhone 15 Pro, still sealed in box. Free shipping. Key features: A17
Pro processor, 48MP camera. Photos are from the manufacturer website, actual
item may look different. I'm currently in Vancouver for work so my courier
will deliver it.
Seller notes:
Kindly send a $100 deposit by e-transfer to hold it, many people are
interested. Today only! Text me on WhatsApp at 403-555-0199.
100% legit, new account so no reviews yet.
```

Signals, each with a severity, a plain-English explanation, and the quoted
text that triggered it:

| Class | Examples | Severity |
| --- | --- | --- |
| Risky payment | payment or deposit before seeing the item, gift cards, wire / Western Union / MoneyGram, crypto | HIGH |
| | e-transfer / Zelle / Venmo / Cash App (HIGH when combined with paying in advance) | MEDIUM |
| Too-good price | under 50% of the fair midpoint (HIGH) or under 70% (MEDIUM); downgraded one level on thin data | HIGH / MEDIUM |
| Pressure tactics | "today only" deadlines, claims of competing buyers, moving off the platform (WhatsApp, phone numbers, emails, links) | MEDIUM |
| | general urgency ("asap", "won't last") | LOW |
| Seller red flags | refuses to meet or show the item; "I'm overseas / my agent will deliver" | HIGH |
| | shipping only, no history / new account, location doesn't match the listing, scripted text ("kindly", "100% legit", repeated sentences) | MEDIUM / LOW |
| | condition field contradicts the description | LOW |
| Stolen photos / copied text | stock or "for reference" photos, the description admits the photos show a different item, text copied from a retail page ("free shipping", "key features:", "in stock", SKU, ...) | MEDIUM |

**Verdict** (points: HIGH 3, MEDIUM 2, LOW 1):

- **LIKELY SCAM**: 2 or more HIGH signals, or 1 HIGH plus a total of 6 or
  more points, or 8 or more points.
- **SUSPICIOUS**: any HIGH signal, a MEDIUM too-good-price signal, or 3 or
  more points.
- **NO MAJOR RED FLAGS**: anything less.

Reasons are listed most serious first. At equal severity, payment risks come
first. When there is any payment signal, a **PAYMENT SAFETY: READ FIRST**
block opens the scam section and a **PAYMENT DANGER** line appears in the
at-a-glance header. Links quoted from a listing are defanged
(`hxxps://`, `example[.]com`), so the report never contains a live link.

Excerpt:

```text
2. SCAM CHECK: LIKELY SCAM
==============================================================================
  !! PAYMENT SAFETY: READ FIRST !!
    [HIGH] Asks for payment or a deposit before you see the item
    [HIGH] Requests an instant bank or app transfer
    - Never e-transfer or send app payments in advance to a stranger.
    ...
  Reasons, most serious first:
    1. [HIGH] Asks for payment or a deposit before you see the item (payment)
       Paying before you have seen and checked the item is the most common way
       buyers lose money. Legitimate sellers let you inspect first and are
       paid on the spot.
       found: "Kindly send a $100 deposit by e-transfer to hold it, many
              people are interested."
    2. [HIGH] Requests an instant bank or app transfer (payment)
    3. [HIGH] Price is far below the fair range (price)
       Asking $350 is 60% below the fair midpoint of $880. ...
    4. [HIGH] Seller says they are away and someone else will deliver (seller)
    5. [MEDIUM] Artificial deadline ("today only") (pressure)
    ...
```

## 3. Negotiation coach

```sh
python -m marketplace_trust negotiate \
  --listing marketplace_trust/sample_data/bike_listing.txt \
  --comparables marketplace_trust/sample_data/bike_comparables.txt
```

Offer math, where A is the asking price and the fair range is low / mid / high:

- **Walk-away** = `min(A, high)`. Never pay above the top of the fair range.
- **Target** = `min(A, mid)`.
- **Opening** = `max(85% of target, 90% of low)`, never above the target. The
  floor avoids insulting lowballs.
- If A is already at or below the fair low, the coach says to offer the
  asking price and put the effort into verifying the item.
- With no fair range, offers fall back to 85% / 92% / 100% of asking, marked
  low confidence.
- With a **LIKELY SCAM** verdict the coach gives no offer numbers. It says
  not to negotiate and offers a one-line decline.
- Amounts are rounded to $1 / $5 / $10 / $25 steps depending on size, and
  always kept in the order opening <= target <= walk-away <= asking.

The drafts are short and polite. They never invent competing offers or
deadlines, and they only ever offer to pay in person after seeing the item.

```text
  Open at $355, aim for $395, walk away above $395.
    Opening offer:   $355
    Target price:    $395
    Walk-away price: $395 (don't pay more than this)

  Message drafts:
    [opening offer]
      Hi, is the Trek FX 3 hybrid bike, 2021, size M still available? I've
      compared similar listings in good condition, and I'd like to offer $355.
      I can meet at a public place in daylight and pay once I've checked it
      works. Thanks!
    [counter-offer]
      Thanks for getting back to me. I can come up to $395, which is in line
      with what similar ones are listed for. If that works, I can meet at a
      public spot and pay after seeing it in person.
    [walking away]
      Thanks for your time. $395 is the most I can do, so I'll pass for now.
      If anything changes, feel free to message me. Good luck with the sale!
```

## 4. Meetup safety checklist

Every listing report includes this checklist, whatever the verdict. A
one-line meetup rule also sits in the at-a-glance header at the top.

```text
4. MEETUP SAFETY CHECKLIST (always follow)
==============================================================================
  [ ] Meet in a public place, in daylight. A police station or 'safe exchange
      zone' lobby is ideal.
  [ ] Bring someone with you, and tell another person where you're going and
      when.
  [ ] Verify the item works and matches the listing (model, condition,
      accessories) before paying.
  [ ] Pay only after verification: cash, or a secure in-person payment, handed
      over at the meetup.
  [ ] Check the phone is not carrier-locked, blacklisted, or still signed in
      to the seller's account (it should be reset in front of you).
  [ ] Red flags were found above. If the seller pushes back on any item in
      this list, walk away.
  Payment safety:
    - Never e-transfer or send app payments in advance to a stranger.
    - Never pay with gift cards. No genuine seller asks for them.
    - Never wire money or use a money-transfer service (Western Union,
      MoneyGram).
    - Never pay in crypto, and never pay a 'deposit' to hold an item.
    - Never open payment links sent by a seller; keep messages on the
      platform.
```

Extra items are added for the item type (phone, computer, bike, ...), for
high-value purchases ($500 and up), and when red flags were found.

## 5. Price trend watch

```sh
python -m marketplace_trust trend \
  --observations marketplace_trust/sample_data/switch_observations.txt \
  --category "Nintendo Switch OLED"
```

How the trend is read:

- Prices that come with a condition are first normalised to `good`, so a run
  of worn items doesn't look like a falling market.
- A least-squares line through (day, price) gives the drift: the change per
  30 days as a share of the median price.
- Drift under 2% a month, or a noisy fit (R² under 0.25), reads as **flat**.
  Otherwise the trend is **rising** or **falling**.
- With fewer than 5 observations, or less than 14 days covered, the report
  says the data is too thin and gives no direction. The spread is still
  shown.

```text
==============================================================================
PRICE TREND WATCH: Nintendo Switch OLED
==============================================================================
  Observations:  11 from 2026-03-02 to 2026-10-12
  Spread:        min $230, median $300, max $340
  Direction:     FALLING (-3.2% per month, fit R^2 0.96)
  Read: Prices for this category are drifting down (about 3% a month). If
    you're not in a hurry, waiting may help, and sellers may accept lower
    offers.
```

To put a trend section at the end of a full listing report, add
`--observations` to `report`.

## Tests

The tests use plain asserts and run with or without pytest:

```sh
python -m pytest          # if pytest is installed
python tests/run_tests.py # no dependencies
```

The suite covers parsing, condition grading, price estimation (comparables,
condition, depreciation, regional adjustment, thin data, exclusions), every
scam signal class and the verdict rules, offer math and walk-away logic,
trend direction / spread / thin data, safety output (checklist and payment
warnings in every report, no live links, no advice that encourages risky
payment), the CLI, and an offline check. The offline check fails if the
package imports a network or non-standard-library module.

## Layout

```text
marketplace_trust/
  parsing.py      pasted listing / comparables / observations -> data
  condition.py    condition grading rules
  pricing.py      fair price range from comparables
  scam.py         scam signals and verdict
  negotiation.py  offer strategy and message drafts
  safety.py       meetup checklist and payment warnings
  trend.py        price trend watch
  report.py       plain-text report layout
  analysis.py     runs every feature on pasted text
  cli.py          command line
  sample_data/    sample pastes used by --demo and this README
tests/            plain-assert tests + run_tests.py
```

There is no browser demo. The CLI `--demo` is the demo.

## Limits

This is a set of transparent heuristics, not a guarantee. A clean report
does not prove a listing is genuine, so always follow the meetup checklist.
Price estimates are only as good as the comparables you paste.
