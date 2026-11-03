# Telecom CRM / Billing / Invoicing Platform

This project is a learning platform for telecom systems, built incrementally. The first working vertical slice is CRM customer management:

- CRM service for customers, contracts, subscriptions, and support
- Billing service for plans, usage, charges, and payment state
- Invoicing service for invoice generation and payment tracking
- Kafka for asynchronous events between services
- Postgres for operational data
- Astro is the Airflow development platform, in the separate `astro/` project
- DWH/analytics layer for future AI and ML workloads

## Services in this scaffold

- `apps/crm` — CRM API with PostgreSQL-backed customers and subscriptions
- `apps/crm/outbox_publisher.py` — publishes committed CRM outbox events to Kafka
- `apps/billing` — Billing API and idempotent Kafka event consumer
- `apps/invoicing` — Invoicing API skeleton
- `apps/notification` — Notification API skeleton
- `apps/kafka_demo` — small Kafka producer and consumer for learning topics, keys, offsets, and consumer groups
- `astro/` — Astro Airflow project and CRM-to-DWH daily load DAG
- `compose.yaml` — local infrastructure for Postgres, Kafka, CRM, and Billing

## Start the full learning environment

Install Docker Engine/Desktop and the Astro CLI first:
https://www.astronomer.io/docs/astro/cli/install-cli

Optionally copy `.env.example` to `.env` to customize local ports or the local
PostgreSQL credentials. The example password is only for local development.

From the project root, run:

```bash
bash scripts/start-local.sh
```

This builds and starts the CRM, Billing, Invoicing, and Notification APIs, PostgreSQL,
Kafka, the CRM outbox publisher, and Billing's Kafka consumer. It then starts the
separate Astro Airflow project. First startup downloads container images and can take
a few minutes.

After startup, verify the APIs and the complete CRM-to-Kafka-to-Billing flow:

```bash
python3 scripts/smoke-test.py
```

The test creates a sample customer and subscription in the local database.

To stop everything without deleting database data:

```bash
bash scripts/stop-local.sh
```

For app services only, without Astro, use `docker compose up --build -d`.

## Typical endpoints

- CRM: http://localhost:8001
- Billing: http://localhost:8002
- Invoicing: http://localhost:8003
- Notification: http://localhost:8004
- Airflow UI: use the URL printed by Astro CLI (this setup currently reports `http://astro.localhost:6563`)
- Kafka bootstrap: localhost:9092
- PostgreSQL: localhost:5432

The CRM API docs are available at http://localhost:8001/docs after startup.
The Billing API docs are available at http://localhost:8002/docs after startup.

## CRM to DWH Airflow pipeline

The `telecom_daily_dwh_load` DAG reads CRM customers and subscriptions and
upserts analytics-safe fields into PostgreSQL's `dwh` schema. It does not copy
customer names, email addresses, or phone numbers. Open the Airflow UI URL printed
by Astro CLI and trigger the DAG manually, or wait for its daily schedule. The
application Compose services must be running so Airflow can access `crm` and
`postgres` on the shared Docker network. Run `python3 scripts/smoke-test.py` first
to create a sample CRM customer and subscription for the first load.

Check the result from the project root:

```bash
docker compose exec postgres psql -U telecom -d telecom -c \
  'SELECT count(*) AS customers FROM dwh.dim_customer;'
docker compose exec postgres psql -U telecom -d telecom -c \
  'SELECT count(*) AS subscriptions FROM dwh.fact_subscription;'
```

For customized PostgreSQL credentials, set the matching `DWH_DATABASE_URL` in
`astro/.env` (copy `astro/.env.example` first).

## First learning exercise: create a CRM customer

Start only the CRM API and its PostgreSQL dependency:

```bash
docker compose up --build crm
```

In another terminal, create a customer:

```bash
curl -X POST http://localhost:8001/customers \
  -H 'Content-Type: application/json' \
  -d '{
    "full_name": "Amina Example",
    "email": "amina@example.test",
    "phone": "+212600000000",
    "segment": "consumer"
  }'
```

Then list customers with `curl http://localhost:8001/customers`, or open
`http://localhost:8001/docs` to try the endpoints interactively. PostgreSQL generates
the customer UUID and timestamps; records persist when the API container restarts.

The `crm` PostgreSQL schema belongs to the CRM service. Billing does not read or
write CRM tables; after a subscription is activated, CRM publishes a versioned event
and Billing updates its own schema.

## Default credentials

- PostgreSQL user: `telecom`
- PostgreSQL password: `local-dev-only`
- PostgreSQL DB: `telecom`

## Second learning exercise: create and activate a subscription

Create a subscription for a customer using the UUID returned by `POST /customers`:

```bash
curl -X POST http://localhost:8001/customers/<CUSTOMER_UUID>/subscriptions \
  -H 'Content-Type: application/json' \
  -d '{
    "plan_code": "MOBILE-10GB",
    "service_type": "mobile"
  }'
```

The subscription starts as `pending`: CRM has recorded the customer's request, but
the service is not yet active. Use its returned UUID to activate it:

```bash
curl -X POST http://localhost:8001/subscriptions/<SUBSCRIPTION_UUID>/activate
```

List a customer's subscriptions with
`curl http://localhost:8001/customers/<CUSTOMER_UUID>/subscriptions`.
`plan_code` identifies a commercial offer; `service_type` describes the telecom
service (mobile, fixed broadband, or TV). At this stage CRM stores the plan code,
but a future product catalog will own plan details such as price and data allowance.

## Learning sequence

