import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


def local_port(name: str, default: int) -> int:
    if name in os.environ:
        return int(os.environ[name])

    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name:
                return int(value.strip().strip("\"'"))
    return default


CRM_URL = f"http://localhost:{local_port('CRM_PORT', 8001)}"
BILLING_URL = f"http://localhost:{local_port('BILLING_PORT', 8002)}"
INVOICING_URL = f"http://localhost:{local_port('INVOICING_PORT', 8003)}"
NOTIFICATION_URL = f"http://localhost:{local_port('NOTIFICATION_PORT', 8004)}"


def request_json(url: str, method: str = "GET", body: dict | None = None) -> object:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach {url}: {error.reason}") from error


def main() -> None:
    for name, base_url in (
        ("CRM", CRM_URL),
        ("Billing", BILLING_URL),
        ("Invoicing", INVOICING_URL),
        ("Notification", NOTIFICATION_URL),
    ):
        request_json(f"{base_url}/health")
        print(f"PASS {name} health")

    customer = request_json(
        f"{CRM_URL}/customers",
        method="POST",
        body={
            "full_name": "Kafka Smoke Test",
            "email": f"smoke-{uuid4()}@example.test",
            "phone": "+212600000001",
            "segment": "consumer",
        },
    )
    customer_id = customer["customer_id"]

    subscription = request_json(
        f"{CRM_URL}/customers/{customer_id}/subscriptions",
        method="POST",
        body={"plan_code": "SMOKE-1GB", "service_type": "mobile"},
    )
    subscription_id = subscription["subscription_id"]
    request_json(f"{CRM_URL}/subscriptions/{subscription_id}/activate", method="POST")
    print("PASS CRM customer, subscription, and activation")

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        subscriptions = request_json(f"{BILLING_URL}/subscriptions")
        if any(item["subscription_id"] == subscription_id for item in subscriptions):
            print("PASS CRM -> outbox -> Kafka -> Billing")
            return
        time.sleep(1)

    raise RuntimeError(
        "Activated subscription did not reach Billing within 30 seconds. "
        "Inspect `docker compose logs crm-outbox-publisher billing-kafka-consumer`."
    )


if __name__ == "__main__":
    main()
