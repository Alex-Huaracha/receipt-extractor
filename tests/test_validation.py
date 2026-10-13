from datetime import date

import pytest

from app.schemas.receipt import Receipt, Severity
from app.services.validation import has_errors, validate

TODAY = date(2026, 10, 13)


def make_receipt(**overrides) -> Receipt:
    """A coherent online order: 19.98 + 5.99 shipping + 1.82 tax = 27.79."""
    data = {
        "document_type": "order",
        "issue_date": "2026-10-05",
        "country": "US",
        "currency": "USD",
        "issuer": {"name": "Amazon.com Services LLC"},
        "items": [{"description": "USB-C Cable", "quantity": 2, "unit_price": 9.99, "total": 19.98}],
        "subtotal": 19.98,
        "shipping": 5.99,
        "taxes": [{"name": "Sales Tax", "rate": 0.07, "amount": 1.82}],
        "total": 27.79,
    }
    data.update(overrides)
    return Receipt.model_validate(data)


def fields(issues, severity):
    return [issue.field for issue in issues if issue.severity is severity]


def test_coherent_receipt_has_no_issues():
    assert validate(make_receipt(), TODAY) == []


def test_tax_included_in_prices_is_coherent():
    receipt = make_receipt(
        items=[{"description": "Lunch menu", "quantity": 1, "unit_price": 12.10, "total": 12.10}],
        subtotal=12.10,
        shipping=None,
        taxes=[{"name": "VAT", "rate": 0.21, "amount": 2.10}],
        total=12.10,
    )
    assert validate(receipt, TODAY) == []


@pytest.mark.parametrize("subtotal", [45.00, 40.00], ids=["discount-at-the-end", "discount-already-applied"])
def test_discount_is_coherent_either_way(subtotal):
    receipt = make_receipt(
        items=[{"description": "Groceries", "total": 45.00}],
        subtotal=subtotal,
        discount=5.00,
        shipping=None,
        taxes=[],
        total=40.00,
    )
    assert validate(receipt, TODAY) == []


def test_missing_required_fields_are_errors():
    issues = validate(make_receipt(issue_date=None, issuer=None, total=None), TODAY)
    assert fields(issues, Severity.ERROR) == ["issue_date", "issuer", "total"]
    assert has_errors(issues)


def test_total_that_does_not_add_up_is_an_error():
    issues = validate(make_receipt(total=72.79), TODAY)
    assert fields(issues, Severity.ERROR) == ["total"]


def test_totals_are_not_checked_without_subtotal():
    assert validate(make_receipt(subtotal=None, items=[], total=99.00), TODAY) == []


def test_small_rounding_differences_are_tolerated():
    assert validate(make_receipt(total=27.82), TODAY) == []


def test_item_line_that_does_not_match_is_a_warning():
    receipt = make_receipt(
        items=[{"description": "USB-C Cable", "quantity": 3, "unit_price": 9.99, "total": 19.98}]
    )
    issues = validate(receipt, TODAY)
    assert fields(issues, Severity.WARNING) == ["items[0]"]
    assert not has_errors(issues)


def test_items_that_do_not_add_up_are_a_warning():
    receipt = make_receipt(items=[{"description": "USB-C Cable", "total": 10.00}])
    assert fields(validate(receipt, TODAY), Severity.WARNING) == ["items"]


def test_future_date_is_a_warning():
    issues = validate(make_receipt(issue_date="2027-01-01"), TODAY)
    assert fields(issues, Severity.WARNING) == ["issue_date"]


def test_invalid_codes_are_warnings():
    issues = validate(make_receipt(country="usa", currency="XX"), TODAY)
    assert fields(issues, Severity.WARNING) == ["country", "currency"]
