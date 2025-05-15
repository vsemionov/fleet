#!/bin/sh
set -e

clickhouse client <<-EOSQL
    CREATE USER fleet IDENTIFIED BY '$FLEET_WAREHOUSE_PASSWORD';

    CREATE DATABASE fleet;

    GRANT ALL ON fleet.* TO fleet;
EOSQL
