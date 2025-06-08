import sys
import os
import time
from datetime import timedelta, timezone
from pathlib import Path
from typing import Optional, Callable
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


Rect = tuple[float, float, float, float]
Size = tuple[int, int]


logger = logging.getLogger('airflow.task')


@dag(
    description='Process traffic',
    schedule=CronDataIntervalTimetable('0 0 * * *', timezone='UTC'),
    default_args={
        'retries': 3,
        'retry_delay': timedelta(minutes=30),
        'execution_timeout': timedelta(minutes=15),
    },
)
def process_traffic():
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


    def create_projection(projection: cp.crs.Projection) -> Callable:
        geodetic = cp.crs.Geodetic()

        @F.pandas_udf('x float, y float')
        def project_coords(lon: pd.Series, lat: pd.Series) -> pd.DataFrame:
            x, y = projection.transform_points(geodetic, lon, lat).T[:2]
            return pd.DataFrame({'x': x, 'y': y})

        return project_coords


    def filter_crop(df: sql.DataFrame, window: Rect) -> sql.DataFrame:
        x_start, x_end, y_start, y_end = window
        return df.filter(
            (F.col('coords.x') >= x_start) & (F.col('coords.x') < x_end) &
            (F.col('coords.y') >= y_start) & (F.col('coords.y') < y_end)
        )


    def image_coords(df: sql.DataFrame, window: Rect, resolution: Size) -> sql.DataFrame:
        x_start, x_end, y_start, y_end = window
        w, h = resolution
        wx = w / (x_end - x_start)
        wy = h / (y_end - y_start)
        return df.select(
            # modulo wraps to zero points with exactly maximum lat/lon
            (F.floor((F.col('coords.x') - x_start) * wx) % w).alias('x'),
            (F.floor((F.col('coords.y') - y_start) * wy) % h).alias('y'),
        )


    def to_array(df: sql.DataFrame, resolution: Size) -> xr.DataArray:
        df = df.toPandas()
        yx = df[['y', 'x']].to_numpy()
        v = df['v'].to_numpy()

        agg = np.zeros(resolution[::-1], dtype=np.uint64)
        agg[yx[:, 0], yx[:, 1]] = v
        return xr.DataArray(agg)


    def get_output_path(slug: str) -> Path:
        plot_group = get_current_context()['data_interval_start'].astimezone(timezone.utc).strftime('%Y-%m-%d')
        output_dir = Path(config.PLOT_OUTPUT_DIR) / 'traffic' / plot_group
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f'{slug}.png'


    def rasterize(
            agg: xr.DataArray,
            projection: cp.crs.Projection,
            window: Rect,
            figsize: float,
            fontsize: float,
            title: str,
            output_path: Path
    ) -> None:
        img = ds.tf.shade(agg, cmap=cc.fire)
        img = img.to_pil()

        plt.style.use('dark_background')
        plt.figure(figsize=(figsize, figsize))

        try:
            ax = plt.axes(projection=projection)
            ax.coastlines(color='grey')
            ax.add_feature(cp.feature.LAND, facecolor='#202020')
            ax.add_feature(cp.feature.BORDERS, edgecolor='grey', linewidth=0.5)
            ax.imshow(img, extent=window, transform=projection, zorder=2)
            plt.title(title, fontsize=fontsize)
            plt.savefig(output_path, bbox_inches='tight', pad_inches=(figsize / 100))

        finally:
            plt.close()


    def plot_traffic(
            states: sql.DataFrame,
            projection: cp.crs.Projection,
            region: Optional[Rect],
            resolution: Size,
            figsize: float,
            fontsize: float,
            title: str,
            slug: str
    ) -> None:
        if region is not None:
            w, e, s, n = region
            geodetic = cp.crs.Geodetic()
            x_start, y_start = projection.transform_point(w, s, geodetic)
            x_end, y_end = projection.transform_point(e, n, geodetic)
        else:
            x_start, x_end = projection.x_limits
            y_start, y_end = projection.y_limits
        window = x_start, x_end, y_start, y_end

        project_coords = create_projection(projection)

        t0 = time.time()
        df = states.select(project_coords('longitude', 'latitude').alias('coords'))
        if region is not None:
            df = filter_crop(df, window)
        df = image_coords(df, window, resolution)
        df = df.select('x', 'y').groupBy('x', 'y').agg(F.count('*').alias('v'))
        agg = to_array(df, resolution)
        logger.info(f'Processing took {time.time() - t0:.3f} s')

        output_path = get_output_path(slug)
        rasterize(agg, projection, window, figsize, fontsize, title, output_path)
        logger.info(f'Saved to: {output_path}')


    @task()
    def process():
        with spark_session() as spark:
            t0 = time.time()
            states = load_data(spark)
            logger.info(f'Loaded {states.count()} records in {time.time() - t0:.3f} s')

            logger.info('Plotting traffic density - global')
            plot_traffic(
                states,
                cp.crs.Robinson(),
                None,
                (2048, 1024),
                25,
                20,
                'Traffic Density - Global',
                'global'
            )

            logger.info('Plotting traffic density - Europe')
            plot_traffic(
                states,
                cp.crs.Mercator(),
                (-18, 50, 28, 72),
                (1024, 512),
                15,
                16,
                'Traffic Density - Europe',
                'europe'
            )

            logger.info('Plotting traffic density - North America')
            plot_traffic(
                states,
                cp.crs.Mercator(),
                (-180, -50, 0, 75),
                (1024, 512),
                15,
                16,
                'Traffic Density - North America',
                'north_america'
            )

            logger.info('Plotting traffic density - United States')
            plot_traffic(
                states,
                cp.crs.Mercator(),
                (-130, -55, 15, 55),
                (1024, 512),
                15,
                12,
                'Traffic Density - United States',
                'united_states'
            )


    process()


dag_obj = process_traffic()


if __name__ == '__main__':
    dag_obj.test()
