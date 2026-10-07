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


class DocumentType(StrEnum):
    INVOICE = "invoice"  # tax invoice issued to a business (RUC)
    RECEIPT = "receipt"  # sales receipt issued to a consumer
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    TICKET = "ticket"
    OTHER = "other"


class Currency(StrEnum):
    PEN = "PEN"
    USD = "USD"


class CustomerDocType(StrEnum):
    DNI = "DNI"
    RUC = "RUC"
    CE = "CE"  # foreign resident ID card
    PASSPORT = "PASSPORT"


class Item(BaseModel):
    description: str
    quantity: Money | None = None
    unit_price: Money | None = None
    discount: Money | None = None
    total: Money | None = None


class Receipt(BaseModel):
    """Data printed on a receipt or invoice. Any unreadable field must be null, never guessed."""

    document_type: DocumentType | None = None
    series: str | None = Field(None, description="e.g. F001, B001, or 0001 for paper receipts")
    number: str | None = Field(None, description="Correlative number without leading zeros")
    issue_date: date | None = None
    currency: Currency | None = None

    issuer_ruc: str | None = Field(None, description="Issuer RUC, 11 digits")
    issuer_name: str | None = None

    customer_doc_type: CustomerDocType | None = None
    customer_doc_number: str | None = None
    customer_name: str | None = None

    taxable_amount: Money | None = Field(None, description="Taxable amount before IGV (printed as OP. GRAVADA)")
    exempt_amount: Money | None = Field(None, description="Tax-exempt amount (printed as OP. EXONERADA)")
    unaffected_amount: Money | None = Field(None, description="Non-taxable amount (printed as OP. INAFECTA)")
    discount_amount: Money | None = Field(None, description="Total discounts")
    igv: Money | None = None
    other_charges: Money | None = Field(None, description="Plastic bag tax (ICBPER), tips, surcharges")
    total: Money | None = None

    items: list[Item] = []


class Source(StrEnum):
    LLM = "llm"
    LLM_QR = "llm+qr"  # key fields confirmed by the SUNAT QR code


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
    source: Source
    issues: list[Issue] = []
    needs_review: bool
    usage: Usage | None = None
