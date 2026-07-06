# Usage Guide

## Setup Instructions

1. Run `schema.sql` to create the database and tables.
2. Run `python etl_load.py` to load the CSV files into `staging_air_quality_raw` and populate the normalized tables.
3. Run `queries.sql` to confirm row counts, duplicates, and summary values.

## Environment Setup

The ETL loader reads credentials from a local `.env` file first, so you do not need to type connection values every time.

Create a file named `.env` in the project root or in `mysql_database/` with these values:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password_here
MYSQL_DATABASE=beijing_air_quality
```

You can also set the same variables manually in your terminal if you prefer. The `.env` file is ignored by git, so it is safe for local credentials.

## Loading the CSV Files

The recommended option is the Python loader in `etl_load.py`. It reads all 12 CSV files, writes them into `staging_air_quality_raw`, and then applies the normalization script using the `.env` settings.

If you prefer a manual import path, each CSV already has the correct columns except for `source_file` and `source_row_no`, which are staging-only metadata fields.

Use one `LOAD DATA LOCAL INFILE` statement per CSV file. Example:

```sql
LOAD DATA LOCAL INFILE 'C:/path/to/PRSA_Data_Aotizhongxin_20130301-20170228.csv'
INTO TABLE staging_air_quality_raw
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(no, year, month, day, hour, pm25, pm10, so2, no2, co, o3, temp, pres, dewp, rain, wd, wspm, station_name)
SET
  source_file = 'PRSA_Data_Aotizhongxin_20130301-20170228.csv';

UPDATE staging_air_quality_raw
SET source_row_no = no
WHERE source_file = 'PRSA_Data_Aotizhongxin_20130301-20170228.csv';
```

If you prefer, you can also import the CSVs through MySQL Workbench or a Python ETL script, as long as the rows end up in `staging_air_quality_raw` with the same column names.

## Querying the Database

The main read model is `v_hourly_air_quality`:

```sql
SELECT *
FROM v_hourly_air_quality
WHERE station_name = 'Aotizhongxin'
  AND observed_at BETWEEN '2016-01-01' AND '2016-12-31';
```
