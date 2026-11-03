import os
import time
from datetime import datetime, timedelta
from typing import Any

import psycopg
from airflow.decorators import dag, task


PAGE_SIZE = 100
CRM_API_URL = os.getenv("CRM_API_URL", "http://crm:8000").rstrip("/")
DWH_DATABASE_URL = os.getenv(
    "DWH_DATABASE_URL",
    "postgresql://telecom:local-dev-only@postgres:5432/telecom",
)


def fetch_page(resource: str, offset: int) -> list[dict[str, Any]]:
    import json
    from urllib.error import URLError
    from urllib.request import urlopen

    url = f"{CRM_API_URL}/{resource}?limit={PAGE_SIZE}&offset={offset}"
    for attempt in range(3):
        try:
            with urlopen(url, timeout=15) as response:
                page = json.loads(response.read())
            if not isinstance(page, list):
                raise ValueError(f"CRM endpoint /{resource} did not return a list")
            return page
        except URLError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Could not fetch CRM resource: {resource}")


def fetch_all(resource: str) -> list[dict[str, Any]]:
    rows = []
    offset = 0
    while True:
        page = fetch_page(resource, offset)
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += len(page)


@dag(
    dag_id="telecom_daily_dwh_load",
    description="Load CRM customer and subscription snapshots into the DWH.",
    start_date=datetime(2025, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["telecom", "crm", "dwh", "learning"],
)
def telecom_daily_dwh_load():
    @task
    def load_crm_snapshot() -> dict[str, int]:
        customers = fetch_all("customers")
        subscriptions = fetch_all("subscriptions")

        with psycopg.connect(DWH_DATABASE_URL) as connection:
            connection.execute("CREATE SCHEMA IF NOT EXISTS dwh")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dwh.dim_customer (
                    customer_id UUID PRIMARY KEY,
                    segment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    source_updated_at TIMESTAMPTZ NOT NULL,
                    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dwh.fact_subscription (
                    subscription_id UUID PRIMARY KEY,
                    customer_id UUID NOT NULL REFERENCES dwh.dim_customer (customer_id),
                    plan_code TEXT NOT NULL,
                    service_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    activated_at TIMESTAMPTZ,
                    source_updated_at TIMESTAMPTZ NOT NULL,
                    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO dwh.dim_customer (
                    customer_id, segment, status, created_at, source_updated_at, loaded_at
                )
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (customer_id) DO UPDATE SET
                    segment = EXCLUDED.segment,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    source_updated_at = EXCLUDED.source_updated_at,
                    loaded_at = now()
                """,
                [
                    (
                        customer["customer_id"],
                        customer["segment"],
                        customer["status"],
                        datetime.fromisoformat(customer["created_at"]),
                        datetime.fromisoformat(customer["updated_at"]),
                    )
                    for customer in customers
                ],
            )
            connection.executemany(
                """
                INSERT INTO dwh.fact_subscription (
                    subscription_id, customer_id, plan_code, service_type, status,
                    start_date, activated_at, source_updated_at, loaded_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (subscription_id) DO UPDATE SET
                    customer_id = EXCLUDED.customer_id,
                    plan_code = EXCLUDED.plan_code,
                    service_type = EXCLUDED.service_type,
                    status = EXCLUDED.status,
                    start_date = EXCLUDED.start_date,
                    activated_at = EXCLUDED.activated_at,
                    source_updated_at = EXCLUDED.source_updated_at,
                    loaded_at = now()
                """,
                [
                    (
                        subscription["subscription_id"],
                        subscription["customer_id"],
                        subscription["plan_code"],
                        subscription["service_type"],
                        subscription["status"],
                        subscription["start_date"],
                        (
                            datetime.fromisoformat(subscription["activated_at"])
                            if subscription["activated_at"]
                            else None
                        ),
                        datetime.fromisoformat(subscription["updated_at"]),
                    )
                    for subscription in subscriptions
                ],
            )
            missing_customers = connection.execute(
                """
                SELECT count(*)
                FROM dwh.fact_subscription AS subscription
                LEFT JOIN dwh.dim_customer AS customer USING (customer_id)
                WHERE customer.customer_id IS NULL
                """
            ).fetchone()[0]
            if missing_customers:
                raise ValueError(
                    f"DWH quality check failed: {missing_customers} subscriptions "
                    "refer to missing customers"
                )

        return {"customers_loaded": len(customers), "subscriptions_loaded": len(subscriptions)}

    @task
    def report_load(result: dict[str, int]) -> None:
        print(
            "CRM snapshot loaded to DWH: "
            f"{result['customers_loaded']} customers, "
            f"{result['subscriptions_loaded']} subscriptions"
        )

    report_load(load_crm_snapshot())


telecom_daily_dwh_load()
