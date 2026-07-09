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
    python predict.py --source mongo
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
# Configuration
# ---------------------------------------------------------------------------
API_BASE      = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_MODEL = os.getenv("MODEL_PATH", "rf_model.pkl")

# Exact 41 features the model was trained on — verified from model.feature_names_in_
FEATURE_COLS = [
    "SO2", "NO2", "CO", "O3",
    "TEMP", "PRES", "DEWP", "RAIN", "WSPM",
    "hour_of_day", "day_of_week",
    "hour_sin", "hour_cos",
    "month_sin", "month_cos",
    "wind_u", "wind_v",
    "PM2.5_lag_1", "PM2.5_lag_2",
    "SO2_lag_1",   "SO2_lag_2",
    "NO2_lag_1",   "NO2_lag_2",
    "CO_lag_1",    "CO_lag_2",
    "TEMP_lag_1",  "TEMP_lag_2",
    "WSPM_lag_1",  "WSPM_lag_2",
    # One-hot encoded station columns (11 stations — Aotizhongxin is the dropped base)
    "st_Aotizhongxin",
    "st_Changping",
    "st_Dingling",
    "st_Dongsi",
    "st_Guanyuan",
    "st_Gucheng",
    "st_Huairou",
    "st_Nongzhanguan",
    "st_Shunyi",
    "st_Tiantan",
    "st_Wanliu",
    "st_Wanshouxigong",
]

# All 12 station names used for one-hot encoding
ALL_STATIONS = [
    "Aotizhongxin", "Changping", "Dingling", "Dongsi",
    "Guanyuan", "Gucheng", "Huairou", "Nongzhanguan",
    "Shunyi", "Tiantan", "Wanliu", "Wanshouxigong",
]

# Wind direction → degrees
WD_TO_DEGREES = {
    "N": 0,   "NNE": 22.5,  "NE": 45,   "ENE": 67.5,
    "E": 90,  "ESE": 112.5, "SE": 135,  "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225,  "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315,  "NNW": 337.5,
}


# ---------------------------------------------------------------------------
# Step 1 — Fetch a record from the API
# ---------------------------------------------------------------------------
def fetch_latest_from_api(source: str) -> dict:
    """Fetch the most recent record from the SQL or MongoDB latest endpoint."""
    url = f"{API_BASE}/api/v1/{source}/time-series/latest"
    print(f"[Step 1] Fetching latest record from: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(
            "\n[ERROR] Cannot connect to the API.\n"
            "        Make sure it is running: uvicorn app:app --reload\n"
        )
    except requests.exceptions.HTTPError as e:
        sys.exit(f"\n[ERROR] API error: {e}\n")

    data = response.json()
    print(f"         Station   : {data.get('station', data.get('station_name', '?'))}")
    print(f"         Timestamp : {data.get('timestamp', data.get('observed_at', '?'))}")
    return data


def fetch_by_timestamp_from_api(source: str, station: str, timestamp: str) -> dict:
    """Fetch a specific station + timestamp record via the date-range endpoint."""
    url = f"{API_BASE}/api/v1/{source}/time-series/range"
    params = {"station": station, "start_date": timestamp, "end_date": timestamp}
    print(f"[Step 1] Fetching record — station={station}, timestamp={timestamp}")

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(
            "\n[ERROR] Cannot connect to the API.\n"
            "        Make sure it is running: uvicorn app:app --reload\n"
        )

    results = response.json()
    if not results:
        sys.exit(
            f"\n[ERROR] No record found for station='{station}' "
            f"at timestamp='{timestamp}'.\n"
        )
    return results[0]


