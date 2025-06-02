import sys
import os
import time
from datetime import timedelta, timezone
from pathlib import Path
from typing import Callable
import logging

from airflow.sdk import dag, task, get_current_context
from airflow.timetables.interval import CronDataIntervalTimetable
from airflow.hooks.base import BaseHook
from pyspark import sql
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
import numpy as np
import xarray as xr
import pandas as pd
import cartopy as cp
import datashader as ds
import colorcet as cc
import matplotlib.pyplot as plt

from daglib import config


logger = logging.getLogger('airflow.task')

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
    def spark_session() -> SparkSession:
        spark_conn = BaseHook.get_connection(config.SPARK_CONN_ID)

        os.environ['PYSPARK_PYTHON'] = f'python{sys.version_info.major}.{sys.version_info.minor}'

        return SparkSession.builder \
            .appName(Path(__file__).stem) \
            .master(f'spark://{spark_conn.host}:{spark_conn.port or config.SPARK_DEFAULT_PORT}') \
            .config('spark.jars', f'{config.CLICKHOUSE_JDBC_JAR}') \
            .getOrCreate()

    def load_data(spark: SparkSession) -> sql.DataFrame:
        context = get_current_context()
        data_interval_start = context['data_interval_start'].astimezone(timezone.utc).replace(tzinfo=None)
        data_interval_end = context['data_interval_end'].astimezone(timezone.utc).replace(tzinfo=None)

        clickhouse_conn = BaseHook.get_connection(config.CLICKHOUSE_CONN_ID)

        query = f"select time_position, longitude, latitude " \
            f"from {config.CLEAN_STATES_TABLE} " \
            f"where time_position >= '{data_interval_start.strftime('%Y-%m-%d %H:%M:%S')}' " \
            f"    and time_position < '{data_interval_end.strftime('%Y-%m-%d %H:%M:%S')}'"

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

    def create_projection() -> tuple[cp.crs.Projection, Callable]:
        projection = cp.crs.Robinson()
        geodetic = cp.crs.Geodetic()

        @F.pandas_udf('x float, y float')
        def project_coords(lon: pd.Series, lat: pd.Series) -> pd.DataFrame:
            x, y = projection.transform_points(geodetic, lon, lat).T[:2]
            return pd.DataFrame({'x': x, 'y': y})

        return projection, project_coords

    def image_coords(df: sql.DataFrame, projection: cp.crs.Projection) -> sql.DataFrame:
        w, h = config.PLOT_AGG_RESOLUTION
        x_start, x_end = projection.x_limits
        y_start, y_end = projection.y_limits
        wx = w / (x_end - x_start)
        wy = h / (y_end - y_start)
        return df.select(
            # modulo wraps to zero points with exactly maximum lat/lon
            (F.floor((F.col('coords.x') - x_start) * wx) % w).alias('x'),
            (F.floor((F.col('coords.y') - y_start) * wy) % h).alias('y'),
        )

    def to_array(df: sql.DataFrame) -> xr.DataArray:
        df = df.toPandas()
        yx = df[['y', 'x']].to_numpy()
        v = df['v'].to_numpy()

        agg = np.zeros(config.PLOT_AGG_RESOLUTION[::-1], dtype=np.uint64)
        agg[yx[:, 0], yx[:, 1]] = v
        return xr.DataArray(agg)

    def get_output_path() -> Path:
        output_dir = Path(config.PLOT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        plot_id = get_current_context()['data_interval_start'].astimezone(timezone.utc).strftime('%Y-%m-%d')
        return output_dir / f'traffic-{plot_id}.png'

    def rasterize(agg: xr.DataArray, projection: cp.crs.Projection, output_path: Path) -> None:
        img = ds.tf.shade(agg, cmap=cc.fire)
        img = img.to_pil()

        plt.style.use('dark_background')
        plt.figure(figsize=(config.PLOT_FIG_SIZE, config.PLOT_FIG_SIZE))

        try:
            ax = plt.axes(projection=projection)
            ax.coastlines(color='grey')
            ax.add_feature(cp.feature.LAND, facecolor='#202020')
            ax.add_feature(cp.feature.BORDERS, edgecolor='grey', linewidth=0.5)
            ax.imshow(img, extent=(projection.x_limits + projection.y_limits), transform=projection, zorder=2)
            plt.title('Traffic Density', fontsize=config.PLOT_TITLE_SIZE)
            plt.savefig(output_path, bbox_inches='tight', pad_inches=config.PLOT_PAD_SIZE)

        finally:
            plt.close()


    @task()
    def process():
        with spark_session() as spark:
            projection, project_coords = create_projection()
            logger.info(f'Setup complete')

            t0 = time.time()
            df = load_data(spark)
            logger.info(f'Loaded {df.count()} records in {time.time() - t0:.3f} s')

            t0 = time.time()
            df = df.select(project_coords('longitude', 'latitude').alias('coords'))
            df = image_coords(df, projection)
            df = df.select('x', 'y').groupBy('x', 'y').agg(F.count('*').alias('v'))
            agg = to_array(df)
            logger.info(f'Processing took {time.time() - t0:.3f} s')

            output_path = get_output_path()
            rasterize(agg, projection, output_path)
            logger.info(f'Saved to: {output_path}')


    process()


dag_obj = process_states()


if __name__ == '__main__':
    dag_obj.test()
