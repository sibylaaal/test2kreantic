import os
from collections.abc import Generator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


def connect() -> Connection:
    database_url = os.getenv("BILLING_DATABASE_URL")
    if not database_url:
        raise RuntimeError("BILLING_DATABASE_URL must be set before Billing can start")

    return psycopg.connect(database_url, row_factory=dict_row)


def initialize_database() -> None:
    with connect() as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS billing")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS billing.subscriptions (
                subscription_id UUID PRIMARY KEY,
                customer_id UUID NOT NULL,
                plan_code TEXT NOT NULL,
                service_type TEXT NOT NULL,
                status TEXT NOT NULL,
                activated_at TIMESTAMPTZ NOT NULL,
                last_event_id UUID NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS billing.processed_events (
                event_id UUID PRIMARY KEY,
                event_name TEXT NOT NULL,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def get_connection() -> Generator[Connection, None, None]:
    with connect() as connection:
        yield connection
