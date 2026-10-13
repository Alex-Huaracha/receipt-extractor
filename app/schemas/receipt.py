from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, WithJsonSchema

# Decimal keeps cents exact for validations; in JSON it is exposed as a plain number.
Money = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
    WithJsonSchema({"type": "number"}),
]
Rate = Money


class DocumentType(StrEnum):
    INVOICE = "invoice"  # tax invoice, usually issued to a business
    RECEIPT = "receipt"  # proof of payment from a store, restaurant, etc.
    ORDER = "order"  # online order confirmation (Amazon, Temu, AliExpress...)
    CREDIT_NOTE = "credit_note"
    OTHER = "other"


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    OTHER = "other"


class Party(BaseModel):
    name: str | None = None
    tax_id: str | None = Field(
        None, description="Tax identification number as printed (e.g. RUC, VAT number, EIN, RFC)"
    )


class Tax(BaseModel):
    name: str = Field(description="Tax name as printed (e.g. IGV, VAT, IVA, Sales Tax, GST)")
    rate: Rate | None = Field(None, description="Rate as a fraction, e.g. 0.18 for 18%")
    amount: Money


class Item(BaseModel):
    description: str
    quantity: Money | None = None
    unit_price: Money | None = None
    discount: Money | None = None
    total: Money | None = None


class Receipt(BaseModel):
    """Data printed on a receipt, invoice or order. Any unreadable field must be null, never guessed."""

    document_type: DocumentType | None = None
    document_number: str | None = Field(
        None, description="Identifier as printed (e.g. B001-4521, INV-2041, order 112-4589321-7765012)"
    )
    issue_date: date | None = None
    country: str | None = Field(
        None, description="ISO 3166-1 alpha-2 code of the issuing country (e.g. PE, US, CN), inferred from the document"
    )
    currency: str | None = Field(None, description="ISO 4217 code (e.g. PEN, USD, EUR, CNY)")

    issuer: Party | None = None
    customer: Party | None = None

    items: list[Item] = []

    subtotal: Money | None = Field(None, description="Amount before taxes, discounts and shipping")
    discount: Money | None = Field(None, description="Total discounts, as a positive number")
    shipping: Money | None = None
    taxes: list[Tax] = []
    tip: Money | None = None
    total: Money | None = Field(None, description="Final amount paid or due")

    payment_method: PaymentMethod | None = None


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class Issue(BaseModel):
    field: str
    message: str
    severity: Severity


class Usage(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ExtractionResult(BaseModel):
    receipt: Receipt
    issues: list[Issue] = []
    needs_review: bool
    usage: Usage | None = None
