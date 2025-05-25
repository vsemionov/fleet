import time
from datetime import datetime, timedelta
from typing import Optional
import logging

from airflow.sdk import dag, task
from airflow.timetables.trigger import DeltaTriggerTimetable
from airflow.hooks.base import BaseHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook
import httpx
from retryhttp import retry

from daglib.auth import refresh_opensky_auth_token
from daglib.assets import states_asset
from daglib.models import State
from daglib import config


logger = logging.getLogger('airflow.task')


@dag(
    description='Ingest aircraft states',
    schedule=DeltaTriggerTimetable(timedelta(seconds=90)),
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args={
        'retries': 0,  # no retries to avoid exhausting API quota
        'retry_delay': 60.0,
        'execution_timeout': timedelta(seconds=60),
    },
)
def collect_states():
    """Ingests aircraft states from OpenSky REST API to ClickHouse.

    Requires: Postgres connection, ClickHouse connection, OpenSky connection

    Produces: assets
    """

    @retry
    def retrieve(auth_token: Optional[tuple[str, str]], timestamp: Optional[float]) -> tuple[float, dict]:
        headers = {}
        params = config.OPENSKY_STATES_PARAMS.copy()
        if auth_token is not None:
            token_type, access_token = auth_token
            headers['Authorization'] = f'{token_type} {access_token}'
        if timestamp is not None:
            params['time'] = int(timestamp)
        request_time = time.time()
        r = httpx.get(config.OPENSKY_STATES_URL, params=params, headers=headers, timeout=config.OPENSKY_TIMEOUT)
        logger.info(f'API response took {r.elapsed.total_seconds():.3f} s')
        r.raise_for_status()
        data = r.json()
        logger.info(f'Retrieved {len(data['states'])} records for time {data['time']}')
        return request_time, data

    def validate(timestamp: Optional[float], request_time: float, data: dict):
        if not len(data['states']) > 0:
            raise ValueError('No states returned')
        remote_time = data['time']
        local_time = timestamp if timestamp is not None else request_time
        tol = config.OPENSKY_MAX_TIME_DIFF
        extra_tol = 0 if timestamp is not None else config.OPENSKY_TIMEOUT
        if not local_time - tol < remote_time < local_time + tol + extra_tol:
            raise ValueError(f'Time mismatch ({remote_time} vs {local_time:.3f})')

    def convert(data: dict) -> tuple[int, list]:
        timestamp = data['time']
        fields = list(State.model_fields.keys())
        assert fields[0] == 'time'
        fields = fields[1:]
        states = [dict(zip(fields, state[:len(fields)])) for state in data['states']]
        states = [State(time=timestamp, **state) for state in states]
        return timestamp, states

    def adapt(states: list[State]):
        for state in states:
            state.callsign = state.callsign.strip()
            if state.sensors is None:
                state.sensors = []
            if state.squawk == '':
                state.squawk = None

    @task(outlets=[states_asset])
    def collect(**context):
        postgres_hook = PostgresHook(postgres_conn_id=config.POSTGRES_CONN_ID)
        opensky_conn = BaseHook.get_connection(config.OPENSKY_CONN_ID)
        auth_token = refresh_opensky_auth_token(postgres_hook, opensky_conn, config.OPENSKY_MIN_AUTH_TTL)
        timestamp = context['logical_date'].timestamp()
        request_time, data = retrieve(auth_token, timestamp)
        validate(timestamp, request_time, data)
        timestamp, states = convert(data)
        adapt(states)
        states = [list(state.model_dump().values()) for state in states]
        clickhouse_hook = ClickHouseHook(clickhouse_conn_id=config.CLICKHOUSE_CONN_ID)
        start_time = time.time()
        clickhouse_hook.execute(f'insert into {config.STATES_TABLE} values', states)
        logger.info(f'Insert took {time.time() - start_time:.3f} s')
        return timestamp

    collect()


dag_obj = collect_states()


if __name__ == '__main__':
    dag_obj.test()
