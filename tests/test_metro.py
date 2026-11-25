"""Checks the distance to the nearest metro station."""

import pandas as pd
import pytest

from data_processing.add_metro_distance import build, metro_stations, nearest_station


def test_nearest_station_is_found_and_close():
    stations = pd.DataFrame({"name": ["A", "B"], "lat": [12.97, 13.10], "lon": [77.59, 77.70]})
    km, name = nearest_station(12.975, 77.59, stations)
    assert name == "A"
    assert km == pytest.approx(0.556, abs=0.01)   # 0.005 degrees of latitude is about 556 m


def test_real_stations_and_every_area_gets_a_distance():
    assert len(metro_stations()) >= 50
    table, count = build()
    assert table["dist_to_metro_km"].notna().all()
    assert (table["dist_to_metro_km"] >= 0).all()