# ---------------------------------------------------------------------------
# Step 2 — Preprocess
# ---------------------------------------------------------------------------
def _parse_record(record: dict) -> dict:
    """
    Normalise the API response into a flat dict regardless of whether it
    came from the MongoDB endpoint (nested pollutants/weather sub-docs)
    or the SQL endpoint (flat column names).
    """
    flat = {}

    if "pollutants" in record:
        # MongoDB structure
        p, w = record["pollutants"], record["weather"]
        flat.update({
            "PM2.5": p.get("PM2_5"), "PM10": p.get("PM10"),
            "SO2":   p.get("SO2"),   "NO2":  p.get("NO2"),
            "CO":    p.get("CO"),    "O3":   p.get("O3"),
            "TEMP":  w.get("TEMP"),  "PRES": w.get("PRES"),
            "DEWP":  w.get("DEWP"),  "RAIN": w.get("RAIN"),
            "wd":    w.get("wd"),    "WSPM": w.get("WSPM"),
            "year":  record.get("year"),  "month": record.get("month"),
            "day":   record.get("day"),   "hour":  record.get("hour"),
            "station": record.get("station"),
        })
    else:
        # SQL (v_hourly_air_quality view) structure
        ts = pd.to_datetime(record.get("observed_at", "2013-01-01T00:00:00"))
        flat.update({
            "PM2.5": record.get("pm25"), "PM10": record.get("pm10"),
            "SO2":   record.get("so2"),  "NO2":  record.get("no2"),
            "CO":    record.get("co"),   "O3":   record.get("o3"),
            "TEMP":  record.get("temp"), "PRES": record.get("pres"),
            "DEWP":  record.get("dewp"), "RAIN": record.get("rain"),
            "wd":    record.get("wd"),   "WSPM": record.get("wspm"),
            "year":  ts.year, "month": ts.month,
            "day":   ts.day,  "hour":  ts.hour,
            "station": record.get("station_name"),
        })

    return flat


def preprocess(record: dict) -> pd.DataFrame:
    """
    Replicate the exact Task 1C preprocessing pipeline for a single record.

    Features built:
    - Raw pollutants (SO2, NO2, CO, O3) and weather variables
    - hour_of_day, day_of_week (raw integers)
    - Cyclical hour and month encodings (sin/cos)
    - Wind U/V vector components
    - Lag features for PM2.5, SO2, NO2, CO, TEMP, WSPM (lags 1 and 2)
    - One-hot encoded station columns (st_<StationName>)

    Lag values are approximated as the current reading since only one
    timestep is available from the API response.
    """
    print("\n[Step 2] Preprocessing the record...")

    flat = _parse_record(record)

    hour        = int(flat.get("hour")  or 0)
    month       = int(flat.get("month") or 1)
    day         = int(flat.get("day")   or 1)
    year        = int(flat.get("year")  or 2013)
    dt          = pd.Timestamp(year=year, month=month, day=day)
    day_of_week = dt.dayofweek  # 0 = Monday

    # ── Wind vector ─────────────────────────────────────────────────────────
    wd_str  = (flat.get("wd") or "N").strip().upper()
    degrees = WD_TO_DEGREES.get(wd_str, 0.0)
    wspm    = float(flat.get("WSPM") or 0.0)
    wind_u  = wspm * np.sin(np.deg2rad(degrees))
    wind_v  = wspm * np.cos(np.deg2rad(degrees))

    # ── Build the base feature row ───────────────────────────────────────────
    row = {
        "SO2":  float(flat.get("SO2")  or 0.0),
        "NO2":  float(flat.get("NO2")  or 0.0),
        "CO":   float(flat.get("CO")   or 0.0),
        "O3":   float(flat.get("O3")   or 0.0),
        "TEMP": float(flat.get("TEMP") or 0.0),
        "PRES": float(flat.get("PRES") or 0.0),
        "DEWP": float(flat.get("DEWP") or 0.0),
        "RAIN": float(flat.get("RAIN") or 0.0),
        "WSPM": wspm,
        # Raw time integers (Task 1C used these directly, not encoded)
        "hour_of_day": hour,
        "day_of_week": day_of_week,
        # Cyclical encodings
        "hour_sin":  np.sin(2 * np.pi * hour  / 24),
        "hour_cos":  np.cos(2 * np.pi * hour  / 24),
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
        # Wind vectors
        "wind_u": wind_u,
        "wind_v": wind_v,
    }

    # ── Lag features (approximated as current value) ─────────────────────────
    current_pm25 = float(flat.get("PM2.5") or 0.0)
    for col, val in [
        ("PM2.5", current_pm25),
        ("SO2",   float(flat.get("SO2")  or 0.0)),
        ("NO2",   float(flat.get("NO2")  or 0.0)),
        ("CO",    float(flat.get("CO")   or 0.0)),
        ("TEMP",  float(flat.get("TEMP") or 0.0)),
        ("WSPM",  wspm),
    ]:
        row[f"{col}_lag_1"] = val
        row[f"{col}_lag_2"] = val

    # ── One-hot encode station ───────────────────────────────────────────────
    station = flat.get("station") or ""
    for s in ALL_STATIONS:
        row[f"st_{s}"] = 1.0 if station == s else 0.0

    # ── Assemble DataFrame and enforce exact column order ────────────────────
    df = pd.DataFrame([row])
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0
    df = df[FEATURE_COLS]

    print(f"         Feature vector shape : {df.shape}")
    print(f"         Non-null features    : {df.notna().sum().sum()} / {df.shape[1]}")
    return df


