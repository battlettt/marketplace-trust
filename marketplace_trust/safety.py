"""Meetup safety checklist and payment warnings.

The core checklist and payment warnings are always included, word for word,
whatever the listing says. Extra items are added for the item type, price,
and any red flags found.
"""

CORE_CHECKLIST = [
    "Meet in a public place, in daylight. A police station or 'safe exchange zone' lobby is ideal.",
    "Bring someone with you, and tell another person where you're going and when.",
    "Verify the item works and matches the listing (model, condition, accessories) before paying.",
    "Pay only after verification: cash, or a secure in-person payment, handed over at the meetup.",
]

PAYMENT_WARNINGS = [
    "Never e-transfer or send app payments in advance to a stranger.",
    "Never pay with gift cards. No genuine seller asks for them.",
    "Never wire money or use a money-transfer service (Western Union, MoneyGram).",
    "Never pay in crypto, and never pay a 'deposit' to hold an item.",
    "Never open payment links sent by a seller; keep messages on the platform.",
]

CATEGORY_CHECKS = {
    "phone": "Check the phone is not carrier-locked, blacklisted, or still signed in to the "
             "seller's account (it should be reset in front of you).",
    "computer": "Boot it, check the specs in system settings, and make sure it is signed out of "
                "the seller's account and not locked by an organisation.",
    "electronics": "Power it on and test the main functions; check the serial number matches any box or receipt.",
    "bike": "Check the frame serial number, ask how they got it, and take a short test ride.",
    "furniture": "Inspect for damage, stains, and pests before it goes in your car.",
    "tools": "Run the tool under load and check for missing parts or batteries.",
    "instrument": "Play it, check the neck/keys/hardware, and look for cracks.",
}

HIGH_VALUE = 500


def checklist(estimate=None, scam_report=None):
    """Return the full checklist: core items first, then context-specific extras."""
    items = list(CORE_CHECKLIST)
    category = estimate.category if estimate is not None else "general"
    if category in CATEGORY_CHECKS:
        items.append(CATEGORY_CHECKS[category])
    asking = estimate.asking if estimate is not None else None
    if asking and asking >= HIGH_VALUE:
        items.append(f"This is a high-value purchase (${asking:,.0f}). Meet at a police station "
                     "safe exchange spot or inside your bank.")
    if scam_report is not None and scam_report.signals:
        items.append("Red flags were found above. If the seller pushes back on any item in this "
                     "list, walk away.")
    return items


def payment_warnings():
    return list(PAYMENT_WARNINGS)
