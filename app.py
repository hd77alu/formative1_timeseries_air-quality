from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Query, Path
from pydantic import BaseModel

app = FastAPI(
    title="Beijing Air Quality Unified API Gateway",
    description="Unified CRUD and Time-Series Endpoints for MySQL and MongoDB backends (Mock Mode).",
    version="1.0.0"
)

# ---------------------------------------------------------------------------
# 1. Pydantic Data Schemas (Validates Web Requests)
# ---------------------------------------------------------------------------
class Pollutants(BaseModel):
    PM2_5: Optional[float] = None
    PM10: Optional[float] = None
    SO2: Optional[float] = None
    NO2: Optional[float] = None
    CO: Optional[float] = None
    O3: Optional[float] = None

class Weather(BaseModel):
    TEMP: Optional[float] = None
    PRES: Optional[float] = None
    DEWP: Optional[float] = None
    RAIN: Optional[float] = None
    wd: Optional[str] = None
    WSPM: Optional[float] = None

class AirQualityRecord(BaseModel):
    station: str
    timestamp: str  # Format: YYYY-MM-DD HH:MM:SS
    year: int
    month: int
    day: int
    hour: int
    pollutants: Pollutants
    weather: Weather

# ---------------------------------------------------------------------------
# 2. Mock Data Stores
# ---------------------------------------------------------------------------
# Simulating SQL Rows (List of Dictionaries)
MOCK_SQL_STORE: List[dict] = [
    {
        "id": 1, "station": "Aotizhongxin", "timestamp": "2013-03-01 00:00:00",
        "year": 2013, "month": 3, "day": 1, "hour": 0,
        "pollutants": {"PM2_5": 4.0, "PM10": 4.0, "SO2": 4.0, "NO2": 7.0, "CO": 300.0, "O3": 77.0},
        "weather": {"TEMP": -0.7, "PRES": 1023.0, "DEWP": -18.8, "RAIN": 0.0, "wd": "NNW", "WSPM": 4.4}
    }
]

# Simulating MongoDB Documents (Dictionary keyed by custom _id)
MOCK_MONGO_STORE: Dict[str, dict] = {
    "Aotizhongxin_2013-03-01T00:00:00": {
        "_id": "Aotizhongxin_2013-03-01T00:00:00", "station": "Aotizhongxin", "timestamp": "2013-03-01 00:00:00",
        "year": 2013, "month": 3, "day": 1, "hour": 0, "season": "Spring",
        "pollutants": {"PM2_5": 4.0, "PM10": 4.0, "SO2": 4.0, "NO2": 7.0, "CO": 300.0, "O3": 77.0},
        "weather": {"TEMP": -0.7, "PRES": 1023.0, "DEWP": -18.8, "RAIN": 0.0, "wd": "NNW", "WSPM": 4.4}
    }
}

# ---------------------------------------------------------------------------
# 3. SQL ENDPOINTS (Mocked)
# ---------------------------------------------------------------------------
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the Beijing Air Quality API! Please visit /docs for the interactive dashboard."}
@app.post("/api/v1/sql/air-quality", status_code=201, tags=["SQL Endpoints"])
def create_sql_record(record: AirQualityRecord):
    """CREATE: Add a new record to SQL."""
    new_id = max([r["id"] for r in MOCK_SQL_STORE] + [0]) + 1
    new_doc = record.model_dump()
    new_doc["id"] = new_id
    MOCK_SQL_STORE.append(new_doc)
    return {"message": "Record added successfully", "inserted_id": new_id}

@app.get("/api/v1/sql/air-quality/{record_id}", tags=["SQL Endpoints"])
def get_sql_record(record_id: int):
    """READ: Get a specific record by its SQL ID."""
    for r in MOCK_SQL_STORE:
        if r["id"] == record_id:
            return r
    raise HTTPException(status_code=404, detail="Record not found")

@app.put("/api/v1/sql/air-quality/{record_id}", tags=["SQL Endpoints"])
def update_sql_record(record_id: int, record: AirQualityRecord):
    """UPDATE: Modify an existing SQL record."""
    for idx, r in enumerate(MOCK_SQL_STORE):
        if r["id"] == record_id:
            updated_doc = record.model_dump()
            updated_doc["id"] = record_id
            MOCK_SQL_STORE[idx] = updated_doc
            return {"message": "Record updated successfully"}
    raise HTTPException(status_code=404, detail="Record not found")

