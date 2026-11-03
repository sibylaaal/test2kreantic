import json
import os

from kafka import KafkaConsumer


TOPIC = "telecom.crm.events.v1"


def main() -> None:
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id="telecom-notification-demo",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )

    print(f"Listening to {TOPIC} as group telecom-notification-demo; press Ctrl+C to stop.")
    try:
        for record in consumer:
            event = record.value
            print(
                f"Handled {event['event_name']} "
                f"event_id={event['event_id']} "
                f"key={record.key.decode('utf-8') if record.key else None} "
                f"partition={record.partition} offset={record.offset}"
            )
            consumer.commit()
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
