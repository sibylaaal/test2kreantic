from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


CustomerSegment = Literal["consumer", "business"]
CustomerStatus = Literal["active", "suspended", "closed"]
SubscriptionServiceType = Literal["mobile", "fixed_broadband", "tv"]
SubscriptionStatus = Literal["pending", "active", "suspended", "cancelled"]


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=8, max_length=16)
    segment: CustomerSegment = "consumer"


class CustomerRead(BaseModel):
    customer_id: UUID
    full_name: str
    email: str
    phone: str
    segment: CustomerSegment
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime


class SubscriptionCreate(BaseModel):
    plan_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{1,39}$")
    service_type: SubscriptionServiceType
    start_date: date = Field(default_factory=date.today)


class SubscriptionRead(BaseModel):
    subscription_id: UUID
    customer_id: UUID
    plan_code: str
    service_type: SubscriptionServiceType
    status: SubscriptionStatus
    start_date: date
    activated_at: datetime | None
    created_at: datetime
    updated_at: datetime
