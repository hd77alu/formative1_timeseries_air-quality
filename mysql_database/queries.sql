USE beijing_air_quality;

-- Query 1: row counts and station coverage
SELECT
    (SELECT COUNT(*) FROM stations) AS station_count,
    (SELECT COUNT(*) FROM observations) AS observation_count,
    (SELECT COUNT(*) FROM air_quality_readings) AS air_quality_row_count,
    (SELECT COUNT(*) FROM weather_readings) AS weather_row_count;
/*
Results:
station_count	12
observation_count	420768
air_quality_row_count	420768
weather_row_count	420768
*/
-- Query 2: duplicate check on the natural key
SELECT
    station_id,
    observed_at,
    COUNT(*) AS row_count
FROM observations
GROUP BY station_id, observed_at
HAVING COUNT(*) > 1;
/*
Results:
0
*/
-- Query 3: missing value summary after load
SELECT
    SUM(pm25 IS NULL) AS missing_pm25,
    SUM(pm10 IS NULL) AS missing_pm10,
    SUM(so2 IS NULL) AS missing_so2,
    SUM(no2 IS NULL) AS missing_no2,
    SUM(co IS NULL) AS missing_co,
    SUM(o3 IS NULL) AS missing_o3
FROM air_quality_readings;
/*
Results:
missing_pm25	8739
missing_pm10	6449
missing_so2	9021
missing_no2	12116
missing_co	20701
missing_o3	13277
*/
SELECT
    SUM(temp IS NULL) AS missing_temp,
    SUM(pres IS NULL) AS missing_pres,
    SUM(dewp IS NULL) AS missing_dewp,
    SUM(rain IS NULL) AS missing_rain,
    SUM(wd IS NULL) AS missing_wd,
    SUM(wspm IS NULL) AS missing_wspm
FROM weather_readings;
/*
Results:
missing_temp	398
missing_pres	393
missing_dewp	403
missing_rain	390
missing_wd	1822
missing_wspm	318
*/
-- Query 4: top 5 stations by average PM2.5
SELECT
    s.station_name,
    ROUND(AVG(aq.pm25), 2) AS avg_pm25
FROM observations o
JOIN stations s ON s.station_id = o.station_id
JOIN air_quality_readings aq ON aq.observation_id = o.observation_id
GROUP BY s.station_name
ORDER BY avg_pm25 DESC
LIMIT 5;
/*
Results:
station_name	Dongsi
avg_pm25	86.19
station_name	Wanshouxigong
avg_pm25	85.02
station_name	Nongzhanguan
avg_pm25	84.84
station_name	Gucheng
avg_pm25	83.85
tation_name	Wanliu
avg_pm25	83.37
*/
-- Query 5: monthly PM2.5 trend sample
SELECT
    DATE_FORMAT(o.observed_at, '%Y-%m') AS month_bucket,
    ROUND(AVG(aq.pm25), 2) AS avg_pm25
FROM observations o
JOIN air_quality_readings aq ON aq.observation_id = o.observation_id
GROUP BY DATE_FORMAT(o.observed_at, '%Y-%m')
ORDER BY month_bucket
LIMIT 5;
/*
Results:
month_bucket	2013-03
avg_pm25	104.89
month_bucket	2013-04
avg_pm25	62.14
month_bucket	2013-05
avg_pm25	81.85
month_bucket	2013-06
avg_pm25	102.44
month_bucket	2013-07
avg_pm25	67.91
*/
-- Query 6: most common wind directions
SELECT
    wd,
    COUNT(*) AS frequency
FROM weather_readings
WHERE wd IS NOT NULL
GROUP BY wd
ORDER BY frequency DESC
LIMIT 5;
/*
Results:
wd	NE
frequency	43335
wd	ENE
frequency	34142
wd	NW
frequency	32600
wd	N
frequency	30869
wd	E
frequency	29752
*/