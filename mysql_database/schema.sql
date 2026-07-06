-- Beijing Multi-Site Air Quality Database
-- MySQL 8+ schema for staging, normalization, and reporting.

CREATE DATABASE IF NOT EXISTS beijing_air_quality
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE beijing_air_quality;

DROP VIEW IF EXISTS v_hourly_air_quality;
DROP TABLE IF EXISTS weather_readings;
DROP TABLE IF EXISTS air_quality_readings;
DROP TABLE IF EXISTS observations;
DROP TABLE IF EXISTS stations;
DROP TABLE IF EXISTS staging_air_quality_raw;

CREATE TABLE staging_air_quality_raw (
    staging_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_file VARCHAR(255) NOT NULL,
    source_row_no INT NULL,
    no INT NULL,
    year SMALLINT NOT NULL,
    month TINYINT NOT NULL,
    day TINYINT NOT NULL,
    hour TINYINT NOT NULL,
    pm25 DECIMAL(8,2) NULL,
    pm10 DECIMAL(8,2) NULL,
    so2 DECIMAL(8,2) NULL,
    no2 DECIMAL(8,2) NULL,
    co DECIMAL(10,2) NULL,
    o3 DECIMAL(8,2) NULL,
    temp DECIMAL(6,2) NULL,
    pres DECIMAL(8,2) NULL,
    dewp DECIMAL(6,2) NULL,
    rain DECIMAL(6,2) NULL,
    wd VARCHAR(8) NULL,
    wspm DECIMAL(6,2) NULL,
    station_name VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_stage_station_time (station_name, year, month, day, hour)
) ENGINE=InnoDB;

CREATE TABLE stations (
    station_id INT AUTO_INCREMENT PRIMARY KEY,
    station_name VARCHAR(50) NOT NULL,
    city VARCHAR(50) NOT NULL DEFAULT 'Beijing',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_station_name (station_name)
) ENGINE=InnoDB;

CREATE TABLE observations (
    observation_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    station_id INT NOT NULL,
    observed_at DATETIME NOT NULL,
    source_row_no INT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_observations_station
        FOREIGN KEY (station_id) REFERENCES stations(station_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE KEY uq_station_time (station_id, observed_at),
    KEY idx_observed_at (observed_at)
) ENGINE=InnoDB;

CREATE TABLE air_quality_readings (
    observation_id BIGINT PRIMARY KEY,
    pm25 DECIMAL(8,2) NULL,
    pm10 DECIMAL(8,2) NULL,
    so2 DECIMAL(8,2) NULL,
    no2 DECIMAL(8,2) NULL,
    co DECIMAL(10,2) NULL,
    o3 DECIMAL(8,2) NULL,
    CONSTRAINT fk_air_quality_observation
        FOREIGN KEY (observation_id) REFERENCES observations(observation_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    KEY idx_pm25 (pm25),
    KEY idx_pm10 (pm10)
) ENGINE=InnoDB;

CREATE TABLE weather_readings (
    observation_id BIGINT PRIMARY KEY,
    temp DECIMAL(6,2) NULL,
    pres DECIMAL(8,2) NULL,
    dewp DECIMAL(6,2) NULL,
    rain DECIMAL(6,2) NULL,
    wd VARCHAR(8) NULL,
    wspm DECIMAL(6,2) NULL,
    CONSTRAINT fk_weather_observation
        FOREIGN KEY (observation_id) REFERENCES observations(observation_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    KEY idx_wd (wd),
    KEY idx_wspm (wspm)
) ENGINE=InnoDB;

CREATE OR REPLACE VIEW v_hourly_air_quality AS
SELECT
    o.observation_id,
    s.station_id,
    s.station_name,
    o.observed_at,
    o.source_row_no,
    aq.pm25,
    aq.pm10,
    aq.so2,
    aq.no2,
    aq.co,
    aq.o3,
    w.temp,
    w.pres,
    w.dewp,
    w.rain,
    w.wd,
    w.wspm
FROM observations o
JOIN stations s ON s.station_id = o.station_id
JOIN air_quality_readings aq ON aq.observation_id = o.observation_id
JOIN weather_readings w ON w.observation_id = o.observation_id;
