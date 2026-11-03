from pydantic import BaseModel, Field
from typing import Optional


class InvoiceCreate(BaseModel):
    invoice_id: str
    customer_id: str
    account_id: str
    total_amount: float = Field(..., gt=0)
    due_date: str


class InvoiceRead(BaseModel):
    invoice_id: str
    customer_id: str
    account_id: str
    total_amount: float
    due_date: str
    status: str = "open"
