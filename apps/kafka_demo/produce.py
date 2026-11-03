import json
import os

from kafka import KafkaProducer

from apps.shared.events import DomainEvent


TOPIC = "telecom.crm.events.v1"


def main() -> None:
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        key_serializer=lambda key: key.encode("utf-8"),
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        acks="all",
    )
    event = DomainEvent.create(
        event_name="customer.created",
        source="crm-service",
        payload={
            "customer_id": "learning-demo-customer-001",
            "segment": "consumer",
        },
        correlation_id="learning-demo-customer-001",
    )

    try:
        metadata = producer.send(
            TOPIC,
            key=event.payload["customer_id"],
            value=event.to_dict(),
        ).get(timeout=10)
        print(
            f"Published {event.event_name} to {metadata.topic}, "
            f"partition={metadata.partition}, offset={metadata.offset}"
        )
    finally:
        producer.close()


if __name__ == "__main__":
    main()
