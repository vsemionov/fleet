import time
from datetime import datetime, timedelta
import logging

from airflow.sdk import dag, task, Asset
from airflow.timetables.trigger import CronTriggerTimetable
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook
import httpx
from retryhttp import retry

from daglib.models import State


CONN_ID = 'clickhouse'
STATES_TABLE = 'states'
STATES_URI = f'fleet://{CONN_ID}/{STATES_TABLE}'

API_URL = 'https://opensky-network.org/api/states/all'
API_PARAMS = {'extended': 1}
API_TIMEOUT = 30
MAX_TIME_DIFF = 300


logger = logging.getLogger('airflow.task')
states_asset = Asset(STATES_URI)


@dag(
    description='Ingest aircraft states',
    schedule=CronTriggerTimetable('*/15 * * * *', timezone='UTC'),
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args={
        'retries': 5,
        'retry_delay': 60.0,
        'execution_timeout': timedelta(seconds=60),
    },
)
def states_etl():
    """Ingests aircraft states from OpenSky REST API to ClickHouse.

    Requires: ClickHouse connection

    Produces: assets
    """

    @retry
    def retrieve() -> dict:
        r = httpx.get(API_URL, params=API_PARAMS, timeout=API_TIMEOUT)
        logger.info(f'API response took {r.elapsed.total_seconds():.3f} s')
        r.raise_for_status()
        data = r.json()
        logger.info(f'Retrieved {len(data['states'])} records for time {data['time']}')
        return data

    def validate(data: dict):
        if not len(data['states']) > 0:
            raise ValueError('No states returned')
        remote_time = data['time']
        local_time = time.time()
        if not abs(remote_time - local_time) < API_TIMEOUT + MAX_TIME_DIFF:
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
            if state.sensors is None:
                state.sensors = []
            if state.squawk == 'None':
                state.squawk = None

    @task(outlets=[states_asset])
    def etl():
        data = retrieve()
        validate(data)
        timestamp, states = convert(data)
        adapt(states)
        states = [list(state.model_dump().values()) for state in states]
        hook = ClickHouseHook(clickhouse_conn_id=CONN_ID)
        start_time = time.time()
        hook.execute(f'insert into {STATES_TABLE} values', states)
        logger.info(f'Insert took {time.time() - start_time:.3f} s')
        return timestamp

    @task(outlets=[states_asset])
    def transform_load(timestamp):
        logger.info('todo')

    etl()


dag_obj = states_etl()


if __name__ == '__main__':
    dag_obj.test()
