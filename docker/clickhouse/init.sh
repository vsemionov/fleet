#!/bin/sh
set -e

clickhouse client <<-EOSQL
    CREATE USER fleet IDENTIFIED BY '$FLEET_WAREHOUSE_PASSWORD';
    CREATE USER reader IDENTIFIED BY '$READER_WAREHOUSE_PASSWORD';

    CREATE DATABASE fleet;

    GRANT ALL ON fleet.* TO fleet;
    GRANT SELECT ON fleet.* TO reader;
    -- required for Spark ClickHouse Connector:
    GRANT SELECT ON system.clusters to fleet;
    GRANT SELECT ON system.parts to fleet;
EOSQL
