"""Coherence checks on extracted data. The model can misread a number; arithmetic catches it."""

import re
from datetime import date
from decimal import Decimal

from app.schemas.receipt import Issue, Receipt, Severity

# Receipts round to 2 decimals, so exact equality would flag correct documents.
TOLERANCE = Decimal("0.05")
ZERO = Decimal(0)


def validate(receipt: Receipt, today: date | None = None) -> list[Issue]:
    return [
        *check_required_fields(receipt),
        *check_totals(receipt),
        *check_items(receipt),
        *check_date(receipt, today or date.today()),
        *check_codes(receipt),
    ]


def has_errors(issues: list[Issue]) -> bool:
    return any(issue.severity is Severity.ERROR for issue in issues)


def check_required_fields(receipt: Receipt) -> list[Issue]:
    issues = []
    if receipt.issue_date is None:
        issues.append(_error("issue_date", "Issue date is missing"))
    if receipt.issuer is None or not (receipt.issuer.name or receipt.issuer.tax_id):
        issues.append(_error("issuer", "Issuer is missing"))
    if receipt.total is None:
        issues.append(_error("total", "Total is missing"))
    return issues


def check_totals(receipt: Receipt) -> list[Issue]:
    if receipt.total is None or receipt.subtotal is None:
        return []

    base = receipt.subtotal + (receipt.shipping or ZERO) + (receipt.tip or ZERO)
    taxes = sum((tax.amount for tax in receipt.taxes), ZERO)
    discount = abs(receipt.discount or ZERO)

    # Taxes may be added on top or already included in the prices;
    # the discount may be subtracted at the end or already applied to the subtotal.
    candidates = {
        base + tax_part - discount_part
        for tax_part in {taxes, ZERO}
        for discount_part in {discount, ZERO}
    }
    if any(_close(candidate, receipt.total) for candidate in candidates):
        return []
    return [
        _error(
            "total",
            f"Amounts do not add up to the total {receipt.total} "
            f"(subtotal {receipt.subtotal}, discount {discount}, taxes {taxes}, "
            f"shipping {receipt.shipping or ZERO}, tip {receipt.tip or ZERO})",
        )
    ]


def check_items(receipt: Receipt) -> list[Issue]:
    issues = []

    for index, item in enumerate(receipt.items):
        if item.quantity is None or item.unit_price is None or item.total is None:
            continue
        expected = item.quantity * item.unit_price - abs(item.discount or ZERO)
        if not _close(expected, item.total):
            issues.append(
                _warning(
                    f"items[{index}]",
                    f"{item.quantity} x {item.unit_price} does not match the item total {item.total}",
                )
            )

    item_totals = [item.total for item in receipt.items if item.total is not None]
    if not item_totals or len(item_totals) != len(receipt.items):
        return issues

    items_sum = sum(item_totals, ZERO)
    discount = abs(receipt.discount or ZERO)
    references = [ref for ref in (receipt.subtotal, receipt.total) if ref is not None]
    # Items may be listed before a global discount is applied.
    references += [ref + discount for ref in references]
    if references and not any(_close(items_sum, ref) for ref in references):
        issues.append(
            _warning("items", f"Items add up to {items_sum}, which does not match the subtotal or total")
        )
    return issues


def check_date(receipt: Receipt, today: date) -> list[Issue]:
    if receipt.issue_date is not None and receipt.issue_date > today:
        return [_warning("issue_date", f"Issue date {receipt.issue_date} is in the future")]
    return []


def check_codes(receipt: Receipt) -> list[Issue]:
    issues = []
    if receipt.country is not None and not re.fullmatch(r"[A-Z]{2}", receipt.country):
        issues.append(_warning("country", f"'{receipt.country}' is not an ISO 3166-1 alpha-2 code"))
    if receipt.currency is not None and not re.fullmatch(r"[A-Z]{3}", receipt.currency):
        issues.append(_warning("currency", f"'{receipt.currency}' is not an ISO 4217 code"))
    return issues


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def _error(field: str, message: str) -> Issue:
    return Issue(field=field, message=message, severity=Severity.ERROR)


def _warning(field: str, message: str) -> Issue:
    return Issue(field=field, message=message, severity=Severity.WARNING)
