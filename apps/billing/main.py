from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Query
from psycopg import Connection

from apps.billing.database import get_connection, initialize_database
from apps.billing.schemas import (
    BillingAccountCreate,
    BillingAccountRead,
    BillingSubscriptionRead,
    ChargeCreate,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Billing Service", version="0.1.0", lifespan=lifespan)
ACCOUNTS = {}


@app.get("/")
def root() -> dict:
    return {"service": "billing", "message": "Billing service is ready"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "billing"}


@app.post("/accounts", response_model=BillingAccountRead)
def create_account(account: BillingAccountCreate) -> BillingAccountRead:
    ACCOUNTS[account.account_id] = account.model_dump()
    return BillingAccountRead(**account.model_dump())


@app.post("/charges")
def create_charge(charge: ChargeCreate) -> dict:
    return {
        "status": "created",
        "charge_id": charge.charge_id,
        "account_id": charge.account_id,
        "amount": charge.amount,
        "description": charge.description,
    }


@app.get("/subscriptions", response_model=list[BillingSubscriptionRead])
def list_subscriptions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    connection: Connection = Depends(get_connection),
) -> Any:
    return connection.execute(
        """
        SELECT subscription_id, customer_id, plan_code, service_type, status,
               activated_at, last_event_id, updated_at
        FROM billing.subscriptions
        ORDER BY updated_at DESC, subscription_id
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()
