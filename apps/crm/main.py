from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from psycopg import Connection
from psycopg.types.json import Jsonb

from apps.crm.database import get_connection, initialize_database
from apps.crm.schemas import (
    CustomerCreate,
    CustomerRead,
    SubscriptionCreate,
    SubscriptionRead,
)
from apps.shared.events import DomainEvent


CRM_EVENTS_TOPIC = "telecom.crm.events.v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="CRM Service", version="0.1.0", lifespan=lifespan)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "crm", "message": "CRM service is ready"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "crm"}


@app.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer: CustomerCreate,
    connection: Connection = Depends(get_connection),
) -> Any:
    row = connection.execute(
        """
        INSERT INTO crm.customers (full_name, email, phone, segment)
        VALUES (%s, %s, %s, %s)
        RETURNING customer_id, full_name, email, phone, segment, status, created_at, updated_at
        """,
        (customer.full_name, customer.email, customer.phone, customer.segment),
    ).fetchone()
    return row


@app.get("/customers", response_model=list[CustomerRead])
def list_customers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    connection: Connection = Depends(get_connection),
) -> Any:
    rows = connection.execute(
        """
        SELECT customer_id, full_name, email, phone, segment, status, created_at, updated_at
        FROM crm.customers
        ORDER BY created_at DESC, customer_id
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()
    return rows


@app.get("/customers/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: UUID,
    connection: Connection = Depends(get_connection),
) -> Any:
    row = connection.execute(
        """
        SELECT customer_id, full_name, email, phone, segment, status, created_at, updated_at
        FROM crm.customers
        WHERE customer_id = %s
        """,
        (customer_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return row


@app.post(
    "/customers/{customer_id}/subscriptions",
    response_model=SubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    customer_id: UUID,
    subscription: SubscriptionCreate,
    connection: Connection = Depends(get_connection),
) -> Any:
    customer = connection.execute(
        "SELECT status FROM crm.customers WHERE customer_id = %s",
        (customer_id,),
    ).fetchone()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active customers can request a subscription",
        )

    return connection.execute(
        """
        INSERT INTO crm.subscriptions (customer_id, plan_code, service_type, start_date)
        VALUES (%s, %s, %s, %s)
        RETURNING subscription_id, customer_id, plan_code, service_type, status,
                  start_date, activated_at, created_at, updated_at
        """,
        (customer_id, subscription.plan_code, subscription.service_type, subscription.start_date),
    ).fetchone()


@app.get(
    "/customers/{customer_id}/subscriptions",
    response_model=list[SubscriptionRead],
)
def list_customer_subscriptions(
    customer_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    connection: Connection = Depends(get_connection),
) -> Any:
    customer = connection.execute(
        "SELECT 1 FROM crm.customers WHERE customer_id = %s",
        (customer_id,),
    ).fetchone()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    return connection.execute(
        """
        SELECT subscription_id, customer_id, plan_code, service_type, status,
               start_date, activated_at, created_at, updated_at
        FROM crm.subscriptions
        WHERE customer_id = %s
        ORDER BY created_at DESC, subscription_id
        LIMIT %s OFFSET %s
        """,
        (customer_id, limit, offset),
    ).fetchall()


@app.get("/subscriptions", response_model=list[SubscriptionRead])
def list_subscriptions(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    connection: Connection = Depends(get_connection),
) -> Any:
    return connection.execute(
        """
        SELECT subscription_id, customer_id, plan_code, service_type, status,
               start_date, activated_at, created_at, updated_at
        FROM crm.subscriptions
        ORDER BY created_at, subscription_id
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


@app.post(
    "/subscriptions/{subscription_id}/activate",
    response_model=SubscriptionRead,
)
def activate_subscription(
    subscription_id: UUID,
    connection: Connection = Depends(get_connection),
) -> Any:
    row = connection.execute(
        """
        UPDATE crm.subscriptions
        SET status = 'active', activated_at = now(), updated_at = now()
        WHERE subscription_id = %s AND status = 'pending'
        RETURNING subscription_id, customer_id, plan_code, service_type, status,
                  start_date, activated_at, created_at, updated_at
        """,
        (subscription_id,),
    ).fetchone()
    if row is not None:
        event = DomainEvent.create(
            event_name="subscription.activated",
            source="crm-service",
            payload={
                "subscription_id": str(row["subscription_id"]),
                "customer_id": str(row["customer_id"]),
                "plan_code": row["plan_code"],
                "service_type": row["service_type"],
                "activated_at": row["activated_at"].isoformat(),
            },
            correlation_id=str(row["subscription_id"]),
        )
        connection.execute(
            """
            INSERT INTO crm.outbox_events (event_id, topic, event_payload)
            VALUES (%s, %s, %s)
            """,
            (event.event_id, CRM_EVENTS_TOPIC, Jsonb(event.to_dict())),
        )
        return row

    existing = connection.execute(
        "SELECT status FROM crm.subscriptions WHERE subscription_id = %s",
        (subscription_id,),
    ).fetchone()
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Cannot activate a subscription with status '{existing['status']}'",
    )
