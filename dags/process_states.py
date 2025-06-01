import sys
import os
from datetime import timedelta, timezone
from pathlib import Path

from airflow.sdk import dag, task, get_current_context
from airflow.timetables.interval import CronDataIntervalTimetable
from airflow.hooks.base import BaseHook
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf
import pandas as pd
import cartopy as cp
import datashader as ds
import colorcet as cc
import matplotlib.pyplot as plt

from daglib import config


@dag(
    description='Process states',
    schedule=CronDataIntervalTimetable('0 0 * * *', timezone='UTC'),
    default_args={
        'retries': 3,
        'retry_delay': timedelta(minutes=30),
        'execution_timeout': timedelta(minutes=15),
    },
)
def process_states():
    def spark_session():
        spark_conn = BaseHook.get_connection(config.SPARK_CONN_ID)

        os.environ['PYSPARK_PYTHON'] = f'python{sys.version_info.major}.{sys.version_info.minor}'

        return SparkSession.builder \
            .appName(Path(__file__).stem) \
            .master(f'spark://{spark_conn.host}:{spark_conn.port or config.SPARK_DEFAULT_PORT}') \
            .config('spark.jars', f'{config.CLICKHOUSE_JDBC_JAR}') \
            .getOrCreate()

    def load_data(spark: SparkSession):
        context = get_current_context()
        data_interval_start = context['data_interval_start'].astimezone(timezone.utc).replace(tzinfo=None)
        data_interval_end = context['data_interval_end'].astimezone(timezone.utc).replace(tzinfo=None)

        clickhouse_conn = BaseHook.get_connection(config.CLICKHOUSE_CONN_ID)

        query = f"select time_position, longitude, latitude " \
            f"from {config.CLEAN_STATES_TABLE} " \
            f"where time_position >= '{data_interval_start.strftime('%Y-%m-%d %H:%M:%S')}' and " \
            f"   time_position < '{data_interval_end.strftime('%Y-%m-%d %H:%M:%S')}'"

        return spark.read \
            .format('jdbc') \
            .option('driver', 'com.clickhouse.jdbc.ClickHouseDriver') \
            .option('url', f'jdbc:ch://{clickhouse_conn.host}'
                f':{clickhouse_conn.port or config.CLICKHOUSE_DEFAULT_HTTP_PORT}'
                f'/{clickhouse_conn.schema}') \
            .option('user', clickhouse_conn.login) \
            .option('password', clickhouse_conn.password) \
            .option('dbtable', f'({query})') \
            .option('numPartitions', config.SPARK_NUM_PARTITIONS) \
            .option('partitionColumn', 'time_position') \
            .option('lowerBound', str(data_interval_start)) \
            .option('upperBound', str(data_interval_end)) \
            .load()

    def register_projection():
        projection = cp.crs.Robinson()
        geodetic = cp.crs.Geodetic()

        @pandas_udf('x float, y float')
        def project_coords(lon: pd.Series, lat: pd.Series) -> pd.DataFrame:
            x, y = projection.transform_points(geodetic, lon, lat).T[:2]
            return pd.DataFrame({'x': x, 'y': y})

        return project_coords

    @task()
    def process():
        with spark_session() as spark:
            project_coords = register_projection()
            df = load_data(spark)
            df = df.select(project_coords(df['longitude'], df['latitude']).alias('coords'))
            df = df.selectExpr('coords.x as x', 'coords.y as y')
            df.show(5)

    process()


dag_obj = process_states()


if __name__ == '__main__':
    dag_obj.test()
