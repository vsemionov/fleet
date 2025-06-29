# Fleet

Fleet is an air traffic analysis system.

![airport safety europe](https://github.com/user-attachments/assets/c96b7004-cbfb-4928-9e4a-82e278a98877)

![traffic density europe](https://github.com/user-attachments/assets/7e92ab66-40bb-48aa-a06d-a9c59c4fdea9)

Click the above images to view full scale maps.

Fleet uses data from OpenSky Network, consisting of the states of individual aircraft at different points in time.
Aircraft are uniquely identified by their ICAO codes (six hexadecimal character strings).
Their states consist of position (as WGS 84 latitude and longitude), altitude, velocity, and whether they are on the ground.
The states of all currently active aircraft are pulled every 90 seconds.

Fleet analyses the data by partitioning it into individual ICAO codes, and ordering the resulting states by time.
This makes it possible, without additional sources of information, and with decent accuracy, to infer flights and airports around the world.


## Analyses
### Airport safety
![global](https://github.com/user-attachments/assets/715ad3b6-e068-46ab-aeb2-92f0cdebb42b)
![united states](https://github.com/user-attachments/assets/8e3dff3c-2dfb-44a7-a050-748e185571e7)

Goal - compute a risk factor for every airport.
The risk factor is defined as the ratio of the number of go-around maneuvers near an airport, to the number of landings on the airport.
A go-around maneuver is performed when a landing is not going by plan, and therefore indicates difficulty.
High ratios of go-arounds to landings indicate (in my understanding) frequent problems during landing approaches.

Airport locations are inferred from clusters of landing points.
Go-arounds are inferred from descents followed by climbs without landing, close to an airport and close to ground level.
More formally:
> Airport locations are inferred by computing clusters of positions,
> where an aircraft's status changes from airborne to on-ground, and averaging the coordinates of each cluster's member points.
> The DBSCAN algorithm is used, because the number of clusters (airports) is not known in advance.
> It is performed in Robinson projection,
> as a compromise to maintain similar scale globally and use Euclidian distance in a single pass.
> The clustering parameters are neighborhood radius = 5 km, and minimum number of points = 5.
> Go-arounds are inferred as local minima of aircraft altitudes,
> where the altitude above ground level and the distance to the nearest airport are below given limits.
> Altitudes above ground level are computed as the difference between barometric altitude
> and the interpolated Earth elevation from the SRTM15+V2.7 dataset.
> The parameters for go-around detection are altitude < 500 m AGL, and distance to nearest airport < 5 km.
> The elevation data has 6 arc minute resolution, and is interpolated linearly for speed.
> Risk factors are clamped above to 1, for visualization purposes.

#### Observations
Most major airports have very low risk factors, as expected.
However, in Europe, London Heathrow airport is a notable exception with relatively high risk.
This is an unexpected result, but the analysis whether this is the case in reality,
or is just an artifact of how I define and compute risk, is deferred for future work.

The results for the United States are similar.
The largest airports seem very safe, but there are a few mid-size airports with significant risk factors,
especially in the West part of the country.

High risk factors are typical for small airports.
On one hand, this could be due to lack of modern automation for precision landings, like ILS.
But, it could also be just because the typical flights in these areas follow less strict plans (if any).
Think Cessnas, not Boeings and Airbuses.
Perhaps, the criteria to consider an altitude minimum to be a go-around (altitude AGL and distance to airport)
should depend on the size of the airport.

### Traffic density
![global](https://github.com/user-attachments/assets/f70a4e80-6f10-40fa-b220-4c982c1dc14c)
![united states](https://github.com/user-attachments/assets/3770af53-62da-4769-a4c5-1dedb4374562)

Unfortunately, traffic above the oceans cannot be seen here.
The data is collected by a network of volunteers, using ADS-B receivers, which (to my knowledge) have a typical range of 250 km.
Hence the gaps over water, and the incomplete country coverage.

All plots above were generated with data from Jun 10, 2025.

### Other visualizations
The below charts are implemented as a Superset dashboard.

![Screenshot 2025-06-12 at 09-55-18 Main](https://github.com/user-attachments/assets/65e66020-b3a6-4090-991d-981ab9f7df57)
![Screenshot 2025-06-12 at 09-55-30 Main](https://github.com/user-attachments/assets/62d95c03-ad23-4492-90a8-6f9ed122b92c)
![Screenshot 2025-06-12 at 09-55-40 Main](https://github.com/user-attachments/assets/4615c362-865a-4a81-89ee-9e5160b282e9)
![Screenshot 2025-06-12 at 09-55-49 Main](https://github.com/user-attachments/assets/916ddfa6-034f-4b6a-b00a-3d32ac06585c)
![Screenshot 2025-06-12 at 09-57-57 Main](https://github.com/user-attachments/assets/6b1468f7-0dff-4ddc-b9d9-6774938561a8)
![Screenshot 2025-06-12 at 10-05-18 Main](https://github.com/user-attachments/assets/aa1f13a0-5ce2-488f-b7d0-aa114f392518)
![Screenshot 2025-06-12 at 10-05-24 Main](https://github.com/user-attachments/assets/011a0fc5-6d8b-42c8-bd75-65960e386849)
![Screenshot 2025-06-12 at 10-05-35 Main](https://github.com/user-attachments/assets/79248747-fdff-4a42-aec0-9d37701a123a)
![Screenshot 2025-06-12 at 10-05-42 Main](https://github.com/user-attachments/assets/31f2180c-0a18-4e60-8868-227d3705d18b)


## Software
### Architecture
Fleet runs in a set of Docker containers:
* Apache Airflow - schedule data ingestion and processing
* ClickHouse - data storage and analytics
* Apache Spark - distributed processing of potentially large data
* Dask - parallelize some parts of the processing
* Apache Superset - expose some of the visualizations in a dashboard
* Grafana - realtime monitoring
* PostgreSQL - metadata store
* Redis - query result cache
* Jupyter - data exploration


### Installation
If you want to run Fleet, first you will need an OpenSky Network account (which is free).
Alternatively, you will need to change the data pull period from 90 seconds to 15 minutes
(corresponding to quotas for registered and anonymous users, respectively).
After creating an account, create an API credential.

You will also need a MapBox API key, to display map tiles in the Superset dashboard.
At the time of writing, this is also free under a certain usage limit, but it does require a credit card.
Alternatively, you can just skip it if you don't need map visualizations.

Then, run the following in the project repository root folder:
```shell
cp .env.blank .env && chmod 600 .env
```
Edit the `.env` file, and add your OpenSky and MapBox credentials.
Then, create a new Python virtual environment (version 3.12 is tested), activate it,
and install the necessary dependencies by running:
```shell
pip install -r requirements.txt
```
Next, build and start the Docker containers with:
```shell
docker compose up -d
```
When this finishes, monitor the output of `docker compose ps`, and when all services become healthy, run:
```shell
bin/deploy.sh
```
The last step imports necessary configurations and data.
After this finishes, you will no longer need your virtual environment, and you can delete it.

### Usage
Assuming Fleet is running on your computer, you can:
* View visualizations in the `data/plots` folder
* View the Superset dashboard at `http://localhost:8088/`
* Access Airflow at `http://localhost:8080/`

The default credentials are `admin/admin` everywhere except for Airflow (`airflow/airflow`).

However, it takes time for data to be collected to have anything to visualize.
I run Fleet on a remote server to collect data.
Ports are opened only on the loopback network interface (localhost).
To access Fleet's services, you can connect to the host server via SSH and tunnel the needed ports:
```shell
ssh -N -L 8080:localhost:8080 -L 8088:localhost:8088 user@host
```
Keep this running, and then point your browser to `http://localhost:8088/` or `http://localhost:8080/`.

To view the periodically generated visualizations on the server's filesystem (not the dashboards),
you can either copy them from the server (using `scp`), or mount them to your computer via `sshfs`.


## Acknowledgements
In addition to the data source, the services listed in *Architecture*, and the programming language (Python),
Fleet works thanks to the following awesome open source projects:
* Cartopy - map projections and beautiful plots
* Datashader - fast big data visualization
* Matplotlib - base for all charts
* NumPy - fast number crunching
* Pandas - structured data processing
* PyGMT - easy access to Earth datasets
* Seaborn - statistical visualizations (in notebooks)
* Scikit-learn - machine learning algorithms (DBSCAN)
* Xarray, SciPy - geospatial data processing (multivariate interpolation)
