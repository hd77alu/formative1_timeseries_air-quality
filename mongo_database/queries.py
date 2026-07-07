"""Run all five analytical queries against the beijing_air_quality MongoDB database.

Run after load_data.py has completed:
    export MONGO_URI="mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/"
    python mongo_database/queries.py

Pre-run results are documented in query_results.md.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def divider(title: str) -> None:
    line = "=" * 60
    print(f"\n{line}")
    print(f"  {title}")
    print(line)


# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------

project_root = Path(__file__).resolve().parent.parent
load_dotenv_file(project_root / ".env")
load_dotenv_file(Path(__file__).resolve().parent / ".env")

mongo_uri = os.environ.get("MONGO_URI")
if not mongo_uri:
    raise EnvironmentError(
        "MONGO_URI environment variable not set.\n"
        "Export it or add it to a .env file at the project root."
    )

client     = MongoClient(mongo_uri)
db         = client["beijing_air_quality"]
collection = db["air_quality_readings"]
client.admin.command("ping")
print(f"Connected — database: {db.name}  |  collection: {collection.name}")
print(f"Total documents: {collection.count_documents({}):,}")


# ---------------------------------------------------------------------------
# Query 1 — Latest record in the collection
# Task 3 pattern: GET /latest
# Uses idx_timestamp — no full collection scan.
# ---------------------------------------------------------------------------

divider("Query 1 — Latest Record")

q1 = collection.find_one({}, sort=[("timestamp", DESCENDING)])

# FIX: Handle empty collection gracefully
if q1 is None:
    print("WARNING: Collection is empty — no documents to query.")
    print("Run load_data.py first to populate the database.")
else:
    print(f"Station   : {q1['station']}")
    print(f"Timestamp : {q1['timestamp']}")
    print(f"Season    : {q1['season']}")
    print(f"PM2.5     : {q1['pollutants']['PM2_5']}")
    print(f"NO2       : {q1['pollutants']['NO2']}")
    print(f"TEMP      : {q1['weather']['TEMP']}")


# ---------------------------------------------------------------------------
# Query 2 — Records for one station within a date range
# Task 3 pattern: GET /records?station=&start=&end=
# Uses compound index idx_station_timestamp — single index range scan.
# ---------------------------------------------------------------------------

divider("Query 2 — Date Range (Dongsi, 2015-01-01 → 2015-01-03)")

q2_docs = list(collection.find(
    {
        "station":   "Dongsi",
        "timestamp": {
            "$gte": "2015-01-01T00:00:00",
            "$lte": "2015-01-03T23:00:00",
        },
    },
    sort=[("timestamp", ASCENDING)],
))

print(f"Documents returned : {len(q2_docs)}  (expected 72 = 3 days × 24 hours)")
print()

rows = [
    {
        "timestamp": d["timestamp"],
        "PM2.5":     d["pollutants"]["PM2_5"],
        "PM10":      d["pollutants"]["PM10"],
        "TEMP":      d["weather"]["TEMP"],
        "WSPM":      d["weather"]["WSPM"],
        "wd":        d["weather"]["wd"],
    }
    for d in q2_docs
]
df_q2 = pd.DataFrame(rows)
print("First 8 records:")
print(df_q2.head(8).to_string(index=False))


# ---------------------------------------------------------------------------
# Query 3 — All 12 stations ranked by average PM2.5
# Aggregation pipeline: $match nulls → $group avg/max → $sort → $project
# ---------------------------------------------------------------------------

divider("Query 3 — Stations Ranked by Average PM2.5")

q3 = list(collection.aggregate([
    {"$match":   {"pollutants.PM2_5": {"$ne": None}}},
    {"$group":   {
        "_id":      "$station",
        "avg_pm25": {"$avg": "$pollutants.PM2_5"},
        "max_pm25": {"$max": "$pollutants.PM2_5"},
        "readings": {"$sum": 1},
    }},
    {"$sort":    {"avg_pm25": DESCENDING}},
    {"$project": {
        "_id":      0,
        "station":  "$_id",
        "avg_pm25": {"$round": ["$avg_pm25", 2]},
        "max_pm25": {"$round": ["$max_pm25", 2]},
        "readings": 1,
    }},
]))

df_q3 = pd.DataFrame(q3)
df_q3.index = range(1, len(df_q3) + 1)
df_q3.index.name = "rank"
print(df_q3.to_string())


# ---------------------------------------------------------------------------
# Query 4 — Hazardous pollution events (PM2.5 > 300 µg/m³)
# Part A: hazardous hours per station
# Part B: 10 single worst readings in the dataset
# Uses idx_pm25 for the threshold filter.
# ---------------------------------------------------------------------------

divider("Query 4 — Hazardous Events (PM2.5 > 300 µg/m³)")

# Part A — count per station
q4a = list(collection.aggregate([
    {"$match":   {"pollutants.PM2_5": {"$gt": 300.0}}},
    {"$group":   {
        "_id":             "$station",
        "hazardous_hours": {"$sum": 1},
        "peak_pm25":       {"$max": "$pollutants.PM2_5"},
    }},
    {"$sort":    {"hazardous_hours": DESCENDING}},
    {"$project": {
        "_id":             0,
        "station":         "$_id",
        "hazardous_hours": 1,
        "peak_pm25":       {"$round": ["$peak_pm25", 1]},
    }},
]))

print("Part A — Hazardous hours per station:")
print(pd.DataFrame(q4a).to_string(index=False))

# Part B — 10 worst individual readings
q4b = list(collection.find(
    {"pollutants.PM2_5": {"$gt": 300.0}},
    {"_id": 0, "station": 1, "timestamp": 1, "pollutants.PM2_5": 1, "weather.TEMP": 1},
).sort("pollutants.PM2_5", DESCENDING).limit(10))

df_q4b = pd.json_normalize(q4b)
df_q4b.columns = ["station", "timestamp", "PM2_5", "TEMP"]
print("\nPart B — 10 worst individual readings:")
print(df_q4b.to_string(index=False))


# ---------------------------------------------------------------------------
# Query 5 — Seasonal average PM2.5 across all stations
# Groups on the pre-computed `season` field inserted by load_data.py.
# ---------------------------------------------------------------------------

divider("Query 5 — Seasonal Average PM2.5")

q5 = list(collection.aggregate([
    {"$match":   {"pollutants.PM2_5": {"$ne": None}}},
    {"$group":   {
        "_id":      "$season",
        "avg_pm25": {"$avg": "$pollutants.PM2_5"},
        "max_pm25": {"$max": "$pollutants.PM2_5"},
        "min_pm25": {"$min": "$pollutants.PM2_5"},
        "readings": {"$sum": 1},
    }},
    {"$sort":    {"avg_pm25": DESCENDING}},
    {"$project": {
        "_id":      0,
        "season":   "$_id",
        "avg_pm25": {"$round": ["$avg_pm25", 2]},
        "max_pm25": {"$round": ["$max_pm25", 2]},
        "min_pm25": {"$round": ["$min_pm25", 2]},
        "readings": 1,
    }},
]))

df_q5 = pd.DataFrame(q5)
print(df_q5.to_string(index=False))

if q5:
    winter = next((r for r in q5 if r["season"] == "Winter"), None)
    summer = next((r for r in q5 if r["season"] == "Summer"), None)
    if winter and summer and summer["avg_pm25"] != 0:
        ratio = round(winter["avg_pm25"] / summer["avg_pm25"], 2)
        print(f"\nWinter average is {ratio}x higher than Summer average.")
    else:
        print("\nCannot compute winter/summer ratio (missing data or division by zero).")
else:
    print("\nNo seasonal data available — collection may be empty.")

print("\nAll queries complete.")
client.close()