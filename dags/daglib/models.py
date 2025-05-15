from typing import Optional

from pydantic import BaseModel, ConfigDict


# Perform only basic type checking and no conversion (e.g. timestamp to datetime),
# because the warehouse performs validation at insert time.
class State(BaseModel):
    model_config = ConfigDict(strict=True)

    time: int
    icao24: str
    callsign: Optional[str]
    origin_country: str
    time_position: Optional[int]
    last_contact: int
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude: Optional[float]
    on_ground: bool
    velocity: Optional[float]
    true_track: Optional[float]
    vertical_rate: Optional[float]
    sensors: Optional[list[int]]
    geo_altitude: Optional[float]
    squawk: Optional[str]
    spi: bool
    position_source: int
    category: int
