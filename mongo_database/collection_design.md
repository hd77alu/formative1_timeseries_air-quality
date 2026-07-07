# MongoDB Collection Design — Beijing Air Quality

## Database
`beijing_air_quality`

---

## Collection

### `air_quality_readings` (420,768 documents)

A single collection where each document represents one hourly observation at one station.
All pollutant and meteorological measurements are embedded as nested sub-documents.

**Why a single collection?**
The dominant read pattern is "give me all measurements for a given station-hour" — pollutants
and weather are always consumed together. Splitting them into separate collections (as the SQL
schema does with `air_quality_readings` and `weather_readings`) would require client-side
joins that MongoDB is not optimised for. One document = one complete reading.

---

## Document Schema

```json
{
  "_id":       "<station>_<ISO-timestamp>",
  "station":   "string",
  "timestamp": "YYYY-MM-DDTHH:MM:SS",
  "year":      "int",
  "month":     "int",
  "day":       "int",
  "hour":      "int",
  "season":    "Spring | Summer | Autumn | Winter",
  "pollutants": {
    "PM2_5": "float | null",
    "PM10":  "float | null",
    "SO2":   "float | null",
    "NO2":   "float | null",
    "CO":    "float | null",
    "O3":    "float | null"
  },
  "weather": {
    "TEMP": "float | null",
    "PRES": "float | null",
    "DEWP": "float | null",
    "RAIN": "float | null",
    "wd":   "string | null",
    "WSPM": "float | null"
  }
}
```

**Key design decisions:**

| Decision | Reason |
|---|---|
| Deterministic `_id` (`station_timestamp`) | Re-running `load_data.py` skips duplicates silently — no accidental double inserts |
| `PM2.5` renamed to `PM2_5` | MongoDB field names cannot contain `.` |
| `timestamp` as ISO string | Enables lexicographic range queries (`$gte`/`$lte`) without datetime conversion overhead |
| `season` pre-computed at insert time | Avoids recomputing in every seasonal aggregation query |
| Missing values stored as `null` | Preserves original missingness; distinguishes a zero reading from an absent one |
| `pollutants` and `weather` as sub-documents | Mirrors the SQL two-table split; each domain is queryable independently |

---

## Indexes

| Name | Fields | Type | Purpose |
|---|---|---|---|
| `idx_station_timestamp` | `(station, timestamp)` | Unique compound | Covers all per-station and date-range queries; enforces uniqueness |
| `idx_timestamp` | `timestamp` | Single-field | Covers global latest-record and cross-station time queries |
| `idx_pm25` | `pollutants.PM2_5` | Single-field | Covers PM2.5 threshold and ranking queries |

---

## Sample Documents

### Clean low-pollution reading (Spring, peri-urban station)
```json
{
  "_id":       "Aotizhongxin_2013-03-01T00:00:00",
  "station":   "Aotizhongxin",
  "timestamp": "2013-03-01T00:00:00",
  "year": 2013, "month": 3, "day": 1, "hour": 0,
  "season":    "Spring",
  "pollutants": { "PM2_5": 4.0,  "PM10": 4.0,  "SO2": 4.0,
                  "NO2": 7.0,    "CO": 300.0,   "O3": 77.0 },
  "weather":   { "TEMP": -0.7,   "PRES": 1023.0, "DEWP": -18.8,
                 "RAIN": 0.0,    "wd": "NNW",    "WSPM": 4.4 }
}
```

### Hazardous winter reading (coal-heating season, central urban station)
```json
{
  "_id":       "Wanshouxigong_2016-02-08T02:00:00",
  "station":   "Wanshouxigong",
  "timestamp": "2016-02-08T02:00:00",
  "year": 2016, "month": 2, "day": 8, "hour": 2,
  "season":    "Winter",
  "pollutants": { "PM2_5": 387.0, "PM10": 416.0, "SO2": 62.0,
                  "NO2": 118.0,   "CO": 4200.0,   "O3": 3.0 },
  "weather":   { "TEMP": -6.0,   "PRES": 1030.2, "DEWP": -18.5,
                 "RAIN": 0.0,    "wd": "N",      "WSPM": 0.6 }
}
```

### Summer reading with elevated O3 (photochemical smog)
```json
{
  "_id":       "Huairou_2015-07-20T14:00:00",
  "station":   "Huairou",
  "timestamp": "2015-07-20T14:00:00",
  "year": 2015, "month": 7, "day": 20, "hour": 14,
  "season":    "Summer",
  "pollutants": { "PM2_5": 28.0, "PM10": 45.0, "SO2": 4.0,
                  "NO2": 21.0,   "CO": 500.0,   "O3": 112.0 },
  "weather":   { "TEMP": 31.5,  "PRES": 998.0, "DEWP": 22.0,
                 "RAIN": 0.0,   "wd": "SE",    "WSPM": 3.4 }
}
```

### Document with null (missing sensor reading)
```json
{
  "_id":       "Gucheng_2014-05-11T03:00:00",
  "station":   "Gucheng",
  "timestamp": "2014-05-11T03:00:00",
  "year": 2014, "month": 5, "day": 11, "hour": 3,
  "season":    "Spring",
  "pollutants": { "PM2_5": null, "PM10": null, "SO2": 8.0,
                  "NO2": 34.0,  "CO": 700.0,  "O3": 55.0 },
  "weather":   { "TEMP": 18.2,  "PRES": 1008.4, "DEWP": 5.1,
                 "RAIN": 0.0,   "wd": "SW",     "WSPM": 1.8 }
}
```

---

## SQL vs MongoDB Mapping

| SQL (`mysql_database/`) | MongoDB (`mongo_database/`) |
|---|---|
| `stations` table | Station name embedded as a field in every document |
| `observations` table | `timestamp`, `year`, `month`, `day`, `hour` fields in document |
| `air_quality_readings` table | `pollutants` sub-document |
| `weather_readings` table | `weather` sub-document |
| `v_hourly_air_quality` view | Not needed — document already contains all fields |
| 3-way JOIN for a full reading | None — single document lookup |
