"""Load the Beijing air-quality CSV files into MongoDB Atlas.

Expected flow:
1. Create a free M0 cluster on MongoDB Atlas and copy your connection string.
2. Set MONGO_URI in your environment or in a .env file at the project root.
3. Run this script from the repo root:
       python mongo_database/load_data.py

The script inserts all 420,768 documents across 12 stations. Re-running is
safe: the deterministic _id causes duplicates to be skipped.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import pandas as pd
from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError


def load_dotenv_file(dotenv_path: Path) -> None:
    """Read a .env file and set variables that are not already in os.environ."""
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


def get_season(month: int) -> str:
    """Map a month number to its meteorological season (Northern Hemisphere)."""
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    else:
        return "Autumn"


def clean(value) -> float | None:
    """Convert NaN / NA to None (BSON null); leave valid numerics as float."""
    if value is None:
        return None
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def row_to_doc(row) -> dict:
    """Convert a single DataFrame row into the target MongoDB document schema."""
    ts = (
        f"{int(row['year']):04d}-{int(row['month']):02d}-"
        f"{int(row['day']):02d}T{int(row['hour']):02d}:00:00"
    )
    return {
        "_id":       f"{row['station']}_{ts}",
        "station":   row['station'],
        "timestamp": ts,
        "year":      int(row['year']),
        "month":     int(row['month']),
        "day":       int(row['day']),
        "hour":      int(row['hour']),
        "season":    get_season(int(row['month'])),
        "pollutants": {
            "PM2_5": clean(row["PM2.5"]),
            "PM10":  clean(row["PM10"]),
            "SO2":   clean(row["SO2"]),
            "NO2":   clean(row["NO2"]),
            "CO":    clean(row["CO"]),
            "O3":    clean(row["O3"]),
        },
        "weather": {
            "TEMP": clean(row["TEMP"]),
            "PRES": clean(row["PRES"]),
            "DEWP": clean(row["DEWP"]),
            "RAIN": clean(row["RAIN"]),
            "wd":   row["wd"] if pd.notna(row["wd"]) else None,
            "WSPM": clean(row["WSPM"]),
        },
    }


def load_csvs(data_dir: Path) -> pd.DataFrame:
    """Read and concatenate all 12 station CSV files into one DataFrame."""
    csv_files = sorted(data_dir.glob("PRSA_Data_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in: {data_dir}")

    print(f"CSV files found: {len(csv_files)}")
    frames = []
    for path in csv_files:
        print(f"  Loaded: {path.name}")
        frames.append(pd.read_csv(path))

    df = pd.concat(frames, ignore_index=True)
    print(f"Combined shape : {df.shape}")
    return df


def create_indexes(collection) -> None:
    """Create the three indexes used by the analytical queries."""
    # drop stale non-_id indexes so re-runs start clean
    for idx in collection.list_indexes():
        if idx["name"] != "_id_":
            collection.drop_index(idx["name"])

    collection.create_index(
        [("station", ASCENDING), ("timestamp", ASCENDING)],
        name="idx_station_timestamp",
        unique=True,
    )
    collection.create_index([("timestamp", ASCENDING)], name="idx_timestamp")
    collection.create_index([("pollutants.PM2_5", ASCENDING)], name="idx_pm25")

    print("Indexes created:")
    for idx in collection.list_indexes():
        print(f"  {idx['name']}")


def insert_documents(collection, df: pd.DataFrame, chunk_size: int) -> None:
    """Convert DataFrame rows to documents and insert in batches."""
    docs = [row_to_doc(row) for _, row in df.iterrows()]

    inserted = 0
    skipped  = 0

    for i in range(0, len(docs), chunk_size):
        batch = docs[i : i + chunk_size]
        try:
            result = collection.insert_many(batch, ordered=False)
            inserted += len(result.inserted_ids)
        except BulkWriteError as exc:
            # duplicate keys are expected on re-runs; count them as skipped
            write_errors = exc.details.get("writeErrors", [])
            dupes = sum(1 for e in write_errors if e.get("code") == 11000)
            inserted += len(batch) - dupes
            skipped  += dupes

        if i % 100_000 == 0 and i > 0:
            print(f"  {i:,} / {len(docs):,} processed...")

    print(f"\nInserted : {inserted:,}")
    print(f"Skipped  : {skipped:,}  (duplicates from prior runs)")
    print(f"Total    : {inserted + skipped:,}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load Beijing air-quality CSVs into MongoDB Atlas."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "beijing_air_quality_data",
        help="Folder containing the PRSA_Data_*.csv files.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5000,
        help="Number of documents to insert per batch (default: 5000).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    load_dotenv_file(project_root / ".env")
    load_dotenv_file(Path(__file__).resolve().parent / ".env")

    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise EnvironmentError(
            "MONGO_URI environment variable not set.\n"
            "Add it to a .env file at the project root or export it in your terminal:\n"
            "  export MONGO_URI='mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/'"
        )

    if not args.data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {args.data_dir}")

    client     = MongoClient(mongo_uri)
    db         = client["beijing_air_quality"]
    collection = db["air_quality_readings"]
    client.admin.command("ping")
    print(f"Connected to MongoDB Atlas, database: {db.name}\n")

    df = load_csvs(args.data_dir)

    print()
    create_indexes(collection)

    print()
    insert_documents(collection, df, args.chunk_size)

    total = collection.count_documents({})
    print(f"\nDocuments in collection: {total:,}")
    print("Load complete.")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())