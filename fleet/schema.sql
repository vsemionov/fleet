create table if not exists states
(
    time DateTime,
    icao24 FixedString(6),
    callsign String,
    origin_country LowCardinality(String),
    time_position Nullable(DateTime),
    last_contact DateTime,
    longitude Nullable(Float64),
    latitude Nullable(Float64),
    baro_altitude Nullable(Float64),
    on_ground Bool,
    velocity Nullable(Float64),
    true_track Nullable(Float64),
    vertical_rate Nullable(Float64),
    sensors Array(UInt32),
    geo_altitude Nullable(Float64),
    squawk Nullable(FixedString(4)),
    spi Bool,
    position_source Enum8('ADS-B' = 0, 'ASTERIX' = 1, 'MLAT' = 2, 'FLARM' = 3),
    category Enum8(
        'No information at all' = 0,
        'No ADS-B Emitter Category Information' = 1,
        'Light (< 15500 lbs)' = 2,
        'Small (15500 to 75000 lbs)' = 3,
        'Large (75000 to 300000 lbs)' = 4,
        'High Vortex Large (aircraft such as B-757)' = 5,
        'Heavy (> 300000 lbs)' = 6,
        'High Performance (> 5g acceleration and 400 kts)' = 7,
        'Rotorcraft' = 8,
        'Glider / sailplane' = 9,
        'Lighter-than-air' = 10,
        'Parachutist / Skydiver' = 11,
        'Ultralight / hang-glider / paraglider' = 12,
        'Reserved' = 13,
        'Unmanned Aerial Vehicle' = 14,
        'Space / Trans-atmospheric vehicle' = 15,
        'Surface Vehicle – Emergency Vehicle' = 16,
        'Surface Vehicle – Service Vehicle' = 17,
        'Point Obstacle (includes tethered balloons)' = 18,
        'Cluster Obstacle' = 19,
        'Line Obstacle' = 20
    ),

    constraint check_time check coalesce(time >= time_position, true) and time >= last_contact,
    constraint check_icao24 check match(icao24, '^[0-9a-f]+$'),
    -- constraint check_origin_country check notEmpty(origin_country),  -- occurs occasionally
    constraint check_time_position_last_contact check coalesce(time_position <= last_contact, true),
    constraint check_longitude check coalesce(-180 <= longitude <= 180, true),
    constraint check_latitude check coalesce(-90 <= latitude <= 90, true),
    constraint check_velocity check coalesce(velocity >= 0, true),
    constraint check_true_track check coalesce(0 <= true_track <= 360, true),
    constraint check_squawk check coalesce(match(squawk, '^[0-9]+$'), true)
)
engine = ReplacingMergeTree(last_contact)
primary key time
order by (time, icao24);


create table if not exists clean_states
(
    time DateTime,
    icao24 FixedString(6),
    callsign String,
    origin_country LowCardinality(String),
    time_position DateTime,
    last_contact DateTime,
    longitude Float64,
    latitude Float64,
    baro_altitude Nullable(Float32),
    on_ground Bool,
    velocity Nullable(Float32),
    true_track Nullable(Float32),
    vertical_rate Nullable(Float32),
    sensors Array(UInt32),
    geo_altitude Nullable(Float32),
    squawk Nullable(FixedString(4)),
    spi Bool,
    position_source Enum8('ADS-B' = 0, 'ASTERIX' = 1, 'MLAT' = 2, 'FLARM' = 3),
    category Enum8(
        'No information at all' = 0,
        'No ADS-B Emitter Category Information' = 1,
        'Light (< 15500 lbs)' = 2,
        'Small (15500 to 75000 lbs)' = 3,
        'Large (75000 to 300000 lbs)' = 4,
        'High Vortex Large (aircraft such as B-757)' = 5,
        'Heavy (> 300000 lbs)' = 6,
        'High Performance (> 5g acceleration and 400 kts)' = 7,
        'Rotorcraft' = 8,
        'Glider / sailplane' = 9,
        'Lighter-than-air' = 10,
        'Parachutist / Skydiver' = 11,
        'Ultralight / hang-glider / paraglider' = 12,
        'Reserved' = 13,
        'Unmanned Aerial Vehicle' = 14,
        'Space / Trans-atmospheric vehicle' = 15,
        'Surface Vehicle – Emergency Vehicle' = 16,
        'Surface Vehicle – Service Vehicle' = 17,
        'Point Obstacle (includes tethered balloons)' = 18,
        'Cluster Obstacle' = 19,
        'Line Obstacle' = 20
    ),

    constraint check_time check time >= time_position and time >= last_contact,
    constraint check_icao24 check match(icao24, '^[0-9a-f]+$'),
    -- constraint check_origin_country check notEmpty(origin_country),  -- occurs occasionally
    constraint check_time_position check time_position > time - 300,
    constraint check_last_contact check last_contact > time - 300,
    constraint check_time_position_last_contact check time_position <= last_contact,
    constraint check_longitude check coalesce(-180 <= longitude <= 180, true),
    constraint check_latitude check coalesce(-90 <= latitude <= 90, true),
    constraint check_velocity check coalesce(velocity >= 0, true),
    constraint check_true_track check coalesce(0 <= true_track <= 360, true),
    constraint check_squawk check coalesce(match(squawk, '^[0-9]+$'), true)
)
engine = ReplacingMergeTree(last_contact)
primary key time_position
order by (time_position, icao24);