# ---------------------------------------------------------------------------
# Step 3 — Load the model
# ---------------------------------------------------------------------------
def load_model(model_path: str):
    """Load the saved Random Forest model from disk using joblib."""
    path = Path(model_path)
    if not path.exists():
        sys.exit(
            f"\n[ERROR] Model file not found: {path.resolve()}\n"
            f"        Save it in the notebook with:\n"
            f"            import joblib\n"
            f"            joblib.dump(rf_log, 'rf_model.pkl')\n"
        )

    print(f"\n[Step 3] Loading model from: {path.resolve()}")
    model = joblib.load(path)
    print(f"         Model type   : {type(model).__name__}")
    print(f"         Features     : {len(model.feature_names_in_)}")
    return model


# ---------------------------------------------------------------------------
# Step 4 — Predict and print
# ---------------------------------------------------------------------------
def predict(model, features: pd.DataFrame, record: dict) -> None:
    """
    Run the model and print the PM2.5 prediction.

    The model was trained on log1p(PM2.5), so we reverse with np.expm1().
    """
    print("\n[Step 4] Running prediction...")

    log_pred  = model.predict(features)[0]
    pm25_pred = float(np.expm1(log_pred))

    station   = record.get("station", record.get("station_name", "Unknown"))
    timestamp = record.get("timestamp", record.get("observed_at", "Unknown"))

    who_limit = 15.0
    status    = "✅ Below WHO guideline" if pm25_pred <= who_limit else "⚠️  Above WHO guideline"

    print()
    print("=" * 55)
    print("  PREDICTION RESULT")
    print("=" * 55)
    print(f"  Station           : {station}")
    print(f"  Timestamp         : {timestamp}")
    print(f"  Predicted PM2.5   : {pm25_pred:.2f} µg/m³")
    print(f"  WHO 24-hr limit   : {who_limit} µg/m³")
    print(f"  Status            : {status}")
    print("=" * 55)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Beijing Air Quality — PM2.5 Prediction Script (Task 4)"
    )
    parser.add_argument(
        "--source", choices=["sql", "mongo"], default="mongo",
        help="API backend to fetch from (default: mongo)",
    )
    parser.add_argument(
        "--station", type=str, default=None,
        help="Station name (optional; fetches latest if omitted)",
    )
    parser.add_argument(
        "--timestamp", type=str, default=None,
        help="ISO timestamp e.g. '2015-06-10T14:00:00' (requires --station)",
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"Path to model .pkl file (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    print()
    print("Beijing Air Quality — Task 4 Prediction Script")
    print("=" * 55)
    print(f"  API backend : {args.source.upper()}")
    print(f"  Model file  : {args.model}")
    print("=" * 55)

    # Step 1
    if args.station and args.timestamp:
        record = fetch_by_timestamp_from_api(args.source, args.station, args.timestamp)
    else:
        record = fetch_latest_from_api(args.source)

    # Step 2
    features = preprocess(record)

    # Step 3
    model = load_model(args.model)

    # Step 4
    predict(model, features, record)


if __name__ == "__main__":
    main()