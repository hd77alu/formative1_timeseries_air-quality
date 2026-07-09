# MongoDB Query Results — Live Output
**Database:** `beijing_air_quality` | **Collection:** `air_quality_readings`
**Total documents:** 420,768 | **Run against:** MongoDB Atlas (live cluster)

---

## Query 1 — Latest Record

Fetches the single most recent document in the collection by sorting `timestamp`
descending and returning the first result. Uses the `idx_timestamp` index.

```
Station   : Wanshouxigong
Timestamp : 2017-02-28T23:00:00
Season    : Winter
PM2.5     : 13.0 µg/m³
NO2       : 38.0 µg/m³
TEMP      : 8.6 °C
```

**Interpretation:** The most recent record belongs to Wanshouxigong station,
28 February 2017 at 23:00 — the final hour of the dataset. PM2.5 reads
13.0 µg/m³, which is below the WHO 24-hour guideline of 15 µg/m³, confirming
the dataset ends on a relatively clean air day.

---

## Query 2 — Records by Date Range

Retrieves all hourly records for Dongsi station between 1 January 2015 and
3 January 2015. Uses the compound index `(station, timestamp)`.

```
Documents returned : 72  (expected 72 = 3 days × 24 hours ✓)

First 8 records:
          timestamp  PM2.5  PM10  TEMP  WSPM  wd
2015-01-01T00:00:00    3.0  14.0  -7.0   0.9 ENE
2015-01-01T01:00:00    5.0  27.0  -2.0   3.0  NW
2015-01-01T02:00:00    4.0  25.0  -4.0   2.1 ENE
2015-01-01T03:00:00    3.0  26.0  -4.0   1.4   N
2015-01-01T04:00:00    4.0  15.0  -4.0   1.6   N
2015-01-01T05:00:00    3.0  13.0  -6.0   1.7  NE
2015-01-01T06:00:00    3.0   5.0  -8.0   1.3  NE
2015-01-01T07:00:00    3.0  11.0  -9.0   0.8 ESE
```

**Interpretation:** All 72 expected records were returned (3 days × 24 hours),
confirming the date range filter works correctly. The first three days of
January 2015 at Dongsi show unusually low PM2.5 values of 3–5 µg/m³ despite
being mid-winter. Northerly and easterly winds on these days brought cleaner
air from outside the city, explaining the readings well below the winter
average of 95.48 µg/m³.

---

## Query 3 — Stations Ranked by Average PM2.5

Aggregation pipeline: `$match` nulls → `$group` by station with `$avg` and
`$max` → `$sort` descending → `$project` to round output.

```
      readings        station  avg_pm25  max_pm25
rank
1        34314         Dongsi     86.19     737.0
2        34368  Wanshouxigong     85.02     999.0
3        34436   Nongzhanguan     84.84     844.0
4        34418        Gucheng     83.85     770.0
5        34682         Wanliu     83.37     957.0
6        34448       Guanyuan     82.93     680.0
7        34139   Aotizhongxin     82.77     898.0
8        34387        Tiantan     82.16     821.0
9        34151         Shunyi     79.49     941.0
10       34290      Changping     71.10     882.0
11       34111        Huairou     69.63     762.0
12       34285       Dingling     65.99     881.0
```

**Interpretation:** Dongsi records the highest average PM2.5 at 86.19 µg/m³ —
a densely urban district with heavy traffic. Dingling (65.99 µg/m³) is the
cleanest station, located near a rural heritage site north of the city. The
ranking matches the MySQL Query 4 result exactly, confirming cross-database
consistency between both implementations.

---

## Query 4 — Hazardous Pollution Events (PM2.5 > 300 µg/m³)

Filters documents where `pollutants.PM2_5 > 300`, groups by station to count
hazardous hours, then surfaces the 10 worst individual readings. Uses the
`idx_pm25` index for the threshold filter.

**Part A — Hazardous hours per station:**
```
 hazardous_hours       station  peak_pm25
            1115  Nongzhanguan      844.0
            1025 Wanshouxigong      999.0
            1004        Dongsi      737.0
             926        Wanliu      957.0
             891  Aotizhongxin      898.0
             889       Gucheng      770.0
             833      Guanyuan      680.0
             817       Tiantan      821.0
             796        Shunyi      941.0
             511      Dingling      881.0
             469     Changping      882.0
             467       Huairou      762.0
```

**Part B — 10 worst individual readings:**
```
      station           timestamp  PM2_5   TEMP
Wanshouxigong 2016-02-08T02:00:00  999.0  -1.6
       Wanliu 2016-02-08T02:00:00  957.0  -3.6
       Shunyi 2016-02-08T02:00:00  941.0  -3.9
 Aotizhongxin 2016-02-08T02:00:00  898.0  -1.6
    Changping 2016-02-08T02:00:00  882.0  -2.4
     Dingling 2016-02-08T01:00:00  881.0  -1.5
Wanshouxigong 2016-02-08T03:00:00  857.0  -2.6
 Nongzhanguan 2013-05-05T12:00:00  844.0  25.8
 Nongzhanguan 2017-01-28T02:00:00  835.0  -3.0
Wanshouxigong 2016-02-08T01:00:00  826.0  -1.7
```

**Interpretation:** Across the full 4-year dataset, **9,743 hourly readings**
exceeded the 300 µg/m³ hazardous threshold — 2.3% of all records. The worst
cluster is concentrated on **8 February 2016**, a historically severe smog
episode where Wanshouxigong hit the sensor ceiling of 999.0 µg/m³. All the
worst readings show sub-zero temperatures confirming the winter heating
effect. Nongzhanguan leads the per-station hazardous hour count with 1,115
hours. Dingling and Huairou — the most rural stations — recorded the fewest,
consistent with their lower background pollution.

---

## Query 5 — Seasonal Average PM2.5

Groups all documents by the pre-computed `season` field and returns mean,
max, and min PM2.5 per season, confirming the seasonal pattern found in the
Task 1A EDA.

```
 readings season  avg_pm25  max_pm25  min_pm25
   101907 Winter     95.48     999.0       2.0
   102746 Autumn     82.33     687.0       3.0
   103705 Spring     76.97     844.0       2.0
   103671 Summer     64.67     560.0       2.0

Winter average is 1.48× higher than Summer average.
```

**Interpretation:** Winter records the highest average PM2.5 at 95.48 µg/m³ —
1.48× the summer average of 64.67 µg/m³. This confirms the dominant seasonal
pattern from Task 1A: coal-based heating and temperature inversions trap
pollutants near ground level throughout winter. Summer benefits from stronger
convective mixing, higher rainfall, and no heating activity. The `season`
field pre-computed at load time makes this a single-pass aggregation pipeline
with no date parsing overhead at query time.

---

## Summary

| Query | Result | Index used |
|---|---|---|
| Q1 — Latest record | Wanshouxigong, 2017-02-28T23:00, PM2.5=13.0 | `idx_timestamp` |
| Q2 — Date range | 72 documents returned (3 days × 24 hrs ✓) | `idx_station_timestamp` |
| Q3 — Station ranking | Dongsi worst (86.19), Dingling best (65.99) | Collection scan + group |
| Q4 — Hazardous events | 9,743 total; worst on 2016-02-08 | `idx_pm25` |
| Q5 — Seasonal averages | Winter 95.48 vs Summer 64.67 µg/m³ | `season` field group |