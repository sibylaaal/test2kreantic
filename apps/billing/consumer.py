import json
import logging
import os
from datetime import datetime
from typing import Literal
from uuid import UUID

from kafka import KafkaConsumer
from kafka.structs import OffsetAndMetadata, TopicPartition
from psycopg import Connection

from apps.billing.database import connect, initialize_database


logger = logging.getLogger(__name__)
TOPIC = "telecom.crm.events.v1"
CONSUMER_GROUP = "billing-service"


def apply_event(
    connection: Connection,
    event: dict,
) -> Literal["applied", "duplicate", "ignored"]:
    if event.get("schema_version") != 1:
        raise ValueError(f"Unsupported event schema version: {event.get('schema_version')}")
    if event.get("event_name") != "subscription.activated":
        return "ignored"

    event_id = UUID(event["event_id"])
    payload = event["payload"]
    subscription_id = UUID(payload["subscription_id"])
    customer_id = UUID(payload["customer_id"])
    activated_at = datetime.fromisoformat(payload["activated_at"])

    inserted = connection.execute(
        """
        INSERT INTO billing.processed_events (event_id, event_name)
        VALUES (%s, %s)
        ON CONFLICT (event_id) DO NOTHING
        RETURNING event_id
        """,
        (event_id, event["event_name"]),
    ).fetchone()
    if inserted is None:
        return "duplicate"

    connection.execute(
        """
        INSERT INTO billing.subscriptions (
            subscription_id, customer_id, plan_code, service_type,
            status, activated_at, last_event_id, updated_at
        )
        VALUES (%s, %s, %s, %s, 'active', %s, %s, now())
        ON CONFLICT (subscription_id) DO UPDATE SET
            customer_id = EXCLUDED.customer_id,
            plan_code = EXCLUDED.plan_code,
            service_type = EXCLUDED.service_type,
            status = EXCLUDED.status,
            activated_at = EXCLUDED.activated_at,
            last_event_id = EXCLUDED.last_event_id,
            updated_at = now()
        """,
        (
            subscription_id,
            customer_id,
            payload["plan_code"],
            payload["service_type"],
            activated_at,
            event_id,
        ),
    )
    return "applied"


def main() -> None:
    initialize_database()
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id=CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    logger.info("Billing is listening to topic %s", TOPIC)

    try:
        for message in consumer:
            event = message.value
            with connect() as connection:
                result = apply_event(connection, event)

            consumer.commit(
                {
                    TopicPartition(message.topic, message.partition): OffsetAndMetadata(
                        message.offset + 1,
                        "",
                    )
                }
            )
            logger.info(
                "%s event_id=%s partition=%s offset=%s",
                result,
                event["event_id"],
                message.partition,
                message.offset,
            )
    finally:
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
