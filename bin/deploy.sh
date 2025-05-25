#!/bin/bash
set -e

AIRCRAFT_DATA_URL="https://s3.opensky-network.org/data-samples/metadata/aircraft-database-complete-2025-02.csv"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

cd "$SCRIPT_DIR"/..

clean_up () {
    ARG=$?
    rm -rf data/aircraft_data.csv data/aircraft_data.parquet
    exit $ARG
}
trap clean_up EXIT

if ! [ -f data/aircraft.parquet ]; then
    echo "Downloading aircraft data"
    bin/get_aircraft_data.py $AIRCRAFT_DATA_URL data/aircraft_data.csv
    mv data/aircraft_data.parquet/*.parquet data/aircraft.parquet
fi

echo "Installing deployment dependencies"
docker compose exec clickhouse bash -c "dpkg -l gettext || (apt update; apt install -y gettext; ARG=\$?; rm -rf /var/lib/apt/lists/* || exit 1; exit \$ARG)"

echo "Creating database schema"
docker compose exec postgres psql -U fleet -d fleet -f /opt/fleet/db.sql

echo "Creating warehouse schema"
docker compose exec clickhouse bash -c "envsubst </opt/fleet/schema.sql | clickhouse client -d fleet"

echo "Creating Airflow connections"
docker compose exec airflow bash -c "airflow connections get postgres || airflow connections add --conn-type postgres --conn-host postgres --conn-login fleet --conn-password "\$FLEET_DATABASE_PASSWORD" --conn-schema fleet postgres"
docker compose exec airflow bash -c "airflow connections get clickhouse || airflow connections add --conn-type sqlite --conn-host clickhouse --conn-login fleet --conn-password "\$FLEET_WAREHOUSE_PASSWORD" --conn-schema fleet clickhouse"  # type sqlite as per airflow-clickhouse-plugin documentation
docker compose exec airflow bash -c "airflow connections get spark || airflow connections add --conn-type spark --conn-host spark spark"
docker compose exec airflow bash -c "airflow connections get opensky || airflow connections add --conn-type generic --conn-login "\$OPENSKY_CLIENT_ID" --conn-password "\$OPENSKY_CLIENT_SECRET" opensky"

echo "Enabling Airflow DAGs"
#docker compose exec airflow bash -c "airflow dags unpause process_states"
docker compose exec airflow bash -c "airflow dags unpause collect_states"

echo "Importing Superset dashboards"
docker compose exec superset bash /opt/fleet/provision.sh

echo "You can now delete data/aircraft.parquet (unless you plan to run this script again)"
