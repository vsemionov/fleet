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

echo "Creating warehouse schema"
docker compose exec clickhouse bash -c "envsubst </opt/fleet/schema.sql | clickhouse-client -d fleet"

echo "Creating Airflow connections"
docker compose exec airflow bash -c "airflow connections get postgres || airflow connections add --conn-type postgres --conn-host postgres --conn-login fleet --conn-password "\$FLEET_DATABASE_PASSWORD" --conn-schema fleet postgres"
docker compose exec airflow bash -c "airflow connections get clickhouse || airflow connections add --conn-type sqlite --conn-host clickhouse --conn-login fleet --conn-password "\$FLEET_WAREHOUSE_PASSWORD" --conn-schema fleet clickhouse"  # type sqlite as per airflow-clickhouse-plugin documentation
docker compose exec airflow bash -c "airflow connections get spark || airflow connections add --conn-type spark --conn-host spark spark"

echo "Enabling Airflow DAGs"
docker compose exec airflow bash -c "airflow dags unpause process_states"
docker compose exec airflow bash -c "airflow dags unpause collect_states"

echo "Adding Grafana datasources"
docker compose exec -T grafana bash <<EOL
curl -f -sS -u "\$GF_ADMIN_USER:\$GF_ADMIN_PASSWORD" "http://localhost:3000/api/datasources/name/postgres" >/dev/null || curl -f -sS -X POST -u "\$GF_ADMIN_USER:\$GF_ADMIN_PASSWORD" -H "Content-Type: application/json" --data '{"id":1,"uid":"dem4xij9821hcc","orgId":1,"name":"postgres","type":"grafana-postgresql-datasource","typeName":"PostgreSQL","typeLogoUrl":"public/app/plugins/datasource/grafana-postgresql-datasource/img/postgresql_logo.svg","access":"proxy","url":"postgres","user":"reader","secureJsonData":{"password":"'"\$READER_DATABASE_PASSWORD"'"},"database":"","basicAuth":false,"isDefault":false,"jsonData":{"connMaxLifetime":14400,"database":"fleet","maxIdleConns":20,"maxIdleConnsAuto":true,"maxOpenConns":20,"postgresVersion":1500,"sslmode":"disable"},"readOnly":false}' "http://localhost:3000/api/datasources" >/dev/null
EOL
docker compose exec -T grafana bash <<EOL
curl -f -sS -u "\$GF_ADMIN_USER:\$GF_ADMIN_PASSWORD" "http://localhost:3000/api/datasources/name/clickhouse" >/dev/null || curl -f -sS -X POST -u "\$GF_ADMIN_USER:\$GF_ADMIN_PASSWORD" -H "Content-Type: application/json" --data '{"id":2,"uid":"dem4xxg0tkao0a","orgId":1,"name":"clickhouse","type":"grafana-clickhouse-datasource","typeName":"ClickHouse","typeLogoUrl":"public/plugins/grafana-clickhouse-datasource/img/logo.svg","access":"proxy","url":"","user":"","database":"","basicAuth":false,"isDefault":true,"jsonData":{"defaultDatabase":"fleet","host":"clickhouse","logs":{"contextColumns":[],"defaultTable":"otel_logs","otelVersion":"latest","selectContextColumns":true},"port":9000,"protocol":"native","traces":{"defaultTable":"otel_traces","durationUnit":"nanoseconds","otelVersion":"latest"},"username":"reader","version":"4.8.2"},"secureJsonData":{"password":"'"\$READER_DATABASE_PASSWORD"'"},"readOnly":false}' "http://localhost:3000/api/datasources" >/dev/null
EOL

echo "You can now delete data/aircraft.parquet (unless you plan to run this script again)"