create materialized view if not exists clean_states_mv to clean_states as
select *
from states
where time_position is not null and
      longitude is not null and
      latitude is not null and
      time_position > time - 300 and
      last_contact > time - 300;


create or replace view flight_endpoints as
select * from (
    select *,
           lagInFrame(time_position::Nullable(DateTime)) over lag_window as prev_time_position,
           lagInFrame(on_ground::Nullable(Bool)) over lag_window as prev_on_ground,
           lagInFrame(longitude::Nullable(Float64)) over lag_window as prev_longitude,
           lagInFrame(latitude::Nullable(Float64)) over lag_window as prev_latitude,
           lagInFrame(baro_altitude::Nullable(Float32)) over lag_window as prev_baro_altitude,
           lagInFrame(geo_altitude::Nullable(Float32)) over lag_window as prev_geo_altitude,
           leadInFrame(time_position::Nullable(DateTime)) over lead_window as next_time_position
    from clean_states
    window lag_window as (partition by icao24 order by time_position),
           lead_window as (partition by icao24 order by time_position rows between unbounded preceding and unbounded following)
)
where on_ground != prev_on_ground or
      on_ground = false and next_time_position is null;  -- the last airborne state of incomplete flights is a moving endpoint


create or replace view clean_flights as
select *,
       leadInFrame(time_position::Nullable(DateTime)) over lead_window as end_time_position,
       leadInFrame(on_ground::Nullable(Bool)) over lead_window as end_on_ground,
       leadInFrame(longitude::Nullable(Float64)) over lead_window as end_longitude,
       leadInFrame(latitude::Nullable(Float64)) over lead_window as end_latitude,
       leadInFrame(baro_altitude::Nullable(Float32)) over lead_window as end_baro_altitude,
       leadInFrame(geo_altitude::Nullable(Float32)) over lead_window as end_geo_altitude,
       end_time_position - time_position as duration,  -- first time in air to first time on ground (or last in air)
       geoDistance(prev_longitude, prev_latitude, end_longitude, end_latitude) as distance  -- last time on ground to first time on ground (or last in air)
from flight_endpoints
where on_ground = false and  -- to filter flights having a 2nd endpoint: end_time_position is not null; for complete flights: end_on_ground = true
      prev_on_ground = true and  -- filter out last airborne states of incomplete flights
      time_position - prev_time_position < 1800
window lead_window as (partition by icao24 order by time_position rows between unbounded preceding and unbounded following);


create or replace table aircraft
(
    icao24 String,
    timestamp Nullable(DateTime),
    acars UInt8,
    adsb String,
    built Nullable(Date),
    categoryDescription String,
    country String,
    engines String,
    firstFlightDate Nullable(Date),
    firstSeen Nullable(Date),
    icaoAircraftClass String,
    lineNumber String,
    manufacturerIcao String,
    manufacturerName String,
    model String,
    modes String,
    nextReg Nullable(Date),
    notes String,
    operator String,
    operatorCallsign String,
    operatorIata String,
    operatorIcao String,
    owner String,
    prevReg Nullable(Date),
    regUntil Nullable(Date),
    registered Nullable(Date),
    registration String,
    selCal String,
    serialNumber String,
    status String,
    typecode String,
    vdl UInt8
)
engine = ReplacingMergeTree
primary key icao24
order by icao24;

insert into aircraft
select * from file('/var/lib/clickhouse/user_files/aircraft.parquet', 'Parquet');

create or replace dictionary aircraft_dict
(
    icao24 String,
    timestamp Nullable(DateTime),
    acars UInt8,
    adsb String,
    built Nullable(Date),
    categoryDescription String,
    country String,
    engines String,
    firstFlightDate Nullable(Date),
    firstSeen Nullable(Date),
    icaoAircraftClass String,
    lineNumber String,
    manufacturerIcao String,
    manufacturerName String,
    model String,
    modes String,
    nextReg Nullable(Date),
    notes String,
    operator String,
    operatorCallsign String,
    operatorIata String,
    operatorIcao String,
    owner String,
    prevReg Nullable(Date),
    regUntil Nullable(Date),
    registered Nullable(Date),
    registration String,
    selCal String,
    serialNumber String,
    status String,
    typecode String,
    vdl UInt8
)
primary key icao24
source(clickhouse(table 'aircraft' password '$CLICKHOUSE_PASSWORD'))
layout(complex_key_hashed_array())
lifetime(0);

select count(*) from aircraft_dict format null;  -- trigger population of the dictionary


create or replace view clean_states_aircraft as
select *,
       dictGet('aircraft_dict', 'engines', icao24) as engines,
       dictGet('aircraft_dict', 'manufacturerName', icao24) as manufacturerName,
       dictGet('aircraft_dict', 'model', icao24) as model,
       dictGet('aircraft_dict', 'owner', icao24) as owner,
       dictGet('aircraft_dict', 'registration', icao24) as registration
from clean_states;


create or replace view clean_flights_aircraft as
select *,
       dictGet('aircraft_dict', 'engines', icao24) as engines,
       dictGet('aircraft_dict', 'manufacturerName', icao24) as manufacturerName,
       dictGet('aircraft_dict', 'model', icao24) as model,
       dictGet('aircraft_dict', 'owner', icao24) as owner,
       dictGet('aircraft_dict', 'registration', icao24) as registration
from clean_flights;
