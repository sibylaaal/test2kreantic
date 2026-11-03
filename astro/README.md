# Astro Airflow learning project

This is the Astro project for the telecom lab. It is intentionally separate from
the application `compose.yaml`: Astro CLI starts the local Airflow environment
(scheduler, webserver/API, metadata database, and supporting services) for this
project.

The `.astro/config.yaml` file marks this directory as an Astro project. Keep the
`.astro` folder in the project; the local CLI also writes runtime state there.
The metadata database uses host port `5433` because the telecom application
PostgreSQL already uses `5432`.

## Prerequisites

- Docker Engine/Desktop running and accessible to your user
- Astro CLI installed: https://www.astronomer.io/docs/astro/cli/install-cli

## Start the local Airflow environment

From this directory (or start the entire stack from the project root with
`bash scripts/start-local.sh`):

```bash
astro dev start --wait 5m
```

Open the Airflow UI at the URL printed by `astro dev start` (for example,
`http://astro.localhost:6563`; Astro can assign a different proxy port). The CLI
displays the local login credentials when it starts. Find
`telecom_daily_dwh_load` and trigger it manually to try the pipeline immediately;
it is also scheduled to run daily.

To stop the local Airflow environment:

```bash
astro dev stop
```

## First DAG lesson

The DAG in `dags/telecom_daily_dwh_load.py` reads real CRM customer and subscription
records, loads them into the DWH schema in PostgreSQL, and checks referential
integrity. It omits customer names, email addresses, and phone numbers from the
analytics model.

The Astro CLI uses `docker-compose.override.yml` to attach its scheduler and
workers to the application network, so tasks can reach `crm:8000` and `postgres:5432`.
The app Compose stack must be running first. Run `python3 scripts/smoke-test.py`
from the project root to create sample CRM data before the first load. The default
connection settings are in the DAG. If you change the app database credentials,
copy `.env.example` to `.env` in this directory and update `DWH_DATABASE_URL` to
match.

The DAG runs once per day and can also be triggered manually. Its tasks pass only
two row counts through XCom, not the underlying customer data. Kafka remains
responsible for continuous service events; this DAG handles the scheduled analytics
snapshot.

After a successful run, inspect the loaded tables from the project root:

```bash
docker compose exec postgres psql -U telecom -d telecom -c \
  'SELECT count(*) AS customers FROM dwh.dim_customer;'
docker compose exec postgres psql -U telecom -d telecom -c \
  'SELECT count(*) AS subscriptions FROM dwh.fact_subscription;'
```
