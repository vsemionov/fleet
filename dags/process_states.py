from datetime import timedelta
from pathlib import Path

from airflow.sdk import dag, task
from airflow.hooks.base import BaseHook
from pyspark.sql import SparkSession

from daglib.assets import states_asset
from daglib.spark import configure_clickhouse_catalog
from daglib import config


@dag(
    description='Process states',
    schedule=states_asset,
    default_args={
        'retries': 5,
        'retry_delay': 60.0,
        'execution_timeout': timedelta(seconds=60),
    },
)
def process_states():
    @task()
    def process():
        clickhouse_conn = BaseHook.get_connection(config.CLICKHOUSE_CONN_ID)
        spark_conn = BaseHook.get_connection(config.SPARK_CONN_ID)

        with SparkSession.builder \
                .appName(Path(__file__).stem) \
                .master(f'spark://{spark_conn.host}:{spark_conn.port or config.SPARK_DEFAULT_PORT}') \
                .config('spark.jars.packages', config.SPARK_CLICKHOUSE_PACKAGES) \
                .getOrCreate() as spark:
            configure_clickhouse_catalog(spark, config.CLICKHOUSE_CONN_ID, clickhouse_conn)

            df = spark.sql(f'select count(*) from {config.CLICKHOUSE_CONN_ID}.{clickhouse_conn.schema}.clean_states')
            df.show()

    process()


dag_obj = process_states()


if __name__ == '__main__':
    dag_obj.test()
