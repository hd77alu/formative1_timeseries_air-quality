"""
Beijing Air Quality — End-to-End Prediction Script
Task 4 | Group 5 | African Leadership University

This script ties together all four tasks of the pipeline:

    Step 1 — Fetch a time-series record from the API       (Task 3)
    Step 2 — Preprocess it using the Task 1C pipeline      (Task 1C)
    Step 3 — Load the trained Random Forest model          (Task 1C)
    Step 4 — Produce and print a PM2.5 prediction

Usage:
    # Make sure the API server is running first:
    #   uvicorn app:app --reload

    python predict.py

    # Optional arguments:
    python predict.py --station Dongsi --timestamp "2015-06-10T14:00:00"
    python predict.py --source mongo     # fetch from MongoDB endpoint instead of SQL
    python predict.py --model rf_model.pkl
"""

import argparse
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------
API_BASE      = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_MODEL = os.getenv("MODEL_PATH", "rf_model.pkl")

# The feature columns produced by the Task 1C preprocessing pipeline.
# This list must match exactly what the model was trained on.
FEATURE_COLS = [
    # Raw pollutants (lag features are the primary input)
    "PM10", "SO2", "NO2", "CO", "O3",
    # Weather
    "TEMP", "PRES", "DEWP", "RAIN", "WSPM",
    # Cyclical time encodings
    "hour_sin", "hour_cos",
    "month_sin", "month_cos",
    "day_of_week_sin", "day_of_week_cos",
    # Wind vector components
    "wind_u", "wind_v",
    # Lag features — target and key pollutants shifted 1 and 2 hours
    "PM2.5_lag1", "PM2.5_lag2",
    "SO2_lag1",   "SO2_lag2",
    "NO2_lag1",   "NO2_lag2",
    "CO_lag1",    "CO_lag2",
    "TEMP_lag1",  "TEMP_lag2",
    "WSPM_lag1",  "WSPM_lag2",
]

# Wind direction string → degrees mapping used during feature engineering
WD_TO_DEGREES = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
}


# ---------------------------------------------------------------------------
# Step 1 — Fetch a record from the API
# ---------------------------------------------------------------------------
def fetch_latest_from_api(source: str) -> dict:
    """
    Call the /time-series/latest endpoint on either the SQL or MongoDB backend
    and return the raw JSON response as a Python dict.

    Args:
        source: "sql" or "mongo"

    Returns:
        dict with keys: station, timestamp, pollutants, weather, etc.
    """
    url = f"{API_BASE}/api/v1/{source}/time-series/latest"
    print(f"[Step 1] Fetching latest record from: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(
            "\n[ERROR] Could not connect to the API server.\n"
            "        Make sure it is running:  uvicorn app:app --reload\n"
        )
    except requests.exceptions.HTTPError as e:
        sys.exit(f"\n[ERROR] API returned an error: {e}\n")

    data = response.json()
    print(f"         Station   : {data.get('station', data.get('station_name', '?'))}")
    print(f"         Timestamp : {data.get('timestamp', data.get('observed_at', '?'))}")
    return data


def fetch_by_timestamp_from_api(source: str, station: str, timestamp: str) -> dict:
    """
    Fetch a specific record by station + timestamp using the date-range endpoint.

    Args:
        source:    "sql" or "mongo"
        station:   Station name e.g. "Dongsi"
        timestamp: ISO string e.g. "2015-06-10T14:00:00"

    Returns:
        First matching record as a dict, or exits with an error message.
    """
    url = f"{API_BASE}/api/v1/{source}/time-series/range"
    params = {
        "station":    station,
        "start_date": timestamp,
        "end_date":   timestamp,
    }
    print(f"[Step 1] Fetching record from: {url}")
    print(f"         Station   : {station}")
    print(f"         Timestamp : {timestamp}")

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(
            "\n[ERROR] Could not connect to the API server.\n"
            "        Make sure it is running:  uvicorn app:app --reload\n"
        )

    results = response.json()
    if not results:
        sys.exit(
            f"\n[ERROR] No record found for station='{station}' at timestamp='{timestamp}'.\n"
            f"        Try the --source flag or check the timestamp format (YYYY-MM-DDTHH:MM:SS).\n"
        )
    return results[0]


