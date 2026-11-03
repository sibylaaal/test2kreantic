from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BillingAccountCreate(BaseModel):
    account_id: str
    customer_id: str
    balance: float = 0.0
    currency: str = "MAD"


class BillingAccountRead(BaseModel):
    account_id: str
    customer_id: str
    balance: float
    currency: str
    status: str = "active"


class ChargeCreate(BaseModel):
    charge_id: str
    account_id: str
    amount: float = Field(..., gt=0)
    description: str


class BillingSubscriptionRead(BaseModel):
    subscription_id: UUID
    customer_id: UUID
    plan_code: str
    service_type: str
    status: str
    activated_at: datetime
    last_event_id: UUID
    updated_at: datetime
