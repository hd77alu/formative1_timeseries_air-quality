-- Load normalized tables from staging_air_quality_raw.
-- Assumes raw CSV rows have already been imported into staging_air_quality_raw.

USE beijing_air_quality;

INSERT IGNORE INTO stations (station_name)
SELECT DISTINCT station_name
FROM staging_air_quality_raw;

INSERT IGNORE INTO observations (station_id, observed_at, source_row_no)
SELECT
    s.station_id,
    STR_TO_DATE(
        CONCAT(r.year, '-', LPAD(r.month, 2, '0'), '-', LPAD(r.day, 2, '0'), ' ', LPAD(r.hour, 2, '0'), ':00:00'),
        '%Y-%m-%d %H:%i:%s'
    ) AS observed_at,
    r.source_row_no
FROM staging_air_quality_raw r
JOIN stations s
    ON s.station_name = r.station_name;

INSERT INTO air_quality_readings (
    observation_id,
    pm25,
    pm10,
    so2,
    no2,
    co,
    o3
)
SELECT
    o.observation_id,
    r.pm25,
    r.pm10,
    r.so2,
    r.no2,
    r.co,
    r.o3
FROM staging_air_quality_raw r
JOIN stations s
    ON s.station_name = r.station_name
JOIN observations o
    ON o.station_id = s.station_id
   AND o.observed_at = STR_TO_DATE(
        CONCAT(r.year, '-', LPAD(r.month, 2, '0'), '-', LPAD(r.day, 2, '0'), ' ', LPAD(r.hour, 2, '0'), ':00:00'),
        '%Y-%m-%d %H:%i:%s'
    )
ON DUPLICATE KEY UPDATE
    pm25 = VALUES(pm25),
    pm10 = VALUES(pm10),
    so2 = VALUES(so2),
    no2 = VALUES(no2),
    co = VALUES(co),
    o3 = VALUES(o3);

INSERT INTO weather_readings (
    observation_id,
    temp,
    pres,
    dewp,
    rain,
    wd,
    wspm
)
SELECT
    o.observation_id,
    r.temp,
    r.pres,
    r.dewp,
    r.rain,
    r.wd,
    r.wspm
FROM staging_air_quality_raw r
JOIN stations s
    ON s.station_name = r.station_name
JOIN observations o
    ON o.station_id = s.station_id
   AND o.observed_at = STR_TO_DATE(
        CONCAT(r.year, '-', LPAD(r.month, 2, '0'), '-', LPAD(r.day, 2, '0'), ' ', LPAD(r.hour, 2, '0'), ':00:00'),
        '%Y-%m-%d %H:%i:%s'
    )
ON DUPLICATE KEY UPDATE
    temp = VALUES(temp),
    pres = VALUES(pres),
    dewp = VALUES(dewp),
    rain = VALUES(rain),
    wd = VALUES(wd),
    wspm = VALUES(wspm);
