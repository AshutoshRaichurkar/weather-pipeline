"""Pull hourly temperatures from Open-Meteo and load them into raw.hourly_weather."""

import os

import psycopg
import requests

CITIES = {
    "boston": (42.36, -71.06),
    "chicago": (41.88, -87.63),
    "seattle": (47.61, -122.33),
    "austin": (30.27, -97.74),
}

API_URL = "https://api.open-meteo.com/v1/forecast"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS raw.hourly_weather (
    city          TEXT        NOT NULL,
    observed_at   TIMESTAMP   NOT NULL,
    temperature_c REAL,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (city, observed_at)
)
"""

INSERT_ROW = """
INSERT INTO raw.hourly_weather (city, observed_at, temperature_c)
VALUES (%s, %s, %s)
ON CONFLICT (city, observed_at) DO UPDATE
SET temperature_c = EXCLUDED.temperature_c, loaded_at = now()
"""


def fetch_city(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m",
        "past_days": 7,
        "forecast_days": 1,
        "timezone": "UTC",
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    return list(zip(hourly["time"], hourly["temperature_2m"]))


def main():
    conninfo = (
        f"host={os.getenv('DB_HOST', 'localhost')} "
        f"port={os.getenv('DB_PORT', '5432')} "
        f"dbname={os.getenv('DB_NAME', 'postgres')} "
        f"user={os.getenv('DB_USER', 'postgres')} "
        f"password={os.getenv('DB_PASSWORD', 'postgres')}"
    )

    with psycopg.connect(conninfo) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        conn.execute(CREATE_TABLE)
        for city, (lat, lon) in CITIES.items():
            rows = fetch_city(lat, lon)
            with conn.cursor() as cur:
                cur.executemany(INSERT_ROW, [(city, ts, temp) for ts, temp in rows])
            print(f"{city}: loaded {len(rows)} rows!")
            print("Hello World")


if __name__ == "__main__":
    main()
