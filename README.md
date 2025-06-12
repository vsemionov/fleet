# Fleet

Fleet is an air traffic analysis system.
It uses data from OpenSky Network, consisting of the states of individual aircraft at different points in time.
Aircraft are uniquely identified by their ICAO codes (six hexadecimal character strings).
Their states consist of position (as WGS 84 latitude and longitude), altitude, velocity, and whether they are on the ground.
The states of all currently active aircraft are pulled every 90 seconds.

Fleet analyses the data by partitioning it into individual ICAO codes, and ordering the resulting states by time.
This makes it possible, without additional sources of information, and with decent accuracy, to infer flights and airports around the world.


## Analyses
### Airport safety
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
I am unaware if this is the case in reality, or is just an artifact of how I define and compute risk.

The results for the United States are similar.
The largest airports seem very safe, but there are a few mid-size airports with significant risk factors,
especially in the West part of the country.

High risk factors correlate with small airports.
On one hand, this could be due to lack of modern automation for precision landings, like ILS.
But, it could also be just because the typical flights in these areas follow less strict plans (if any).
Think Cessnas, not Boeings and Airbuses.
Perhaps, the criteria to consider an altitude minimum to be a go-around (altitude AGL and distance to airport)
should depend on the size of the airport.

### Traffic density
Unfortunately, traffic above the oceans cannot be seen here.
The data is collected by a network of volunteers, using ADS-B receivers, which (to my knowledge) have a typical range of 250 km.
Hence the gaps over water, and the incomplete country coverage.


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
(quotas for registered and anonymous users, respectively).
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
Next, build and start the docker containers with:
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


## Disclaimer
This is a small hobby project, based on limited publicly available data.
Please do not take my method, results, and interpretation too seriously.
I like algorithms and data, but I am not an aviation or travel expert.
If you see room for correction or improvement, please let me know, for example by opening an issue.