# ---------------------------------------------------------------------------
# Step 2 — Preprocess the raw API record
# ---------------------------------------------------------------------------
def _parse_pollutants(record: dict) -> dict:
    """
    Extract flat pollutant and weather values from either a SQL or MongoDB
    API response. Both endpoints return slightly different key structures:
      - MongoDB: record["pollutants"]["PM2_5"], record["weather"]["TEMP"]
      - SQL:     record["pm25"], record["temp"]
    """
    flat = {}

    if "pollutants" in record:
        # MongoDB response structure
        p = record["pollutants"]
        w = record["weather"]
        flat["PM2.5"] = p.get("PM2_5")
        flat["PM10"]  = p.get("PM10")
        flat["SO2"]   = p.get("SO2")
        flat["NO2"]   = p.get("NO2")
        flat["CO"]    = p.get("CO")
        flat["O3"]    = p.get("O3")
        flat["TEMP"]  = w.get("TEMP")
        flat["PRES"]  = w.get("PRES")
        flat["DEWP"]  = w.get("DEWP")
        flat["RAIN"]  = w.get("RAIN")
        flat["wd"]    = w.get("wd")
        flat["WSPM"]  = w.get("WSPM")
        flat["year"]  = record.get("year")
        flat["month"] = record.get("month")
        flat["day"]   = record.get("day")
        flat["hour"]  = record.get("hour")
    else:
        # SQL (v_hourly_air_quality view) response structure
        flat["PM2.5"] = record.get("pm25")
        flat["PM10"]  = record.get("pm10")
        flat["SO2"]   = record.get("so2")
        flat["NO2"]   = record.get("no2")
        flat["CO"]    = record.get("co")
        flat["O3"]    = record.get("o3")
        flat["TEMP"]  = record.get("temp")
        flat["PRES"]  = record.get("pres")
        flat["DEWP"]  = record.get("dewp")
        flat["RAIN"]  = record.get("rain")
        flat["wd"]    = record.get("wd")
        flat["WSPM"]  = record.get("wspm")
        # Parse datetime from observed_at string
        ts = record.get("observed_at", "2013-01-01T00:00:00")
        dt = pd.to_datetime(ts)
        flat["year"]  = dt.year
        flat["month"] = dt.month
        flat["day"]   = dt.day
        flat["hour"]  = dt.hour

    return flat


def preprocess(record: dict) -> pd.DataFrame:
    """
    Apply the same preprocessing pipeline used in Task 1C to a single record.

    Since we only have one timestep (no history in the API response), lag
    features are set to the current value as a best approximation. In a
    production system you would pass the last N records to compute true lags.

    Args:
        record: Raw dict from the API endpoint

    Returns:
        Single-row DataFrame with all FEATURE_COLS present and filled
    """
    print("\n[Step 2] Preprocessing the record...")

    flat = _parse_pollutants(record)

    # ── Cyclical time encodings ─────────────────────────────────────────────
    hour        = flat.get("hour", 0) or 0
    month       = flat.get("month", 1) or 1
    day         = flat.get("day", 1) or 1
    # Approximate day of week from year/month/day
    dt          = pd.Timestamp(year=flat["year"], month=month, day=day)
    day_of_week = dt.dayofweek   # 0 = Monday

    row = {
        "PM10":  flat.get("PM10"),
        "SO2":   flat.get("SO2"),
        "NO2":   flat.get("NO2"),
        "CO":    flat.get("CO"),
        "O3":    flat.get("O3"),
        "TEMP":  flat.get("TEMP"),
        "PRES":  flat.get("PRES"),
        "DEWP":  flat.get("DEWP"),
        "RAIN":  flat.get("RAIN"),
        "WSPM":  flat.get("WSPM"),
        # Cyclical time features
        "hour_sin":         np.sin(2 * np.pi * hour / 24),
        "hour_cos":         np.cos(2 * np.pi * hour / 24),
        "month_sin":        np.sin(2 * np.pi * month / 12),
        "month_cos":        np.cos(2 * np.pi * month / 12),
        "day_of_week_sin":  np.sin(2 * np.pi * day_of_week / 7),
        "day_of_week_cos":  np.cos(2 * np.pi * day_of_week / 7),
    }

    # ── Wind vector (U/V components) ────────────────────────────────────────
    wd_str  = flat.get("wd") or "N"
    degrees = WD_TO_DEGREES.get(wd_str.strip().upper(), 0.0)
    radians = np.deg2rad(degrees)
    wspm    = float(flat.get("WSPM") or 0.0)
    row["wind_u"] = wspm * np.sin(radians)   # east-west component
    row["wind_v"] = wspm * np.cos(radians)   # north-south component

    # ── Lag features ────────────────────────────────────────────────────────
    # We only have a single timestep, so lag_1 and lag_2 use the current value.
    # This is a reasonable approximation for the prediction demo.
    current_pm25 = flat.get("PM2.5") or 0.0
    for col, src_val in [
        ("PM2.5", current_pm25),
        ("SO2",   flat.get("SO2") or 0.0),
        ("NO2",   flat.get("NO2") or 0.0),
        ("CO",    flat.get("CO")  or 0.0),
        ("TEMP",  flat.get("TEMP") or 0.0),
        ("WSPM",  flat.get("WSPM") or 0.0),
    ]:
        row[f"{col}_lag1"] = src_val
        row[f"{col}_lag2"] = src_val

    df = pd.DataFrame([row])

    # ── Fill any remaining NaN with column medians (mirrors Task 1C imputation)
    df = df.fillna(df.median(numeric_only=True))

    # ── Ensure all expected columns exist in the right order ────────────────
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    df = df[FEATURE_COLS]

    print(f"         Feature vector shape : {df.shape}")
    print(f"         Non-null features    : {df.notna().sum().sum()} / {df.shape[1]}")
    return df


