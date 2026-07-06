# Beijing Air Quality Database ERD

```mermaid
erDiagram
    STATIONS ||--o{ OBSERVATIONS : has
    OBSERVATIONS ||--|| AIR_QUALITY_READINGS : contains
    OBSERVATIONS ||--|| WEATHER_READINGS : contains

    STATIONS {
        int station_id PK
        varchar station_name UK
        varchar city
        boolean is_active
        timestamp created_at
    }

    OBSERVATIONS {
        bigint observation_id PK
        int station_id FK
        datetime observed_at
        int source_row_no
        timestamp created_at
    }

    AIR_QUALITY_READINGS {
        bigint observation_id PK, FK
        decimal pm25
        decimal pm10
        decimal so2
        decimal no2
        decimal co
        decimal o3
    }

    WEATHER_READINGS {
        bigint observation_id PK, FK
        decimal temp
        decimal pres
        decimal dewp
        decimal rain
        varchar wd
        decimal wspm
    }
```

## Design Notes

- `stations` stores the 12 monitoring sites once.
- `observations` stores one hourly timestamp per station.
- `air_quality_readings` stores pollutant measurements.
- `weather_readings` stores meteorological measurements.
- `v_hourly_air_quality` in the schema joins everything back into a single API-friendly hourly record.

## Why This Design

- It avoids repeating station metadata across millions of rows.
- It enforces one reading per station per hour.
- It keeps pollutant and weather data separated but still directly joinable.
- It supports both analytical SQL and later REST API endpoints cleanly.
