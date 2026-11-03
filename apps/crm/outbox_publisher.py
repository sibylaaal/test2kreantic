import json
import logging
import os
import time
from typing import Any

import psycopg
from kafka import KafkaProducer
from kafka.errors import KafkaError

from apps.crm.database import connect


logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 1


def publish_one(producer: KafkaProducer) -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT event_id, topic, event_payload
            FROM crm.outbox_events
            WHERE published_at IS NULL
            ORDER BY created_at, event_id
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        return False

    event: dict[str, Any] = row["event_payload"]
    record = producer.send(
        row["topic"],
        key=event["payload"]["subscription_id"].encode("utf-8"),
        value=event,
    )
    metadata = record.get(timeout=10)

    with connect() as connection:
        connection.execute(
            """
            UPDATE crm.outbox_events
            SET published_at = now()
            WHERE event_id = %s AND published_at IS NULL
            """,
            (row["event_id"],),
        )

    logger.info(
        "Published event_id=%s topic=%s partition=%s offset=%s",
        row["event_id"],
        metadata.topic,
        metadata.partition,
        metadata.offset,
    )
    return True


def main() -> None:
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        key_serializer=lambda key: key,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        acks="all",
    )
    logger.info("Outbox publisher connected to Kafka at %s", bootstrap_servers)
    try:
        while True:
            try:
                if not publish_one(producer):
                    time.sleep(POLL_INTERVAL_SECONDS)
            except (KafkaError, psycopg.Error):
                logger.exception("Could not publish CRM outbox event; will retry")
                time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        producer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