# ---------------------------------------------------------------------------
# Step 3 — Load the trained model
# ---------------------------------------------------------------------------
def load_model(model_path: str):
    """
    Load the saved Random Forest model from a .pkl file using joblib.

    The model is saved at the end of the Task 1C notebook with:
        import joblib
        joblib.dump(rf_log, "rf_model.pkl")

    Args:
        model_path: Path to the .pkl file

    Returns:
        Loaded sklearn estimator
    """
    path = Path(model_path)
    if not path.exists():
        sys.exit(
            f"\n[ERROR] Model file not found: {path.resolve()}\n"
            f"        Save the model in the notebook with:\n"
            f"            import joblib\n"
            f"            joblib.dump(rf_log, 'rf_model.pkl')\n"
            f"        Then re-run this script.\n"
        )

    print(f"\n[Step 3] Loading model from: {path.resolve()}")
    model = joblib.load(path)
    print(f"         Model type : {type(model).__name__}")
    return model


# ---------------------------------------------------------------------------
# Step 4 — Make and print the prediction
# ---------------------------------------------------------------------------
def predict(model, features: pd.DataFrame, record: dict) -> None:
    """
    Run the model on the preprocessed feature vector and print the result.

    The Task 1C champion model (Experiment 2) was trained on log1p(PM2.5),
    so we apply np.expm1() to reverse the transformation.

    Args:
        model:    Loaded sklearn estimator
        features: Single-row DataFrame from preprocess()
        record:   Original API response (for context printing)
    """
    print("\n[Step 4] Running prediction...")

    # Predict — model was trained on log1p(PM2.5), so reverse with expm1
    log_pred = model.predict(features)[0]
    pm25_pred = float(np.expm1(log_pred))

    # Pull the station and timestamp for display
    station   = record.get("station", record.get("station_name", "Unknown"))
    timestamp = record.get("timestamp", record.get("observed_at", "Unknown"))

    # WHO 24-hour PM2.5 guideline is 15 µg/m³
    who_guideline = 15.0
    status = "✅ Below WHO guideline" if pm25_pred <= who_guideline else "⚠️  Above WHO guideline"

    print()
    print("=" * 55)
    print("  PREDICTION RESULT")
    print("=" * 55)
    print(f"  Station           : {station}")
    print(f"  Timestamp         : {timestamp}")
    print(f"  Predicted PM2.5   : {pm25_pred:.2f} µg/m³")
    print(f"  WHO 24-hr limit   : {who_guideline} µg/m³")
    print(f"  Status            : {status}")
    print("=" * 55)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Beijing Air Quality — End-to-End PM2.5 Prediction Script (Task 4)"
    )
    parser.add_argument(
        "--source",
        choices=["sql", "mongo"],
        default="mongo",
        help="Which API backend to fetch from (default: mongo)",
    )
    parser.add_argument(
        "--station",
        type=str,
        default=None,
        help="Station name to fetch (optional; fetches latest if omitted)",
    )
    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="Specific timestamp to fetch e.g. '2015-06-10T14:00:00' (requires --station)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Path to saved model .pkl file (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    print()
    print("Beijing Air Quality — Task 4 Prediction Script")
    print("=" * 55)
    print(f"  API backend : {args.source.upper()}")
    print(f"  Model file  : {args.model}")
    print("=" * 55)

    # ── Step 1: Fetch from API ───────────────────────────────────────────────
    if args.station and args.timestamp:
        record = fetch_by_timestamp_from_api(args.source, args.station, args.timestamp)
    else:
        record = fetch_latest_from_api(args.source)

    # ── Step 2: Preprocess ──────────────────────────────────────────────────
    features = preprocess(record)

    # ── Step 3: Load model ──────────────────────────────────────────────────
    model = load_model(args.model)

    # ── Step 4: Predict ─────────────────────────────────────────────────────
    predict(model, features, record)


if __name__ == "__main__":
    main()