1. CRM customer data model and PostgreSQL persistence
2. CRM subscriptions and telecom product concepts
3. Kafka fundamentals: broker, topic, record, key, partition, offset, and consumer group
4. Reliable CRM events through Kafka (including the transactional outbox pattern)
5. Astro/Airflow DAG for loading the CRM snapshot into the DWH
6. Independent Billing and Invoicing services with their own data stores
7. DWH ingestion, dbt transformations, and data quality
8. AI/ML use cases

This setup is for local learning, not production. The application services currently
share one PostgreSQL server but use separate schemas where implemented. Credentials
and Kafka are configured for local development only; do not expose these services to
the public internet.

## Kafka lesson 1: send and receive one event

Kafka is a durable event log. A **topic** is a named stream of records. A **producer**
writes records, and a **consumer** reads them. A record has a key and a value; Kafka
uses the key to choose a partition, which keeps records with the same key ordered
within that partition. Each record gets an **offset**, its position in that partition.
A **consumer group** shares the work and stores its read position (the committed offset).

This local setup has two Kafka addresses:

- From this computer: `localhost:9092`
- From another Compose container: `kafka:29092`

Kafka advertises different addresses because clients need an address they can resolve
from their own network. The CRM container gets the internal address from
`KAFKA_BOOTSTRAP_SERVERS`.

Start Kafka (Compose will also start its ZooKeeper dependency):

```bash
docker compose up -d --wait kafka
```

Create a versioned CRM topic explicitly:

```bash
docker compose exec kafka kafka-topics \
  --bootstrap-server kafka:29092 \
  --create --if-not-exists \
  --topic telecom.crm.events.v1 \
  --partitions 1 \
  --replication-factor 1
```

In a second terminal, start the consumer first:

```bash
docker compose run --build --rm --no-deps crm python -m apps.kafka_demo.consume
```

In a third terminal, publish the demo customer event:

```bash
docker compose run --build --rm --no-deps crm python -m apps.kafka_demo.produce
```

The producer waits for Kafka's acknowledgement and prints the topic, partition, and
offset. The consumer prints the event and commits its offset **after** handling it.
Stop the consumer with Ctrl+C. Run the producer again: the consumer group will resume
from its committed position and display the new event. For a beginner experiment,
change `group_id` in `apps/kafka_demo/consume.py` and observe that a new group starts
at the earliest retained record.

The topic name ends in `.v1` to make the event contract's major version visible.
The key is the customer ID, so all events for a customer go to the same partition
(and therefore keep their order). The demo uses one partition and one broker to keep
the behavior easy to see; it does not provide production replication or fault tolerance.

## Kafka lesson 2: CRM event to Billing

Now the learning demo is connected to the CRM subscription lifecycle:

1. CRM changes a subscription from `pending` to `active`.
2. In the **same PostgreSQL transaction**, CRM writes a `subscription.activated`
   event into `crm.outbox_events`.
3. The outbox publisher reads unpublished rows and sends them to
   `telecom.crm.events.v1`. It marks a row published only after Kafka acknowledges it.
4. The Billing consumer reads the event and writes its own copy into
   `billing.subscriptions`.
5. Billing commits its database transaction before committing its Kafka offset.

The outbox closes an important failure gap: if CRM changed its database and then
crashed before sending to Kafka, the unpublished event remains in PostgreSQL for
the publisher to retry. If the publisher sends successfully but crashes before
marking the row published, it may send the event again. That is why Billing records
`event_id` in `billing.processed_events`: it can safely recognize and skip a duplicate.
This is **at-least-once delivery with an idempotent consumer**, not a claim that Kafka
and PostgreSQL form one distributed transaction.

The shared CRM topic can contain multiple event types. Billing applies
`subscription.activated` and ignores other valid event types, such as
`customer.created`. The real publisher uses the subscription ID as the record key,
so updates for one subscription stay in the same partition.

### Try the complete flow

Build and start PostgreSQL, Kafka, the CRM and Billing APIs, plus the publisher
and consumer workers:

```bash
docker compose up --build -d postgres kafka crm billing kafka-init crm-outbox-publisher billing-kafka-consumer
```

Compose creates the topic `telecom.crm.events.v1` after Kafka is healthy. Create a
customer using the first exercise, then create a subscription using that customer's
UUID. Activate the subscription:

```bash
curl -X POST http://localhost:8001/subscriptions/<SUBSCRIPTION_UUID>/activate
```

Check `http://localhost:8002/subscriptions`. After a short delay, the activated
subscription should appear in Billing. To follow the message path in logs:

```bash
docker compose logs -f crm-outbox-publisher billing-kafka-consumer
```

If either Kafka worker fails on startup with
`ModuleNotFoundError: No module named 'kafka.vendor.six.moves'`, rebuild the
workers after updating dependencies:

```bash
docker compose up --build -d crm-outbox-publisher billing-kafka-consumer
```

The CRM outbox retains events until Kafka acknowledges them, so the workers should
publish and consume pending activation events after they restart.

CRM and Billing use separate PostgreSQL schemas and each service writes only its
own schema. They share one PostgreSQL server for this local learning setup; separate
database servers can come later. Kafka does not make the change instantaneous, so
check Billing again if the event is still being processed.

If you want to restart from scratch, remember that `docker compose down -v` deletes
the local database volumes and all learning data. Do not run it unless that data can
be discarded.

## Kafka and Airflow have different jobs

Kafka carries events continuously between independent services. Airflow (through Astro
in the intended project setup) schedules and monitors bounded workflows such as daily
warehouse loads, reconciliation, and model training. Airflow is not the message broker
and should not be used as the consumer that keeps CRM and Billing synchronized.

The actual Astro project is in `astro/`, separate from the application Compose file.
See [astro/README.md](./astro/README.md) to start it and trigger the first DAG.
