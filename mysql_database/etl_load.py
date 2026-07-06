"""Load the Beijing air-quality CSV files into MySQL.

Expected flow:
1. Run schema.sql to create the database and tables.
2. Set MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE.
3. Run this script to load the 12 CSV files into staging_air_quality_raw.
4. Execute load_from_staging.sql to normalize the data.

This script uses mysql-connector-python and only standard-library CSV parsing.
"""

from __future__ import annotations

import argparse
import csv
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

import mysql.connector


CSV_COLUMNS = [
    "no",
    "year",
    "month",
    "day",
    "hour",
    "pm25",
    "pm10",
    "so2",
    "no2",
    "co",
    "o3",
    "temp",
    "pres",
    "dewp",
    "rain",
    "wd",
    "wspm",
    "station_name",
]


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


def parse_int(value: str | None) -> int | None:
    if value in (None, "", "NA", "NaN"):
        return None
    return int(value)


def parse_decimal(value: str | None) -> Decimal | None:
    if value in (None, "", "NA", "NaN"):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def parse_text(value: str | None) -> str | None:
    if value in (None, "", "NA", "NaN"):
        return None
    return value


def iter_staging_rows(data_dir: Path) -> Iterable[tuple]:
    for csv_path in sorted(data_dir.glob("PRSA_Data_*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                yield (
                    csv_path.name,
                    row_number,
                    parse_int(row["No"]),
                    parse_int(row["year"]),
                    parse_int(row["month"]),
                    parse_int(row["day"]),
                    parse_int(row["hour"]),
                    parse_decimal(row["PM2.5"]),
                    parse_decimal(row["PM10"]),
                    parse_decimal(row["SO2"]),
                    parse_decimal(row["NO2"]),
                    parse_decimal(row["CO"]),
                    parse_decimal(row["O3"]),
                    parse_decimal(row["TEMP"]),
                    parse_decimal(row["PRES"]),
                    parse_decimal(row["DEWP"]),
                    parse_decimal(row["RAIN"]),
                    parse_text(row["wd"]),
                    parse_decimal(row["WSPM"]),
                    parse_text(row["station"]),
                )


def connect_mysql() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "beijing_air_quality"),
        autocommit=False,
    )


def load_staging_rows(connection: mysql.connector.MySQLConnection, data_dir: Path, chunk_size: int) -> int:
    insert_sql = """
        INSERT INTO staging_air_quality_raw (
            source_file,
            source_row_no,
            no,
            year,
            month,
            day,
            hour,
            pm25,
            pm10,
            so2,
            no2,
            co,
            o3,
            temp,
            pres,
            dewp,
            rain,
            wd,
            wspm,
            station_name
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """
    cursor = connection.cursor()
    buffered_rows = []
    total_rows = 0

    for staging_row in iter_staging_rows(data_dir):
        buffered_rows.append(staging_row)
        if len(buffered_rows) >= chunk_size:
            cursor.executemany(insert_sql, buffered_rows)
            total_rows += len(buffered_rows)
            connection.commit()
            buffered_rows.clear()

    if buffered_rows:
        cursor.executemany(insert_sql, buffered_rows)
        total_rows += len(buffered_rows)
        connection.commit()

    cursor.close()
    return total_rows


def run_sql_script(connection: mysql.connector.MySQLConnection, sql_path: Path) -> None:
    cursor = connection.cursor()
    script_text = sql_path.read_text(encoding="utf-8")
    statements = [statement.strip() for statement in script_text.split(";") if statement.strip()]
    for statement in statements:
        cursor.execute(statement)
    connection.commit()
    cursor.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Load Beijing air-quality CSVs into MySQL.")
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
        help="Number of rows to insert per batch.",
    )
    parser.add_argument(
        "--load-script",
        type=Path,
        default=Path(__file__).resolve().parent / "load_from_staging.sql",
        help="Path to the normalization SQL script.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    load_dotenv_file(project_root / ".env")
    load_dotenv_file(Path(__file__).resolve().parent / ".env")

    if not args.data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {args.data_dir}")

    connection = connect_mysql()
    try:
        print(f"Loading staging rows from: {args.data_dir}")
        total_rows = load_staging_rows(connection, args.data_dir, args.chunk_size)
        print(f"Inserted {total_rows} staging rows.")

        print(f"Running normalization script: {args.load_script}")
        run_sql_script(connection, args.load_script)
        print("Normalization complete.")
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
