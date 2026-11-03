import os
from collections.abc import Generator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def connect() -> Connection:
    database_url = os.getenv("CRM_DATABASE_URL")
    if not database_url:
        raise RuntimeError("CRM_DATABASE_URL must be set before the CRM service can start")

    return psycopg.connect(database_url, row_factory=dict_row)


def initialize_database() -> None:
    with connect() as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS crm")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.customers (
                customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                segment TEXT NOT NULL CHECK (segment IN ('consumer', 'business')),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'suspended', 'closed')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS customers_status_idx ON crm.customers (status)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.subscriptions (
                subscription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                customer_id UUID NOT NULL REFERENCES crm.customers (customer_id),
                plan_code TEXT NOT NULL CHECK (plan_code ~ '^[A-Z0-9][A-Z0-9_-]{1,39}$'),
                service_type TEXT NOT NULL
                    CHECK (service_type IN ('mobile', 'fixed_broadband', 'tv')),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'active', 'suspended', 'cancelled')),
                start_date DATE NOT NULL DEFAULT CURRENT_DATE,
                activated_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS subscriptions_customer_created_idx
            ON crm.subscriptions (customer_id, created_at DESC)
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS subscriptions_status_idx ON crm.subscriptions (status)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.outbox_events (
                event_id UUID PRIMARY KEY,
                topic TEXT NOT NULL,
                event_payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                published_at TIMESTAMPTZ
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS outbox_unpublished_created_idx
            ON crm.outbox_events (created_at)
            WHERE published_at IS NULL
            """
        )


def get_connection() -> Generator[Connection, None, None]:
    with connect() as connection:
        yield connection
