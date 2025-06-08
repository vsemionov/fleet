import time
from datetime import timedelta, timezone
from pathlib import Path
from typing import Optional
import logging

from airflow.sdk import dag, task, get_current_context
from airflow.timetables.interval import CronDataIntervalTimetable
from airflow.hooks.base import BaseHook
from clickhouse_driver import Client
import numpy as np
import xarray as xr
import pandas as pd
from sklearn.cluster import DBSCAN
import pygmt
import cartopy as cp
from cartopy.geodesic import Geodesic
import matplotlib.pyplot as plt

from daglib import config


Rect = tuple[float, float, float, float]


logger = logging.getLogger('airflow.task')


@dag(
    description='Process airports',
    schedule=CronDataIntervalTimetable('0 0 * * *', timezone='UTC'),
    default_args={
        'retries': 3,
        'retry_delay': timedelta(minutes=30),
        'execution_timeout': timedelta(minutes=15),
    },
)
def process_airports():
    def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
        context = get_current_context()
        data_interval_start = context['data_interval_start'].astimezone(timezone.utc).replace(tzinfo=None)
        data_interval_end = context['data_interval_end'].astimezone(timezone.utc).replace(tzinfo=None)

        clickhouse_conn = BaseHook.get_connection(config.CLICKHOUSE_CONN_ID)

        client = Client(
            host=clickhouse_conn.host,
            port=(clickhouse_conn.port or config.CLICKHOUSE_DEFAULT_PORT),
            database=clickhouse_conn.schema,
            user=clickhouse_conn.login,
            password=clickhouse_conn.password,
            settings={'use_numpy': True},
        )

        longitude, latitude = client.execute(
            "select longitude, latitude "
            "from get_flight_endpoints(start_time=%(start_time)s, end_time=%(end_time)s) "
            "where on_ground = true ",
            {'start_time': data_interval_start, 'end_time': data_interval_end},
            columnar=True,
        )
        landings = pd.DataFrame({'longitude': longitude, 'latitude': latitude})
        landings = landings.astype({'longitude': np.float64, 'latitude': np.float64})

        longitude, latitude, altitude = client.execute(
            "select longitude, latitude, baro_altitude "
            "from get_altitude_minima(start_time=%(start_time)s, end_time=%(end_time)s) ",
            {'start_time': data_interval_start, 'end_time': data_interval_end},
            columnar=True,
        )
        minima = pd.DataFrame({'longitude': longitude, 'latitude': latitude, 'altitude': altitude})
        minima = minima.astype({'longitude': np.float64, 'latitude': np.float64, 'altitude': np.float32})

        return landings, minima


    def load_elevation() -> xr.DataArray:
        return pygmt.datasets.load_earth_relief(resolution='06m')


    def infer_airports(landings: pd.DataFrame) -> pd.DataFrame:
        projection = cp.crs.Robinson()
        geodetic = cp.crs.Geodetic()

        projected = projection.transform_points(geodetic, landings['longitude'], landings['latitude'])
        landings['x'], landings['y'] = projected.T[:2]

        dbscan = DBSCAN(eps=5_000, min_samples=5).fit(landings[['x', 'y']])
        landings['airport'] = dbscan.labels_

        landings = landings[landings['airport'] >= 0]

        airports = landings.groupby('airport').agg(
            x=('x', 'mean'),
            y=('y', 'mean'),
            landings=('airport', 'size'),
        )
        wgs84 = geodetic.transform_points(projection, airports['x'], airports['y'])
        airports['longitude'], airports['latitude'] = wgs84.T[:2]

        return landings


    def infer_goarounds(minima: pd.DataFrame, airports: pd.DataFrame, elevation: xr.DataArray) -> pd.DataFrame:
        ground_level = elevation.interp(
            lat=xr.DataArray(minima['latitude']),
            lon=xr.DataArray(minima['longitude']),
        )
        minima['agl'] = minima['altitude'] - ground_level

        minima = minima[minima['agl'] < 250]

        geodesic = Geodesic()
        endpoints = airports[['longitude', 'latitude']].to_numpy()
        dists = minima[['longitude', 'latitude']].apply(
            lambda row: geodesic.inverse(row.to_numpy(), endpoints)[:, 0],
            axis=1,
        )
        dists = np.stack(dists.to_numpy()).astype(np.float32)

        airport_idx = dists.argmin(axis=1)
        minima['airport'] = airports.index.to_numpy()[airport_idx]
        minima['airport_dist'] = dists[range(dists.shape[0]), airport_idx]

        minima = minima[minima['airport_dist'] < 10_000]

        goarounds = minima.groupby('airport').size()
        airports['goarounds'] = 0
        airports.loc[goarounds.index, 'goarounds'] = goarounds

        airports['risk'] = airports['goarounds'] / airports['landings']

        return airports


    def get_output_path(slug: str) -> Path:
        plot_group = get_current_context()['data_interval_start'].astimezone(timezone.utc).strftime('%Y-%m-%d')
        output_dir = Path(config.PLOT_OUTPUT_DIR) / 'airports' / plot_group
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f'{slug}.png'


    def plot_airports(
            airports: pd.DataFrame,
            projection: cp.crs.Projection,
            region: Optional[Rect],
            figwidth: float,
            marker_size: float,
            fontsize: float,
            title: str,
            slug: str
    ) -> None:
        output_path = get_output_path(slug)

        geodetic = cp.crs.Geodetic()
        if region is not None:
            w, e, s, n = region
            x_start, y_start = projection.transform_point(w, s, geodetic)
            x_end, y_end = projection.transform_point(e, n, geodetic)
        else:
            x_start, x_end = projection.x_limits
            y_start, y_end = projection.y_limits

        plt.style.use('default')
        plt.figure(figsize=(figwidth, figwidth * 0.4))

        try:
            ax = plt.axes(projection=projection)
            ax.add_feature(cp.feature.OCEAN)
            ax.add_feature(cp.feature.LAND)
            ax.add_feature(cp.feature.RIVERS)
            ax.add_feature(cp.feature.LAKES)
            ax.add_feature(cp.feature.COASTLINE)
            ax.add_feature(cp.feature.BORDERS, linewidth=0.5)
            ax.add_feature(cp.feature.STATES, linewidth=0.5, linestyle='dashed')

            scatter = ax.scatter(
                x=airports['longitude'],
                y=airports['latitude'],
                s=(airports['landings'] / airports['landings'].max() * 250 * marker_size),
                c=np.minimum(airports['risk'], 1),
                transform=geodetic,
                cmap='RdYlGn_r',
                edgecolor='black',
                linewidth=(0.5 * marker_size),
                zorder=2,
            )
            ax.set_xlim(x_start, x_end)
            ax.set_ylim(y_start, y_end)
            cbar = plt.colorbar(scatter)
            cbar.ax.tick_params(labelsize=(fontsize * 0.625))
            cbar.set_label('Risk', fontsize=(fontsize * 0.625))

            plt.title(title, fontsize=fontsize)
            plt.savefig(output_path, bbox_inches='tight', pad_inches=(figwidth / 100))

        finally:
            plt.close()

        logger.info(f'Saved to: {output_path}')


    @task()
    def process():
        t0 = time.time()
        landings, minima = load_data()
        logger.info(f'Loaded {len(landings)} landings and {len(minima)} minima in {time.time() - t0:.3f} s')

        t0 = time.time()
        elevation = load_elevation()
        logger.info(f'Loaded {elevation.shape[1]}x{elevation.shape[0]} elevation map in {time.time() - t0:.3f} s')

        t0 = time.time()
        airports = infer_airports(landings)
        logger.info(f'Inferred {len(airports)} airports in {time.time() - t0:.3f} s')

        t0 = time.time()
        airports = infer_goarounds(minima, airports, elevation)
        logger.info(f'Inferred {airports.goarounds.sum()} go-arounds in {time.time() - t0:.3f} s')

        logger.info('Plotting airport safety - global')
        plot_airports(
            airports,
            cp.crs.Robinson(),
            None,
            50,
            1,
            20,
            'Airport Safety - Global',
            'global'
        )

        logger.info('Plotting airport safety - Europe')
        plot_airports(
            airports,
            cp.crs.Mercator(),
            (-13, 50, 33, 72),
            50,
            2,
            14,
            'Airport Safety - Global',
            'global'
        )

        logger.info('Plotting airport safety - United States')
        plot_airports(
            airports,
            cp.crs.Mercator(),
            (-127, -65, 24, 51),
            50,
            4,
            20,
            'Airport Safety - Global',
            'global'
        )


    process()


dag_obj = process_airports()


if __name__ == '__main__':
    dag_obj.test()
