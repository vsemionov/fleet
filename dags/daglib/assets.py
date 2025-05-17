from airflow.sdk import Asset

from .config import CLICKHOUSE_CONN_ID


STATES_TABLE = 'states'
states_asset = Asset(f'fleet://{CLICKHOUSE_CONN_ID}/{STATES_TABLE}')