@app.delete("/api/v1/sql/air-quality/{record_id}", tags=["SQL Endpoints"])
def delete_sql_record(record_id: int):
    """DELETE: Remove a SQL record."""
    for idx, r in enumerate(MOCK_SQL_STORE):
        if r["id"] == record_id:
            del MOCK_SQL_STORE[idx]
            return {"message": "Record deleted successfully"}
    raise HTTPException(status_code=404, detail="Record not found")

@app.get("/api/v1/sql/time-series/latest", tags=["SQL Time-Series"])
def get_sql_latest():
    """TIME-SERIES: Fetch the most recent timestamp."""
    if not MOCK_SQL_STORE:
        raise HTTPException(status_code=404, detail="No records found.")
    return sorted(MOCK_SQL_STORE, key=lambda x: x["timestamp"], reverse=True)[0]

@app.get("/api/v1/sql/time-series/range", tags=["SQL Time-Series"])
def get_sql_range(start_date: str = Query(..., example="2013-03-01 00:00:00"), end_date: str = Query(..., example="2013-03-02 00:00:00")):
    """TIME-SERIES: Fetch records between two dates."""
    return [r for r in MOCK_SQL_STORE if start_date <= r["timestamp"] <= end_date]

# ---------------------------------------------------------------------------
# 4. MONGODB ENDPOINTS (Mocked)
# ---------------------------------------------------------------------------
@app.post("/api/v1/mongo/air-quality", status_code=201, tags=["MongoDB Endpoints"])
def create_mongo_record(record: AirQualityRecord):
    """CREATE: Add a new document to MongoDB."""
    custom_id = f"{record.station}_{record.timestamp.replace(' ', 'T')}"
    if custom_id in MOCK_MONGO_STORE:
        raise HTTPException(status_code=400, detail="Document ID already exists.")
    new_doc = record.model_dump()
    new_doc["_id"] = custom_id
    MOCK_MONGO_STORE[custom_id] = new_doc
    return {"message": "Document added successfully", "_id": custom_id}

@app.get("/api/v1/mongo/air-quality/{record_id}", tags=["MongoDB Endpoints"])
def get_mongo_record(record_id: str = Path(..., example="Aotizhongxin_2013-03-01T00:00:00")):
    """READ: Get a specific document by its MongoDB _id."""
    if record_id not in MOCK_MONGO_STORE:
        raise HTTPException(status_code=404, detail="Document not found")
    return MOCK_MONGO_STORE[record_id]

@app.put("/api/v1/mongo/air-quality/{record_id}", tags=["MongoDB Endpoints"])
def update_mongo_record(record: AirQualityRecord, record_id: str = Path(..., example="Aotizhongxin_2013-03-01T00:00:00")):
    """UPDATE: Modify an existing MongoDB document."""
    if record_id not in MOCK_MONGO_STORE:
        raise HTTPException(status_code=404, detail="Document not found")
    updated_doc = record.model_dump()
    updated_doc["_id"] = record_id
    MOCK_MONGO_STORE[record_id] = updated_doc
    return {"message": "Document updated successfully"}

@app.delete("/api/v1/mongo/air-quality/{record_id}", tags=["MongoDB Endpoints"])
def delete_mongo_record(record_id: str = Path(..., example="Aotizhongxin_2013-03-01T00:00:00")):
    """DELETE: Remove a MongoDB document."""
    if record_id not in MOCK_MONGO_STORE:
        raise HTTPException(status_code=404, detail="Document not found")
    del MOCK_MONGO_STORE[record_id]
    return {"message": "Document deleted successfully"}

@app.get("/api/v1/mongo/time-series/latest", tags=["MongoDB Time-Series"])
def get_mongo_latest():
    """TIME-SERIES: Fetch the most recent timestamp document."""
    if not MOCK_MONGO_STORE:
        raise HTTPException(status_code=404, detail="No documents found.")
    return sorted(MOCK_MONGO_STORE.values(), key=lambda x: x["timestamp"], reverse=True)[0]

@app.get("/api/v1/mongo/time-series/range", tags=["MongoDB Time-Series"])
def get_mongo_range(start_date: str = Query(..., example="2013-03-01 00:00:00"), end_date: str = Query(..., example="2013-03-02 00:00:00")):
    """TIME-SERIES: Fetch documents between two dates."""
    return [d for d in MOCK_MONGO_STORE.values() if start_date <= d["timestamp"] <= end_date]
