"""Unified API gateway for the Beijing air quality project (Task 3, Group 5).

Serves CRUD and time-series endpoints for both the MySQL and MongoDB backends.
Reads MONGO_URI, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD and
MYSQL_DATABASE from a .env file or the shell environment.

Run with:
    uvicorn app:app --reload

Interactive docs at http://127.0.0.1:8000/docs
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List

import mysql.connector
from fastapi import FastAPI, HTTPException, Query, Path as FPath
from pymongo import MongoClient, ASCENDING, DESCENDING
from pydantic import BaseModel


def _load_dotenv() -> None:
    """Read a .env file from the project root and set variables into os.environ."""
    for candidate in [Path(__file__).parent / ".env", Path(".env")]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
            break


_load_dotenv()


_MONGO_URI = os.getenv("MONGO_URI", "")
if not _MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is not set. Add it to your .env file or environment."
    )

_mongo_client = MongoClient(_MONGO_URI)
_mongo_col = _mongo_client["beijing_air_quality"]["air_quality_readings"]


def _mysql_cfg() -> dict:
    """Return a fresh mysql.connector connection config dict."""
    return {
        "host":     os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port":     int(os.getenv("MYSQL_PORT", "3306")),
        "user":     os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "beijing_air_quality"),
        "autocommit": False,
    }


@contextmanager
def _mysql():
    """Context manager that opens a MySQL connection and closes it on exit."""
    conn = mysql.connector.connect(**_mysql_cfg())
    try:
        yield conn
    finally:
        conn.close()


class Pollutants(BaseModel):
    PM2_5: Optional[float] = None
    PM10:  Optional[float] = None
    SO2:   Optional[float] = None
    NO2:   Optional[float] = None
    CO:    Optional[float] = None
    O3:    Optional[float] = None


class Weather(BaseModel):
    TEMP: Optional[float] = None
    PRES: Optional[float] = None
    DEWP: Optional[float] = None
    RAIN: Optional[float] = None
    wd:   Optional[str]   = None
    WSPM: Optional[float] = None


class AirQualityRecord(BaseModel):
    station:    str
    timestamp:  str   # Format: YYYY-MM-DDTHH:MM:SS
    year:       int
    month:      int
    day:        int
    hour:       int
    pollutants: Pollutants
    weather:    Weather


app = FastAPI(
    title="Beijing Air Quality API",
    description=(
        "Full CRUD and time-series endpoints for both MySQL and MongoDB backends. "
        "SQL endpoints operate on the normalised v_hourly_air_quality view. "
        "MongoDB endpoints operate on the air_quality_readings collection."
    ),
    version="2.0.0",
)


def _sql_row_to_dict(row: dict) -> dict:
    """Convert Decimal and datetime values in a MySQL row to JSON-safe types."""
    result = {}
    for k, v in row.items():
        if hasattr(v, "__float__"):   # Decimal
            result[k] = float(v)
        elif hasattr(v, "isoformat"): # datetime / date
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": "Beijing Air Quality API is running.",
        "docs": "/docs",
        "backends": ["MySQL", "MongoDB Atlas"],
    }


# SQL endpoints

@app.post("/api/v1/sql/air-quality", status_code=201, tags=["SQL - CRUD"])
def create_sql_record(record: AirQualityRecord):
    """Insert a new hourly reading into MySQL.

    Writes to stations (if new), observations, air_quality_readings,
    and weather_readings in a single transaction.
    """
    p = record.pollutants
    w = record.weather

    with _mysql() as conn:
        cur = conn.cursor()

        # LAST_INSERT_ID(station_id) makes lastrowid valid even when the
        # station already exists
        cur.execute(
            "INSERT INTO stations (station_name, city) VALUES (%s, 'Beijing') "
            "ON DUPLICATE KEY UPDATE station_id = LAST_INSERT_ID(station_id)",
            (record.station,),
        )
        station_id = cur.lastrowid

        try:
            cur.execute(
                "INSERT INTO observations (station_id, observed_at) VALUES (%s, %s)",
                (station_id, record.timestamp),
            )
        except mysql.connector.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail=f"A record for station '{record.station}' at '{record.timestamp}' already exists.",
            )
        obs_id = cur.lastrowid

        cur.execute(
            "INSERT INTO air_quality_readings "
            "(observation_id, pm25, pm10, so2, no2, co, o3) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (obs_id, p.PM2_5, p.PM10, p.SO2, p.NO2, p.CO, p.O3),
        )

        cur.execute(
            "INSERT INTO weather_readings "
            "(observation_id, temp, pres, dewp, rain, wd, wspm) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (obs_id, w.TEMP, w.PRES, w.DEWP, w.RAIN, w.wd, w.WSPM),
        )

        conn.commit()

    return {"message": "Record created successfully.", "observation_id": obs_id}


@app.get("/api/v1/sql/air-quality/{record_id}", tags=["SQL - CRUD"])
def get_sql_record(record_id: int = FPath(..., description="observation_id from the observations table")):
    """Fetch one reading by its observation_id from the v_hourly_air_quality view."""
    with _mysql() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM v_hourly_air_quality WHERE observation_id = %s",
            (record_id,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return _sql_row_to_dict(row)


@app.put("/api/v1/sql/air-quality/{record_id}", tags=["SQL - CRUD"])
def update_sql_record(
    record: AirQualityRecord,
    record_id: int = FPath(..., description="observation_id to update"),
):
    """Update pollutant and weather readings for an existing observation."""
    p = record.pollutants
    w = record.weather

    with _mysql() as conn:
        cur = conn.cursor()

        # Confirm the observation exists
        cur.execute(
            "SELECT observation_id FROM observations WHERE observation_id = %s",
            (record_id,),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Record not found.")

        # Update pollutants
        cur.execute(
            "UPDATE air_quality_readings "
            "SET pm25=%s, pm10=%s, so2=%s, no2=%s, co=%s, o3=%s "
            "WHERE observation_id=%s",
            (p.PM2_5, p.PM10, p.SO2, p.NO2, p.CO, p.O3, record_id),
        )

        # Update weather
        cur.execute(
            "UPDATE weather_readings "
            "SET temp=%s, pres=%s, dewp=%s, rain=%s, wd=%s, wspm=%s "
            "WHERE observation_id=%s",
            (w.TEMP, w.PRES, w.DEWP, w.RAIN, w.wd, w.WSPM, record_id),
        )

        conn.commit()

    return {"message": "Record updated successfully.", "observation_id": record_id}


@app.delete("/api/v1/sql/air-quality/{record_id}", tags=["SQL - CRUD"])
def delete_sql_record(record_id: int = FPath(..., description="observation_id to delete")):
    """Delete an observation from MySQL.

    The ON DELETE CASCADE constraints on air_quality_readings and
    weather_readings remove the child rows automatically.
    """
    with _mysql() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM observations WHERE observation_id = %s", (record_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Record not found.")
        conn.commit()

    return {"message": "Record deleted successfully.", "observation_id": record_id}


@app.get("/api/v1/sql/time-series/latest", tags=["SQL - Time-Series"])
def get_sql_latest():
    """Return the most recent observation across all stations."""
    with _mysql() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM v_hourly_air_quality "
            "ORDER BY observed_at DESC LIMIT 1"
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="No records found.")
    return _sql_row_to_dict(row)


@app.get("/api/v1/sql/time-series/range", tags=["SQL - Time-Series"])
def get_sql_range(
    station: Optional[str] = Query(None, description="Filter by station name (optional)"),
    start_date: str = Query(..., example="2015-01-01T00:00:00", description="ISO datetime, range start"),
    end_date:   str = Query(..., example="2015-01-03T23:00:00", description="ISO datetime, range end"),
):
    """Return all observations within a datetime range.

    Optionally filter to a single station with the `station` parameter.
    """
    with _mysql() as conn:
        cur = conn.cursor(dictionary=True)

        if station:
            cur.execute(
                "SELECT * FROM v_hourly_air_quality "
                "WHERE station_name = %s AND observed_at BETWEEN %s AND %s "
                "ORDER BY observed_at ASC",
                (station, start_date, end_date),
            )
        else:
            cur.execute(
                "SELECT * FROM v_hourly_air_quality "
                "WHERE observed_at BETWEEN %s AND %s "
                "ORDER BY observed_at ASC",
                (start_date, end_date),
            )

        rows = cur.fetchall()

    return [_sql_row_to_dict(r) for r in rows]


# MongoDB endpoints

def _get_season(month: int) -> str:
    if month in (12, 1, 2):  return "Winter"
    elif month in (3, 4, 5): return "Spring"
    elif month in (6, 7, 8): return "Summer"
    else:                    return "Autumn"


@app.post("/api/v1/mongo/air-quality", status_code=201, tags=["MongoDB - CRUD"])
def create_mongo_record(record: AirQualityRecord):
    """Insert a new document into the air_quality_readings collection.

    The deterministic _id pattern station_timestamp prevents duplicates.
    """
    ts = record.timestamp.replace(" ", "T")
    doc_id = f"{record.station}_{ts}"

    if _mongo_col.find_one({"_id": doc_id}):
        raise HTTPException(
            status_code=409,
            detail=f"Document '{doc_id}' already exists.",
        )

    doc = {
        "_id":       doc_id,
        "station":   record.station,
        "timestamp": ts,
        "year":      record.year,
        "month":     record.month,
        "day":       record.day,
        "hour":      record.hour,
        "season":    _get_season(record.month),
        "pollutants": record.pollutants.model_dump(by_alias=True),
        "weather":    record.weather.model_dump(by_alias=True),
    }
    _mongo_col.insert_one(doc)
    return {"message": "Document created successfully.", "_id": doc_id}


@app.get("/api/v1/mongo/air-quality/{record_id}", tags=["MongoDB - CRUD"])
def get_mongo_record(
    record_id: str = FPath(
        ..., example="Aotizhongxin_2013-03-01T00:00:00",
        description="Deterministic _id: station_YYYY-MM-DDTHH:MM:SS"
    )
):
    """Fetch one document by its _id."""
    doc = _mongo_col.find_one({"_id": record_id}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@app.put("/api/v1/mongo/air-quality/{record_id}", tags=["MongoDB - CRUD"])
def update_mongo_record(
    record: AirQualityRecord,
    record_id: str = FPath(
        ..., example="Aotizhongxin_2013-03-01T00:00:00",
        description="_id of the document to update"
    ),
):
    """Replace the pollutant and weather sub-documents of an existing record."""
    result = _mongo_col.update_one(
        {"_id": record_id},
        {"$set": {
            "pollutants": record.pollutants.model_dump(by_alias=True),
            "weather":    record.weather.model_dump(by_alias=True),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document updated successfully.", "_id": record_id}


@app.delete("/api/v1/mongo/air-quality/{record_id}", tags=["MongoDB - CRUD"])
def delete_mongo_record(
    record_id: str = FPath(
        ..., example="Aotizhongxin_2013-03-01T00:00:00",
        description="_id of the document to delete"
    )
):
    """Delete a document from the collection by its _id."""
    result = _mongo_col.delete_one({"_id": record_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document deleted successfully.", "_id": record_id}


@app.get("/api/v1/mongo/time-series/latest", tags=["MongoDB - Time-Series"])
def get_mongo_latest():
    """Return the most recent document in the collection."""
    doc = _mongo_col.find_one({}, sort=[("timestamp", DESCENDING)], projection={"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail="No documents found.")
    return doc


@app.get("/api/v1/mongo/time-series/range", tags=["MongoDB - Time-Series"])
def get_mongo_range(
    station:    Optional[str] = Query(None, description="Filter by station name (optional)"),
    start_date: str = Query(..., example="2015-01-01T00:00:00", description="ISO datetime, range start"),
    end_date:   str = Query(..., example="2015-01-03T23:00:00", description="ISO datetime, range end"),
):
    """Return all documents within a timestamp range.

    Optionally filter to a single station. Uses the compound index
    (station, timestamp) when a station is provided, idx_timestamp otherwise.
    """
    query: dict = {"timestamp": {"$gte": start_date, "$lte": end_date}}
    if station:
        query["station"] = station

    docs = list(
        _mongo_col.find(query, {"_id": 0}, sort=[("timestamp", ASCENDING)])
    )
    return docs
