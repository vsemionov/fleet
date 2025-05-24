#!/bin/sh
set -e

clean_up () {
    ARG=$?
    rm -rf /tmp/fleet-provisioning
    exit $ARG
}
trap clean_up EXIT

cp -r /opt/fleet/provisioning /tmp/fleet-provisioning

sed -i -e "s/\\breader:XXXXXXXXXX\\b/reader:$READER_WAREHOUSE_PASSWORD/" /tmp/fleet-provisioning/all/databases/ClickHouse_Connect_Superset.yaml

cd /tmp/fleet-provisioning
for subdir in `ls`; do
    zip -r $subdir $subdir
    superset import-dashboards -u admin -p ${subdir}.zip
done
