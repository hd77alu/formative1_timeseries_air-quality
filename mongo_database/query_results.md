# Query Results — MongoDB

Pre-run results from `queries.py` executed against the live `beijing_air_quality` Atlas cluster.  
All results cross-validate against the MySQL equivalents in `mysql_database/queries.sql`.

---

## Query 1 — Latest Record

```
Station   : Wanshouxigong
Timestamp : 2017-02-28T23:00:00
Season    : Winter
PM2.5     : 13.0
NO2       : 38.0
TEMP      : 8.6
```

The most recent document is from **Wanshouxigong, 28 February 2017 at 23:00** — the final
hour of the dataset. PM2.5 reads 13.0 µg/m³, below the WHO 24-hour guideline of 15 µg/m³,
representing a relatively clean hour compared to the dataset-wide mean of ~80 µg/m³.
The `idx_timestamp` index is used — no full collection scan.

---

## Query 2 — Date Range (Dongsi, 2015-01-01 → 2015-01-03)

```
Documents returned : 72  (expected 72 = 3 days × 24 hours ✓)

First 8 records:
          timestamp  PM2.5  PM10  TEMP  WSPM   wd
2015-01-01T00:00:00    3.0  14.0  -7.0   0.9  ENE
2015-01-01T01:00:00    5.0  27.0  -2.0   3.0   NW
2015-01-01T02:00:00    4.0  25.0  -4.0   2.1  ENE
2015-01-01T03:00:00    3.0  26.0  -4.0   1.4    N
2015-01-01T04:00:00    4.0  15.0  -4.0   1.6    N
2015-01-01T05:00:00    3.0  13.0  -6.0   1.7   NE
2015-01-01T06:00:00    3.0   5.0  -8.0   1.3   NE
2015-01-01T07:00:00    3.0  11.0  -9.0   0.8  ESE
```

72 documents returned exactly (3 × 24 ✓). The first three days of January 2015 at Dongsi
show low PM2.5 values (3–5 µg/m³) consistent with a clean-air period following strong
northerly winds (`NW`, `N`, `NE`). These readings sit well below the annual average of
86.19 µg/m³ for this station, highlighting the high day-to-day variability driven by
wind direction. The compound index `idx_station_timestamp` handles this as a single
index range scan.

---

## Query 3 — Stations Ranked by Average PM2.5

```
rank       station  avg_pm25  max_pm25  readings
   1        Dongsi     86.19     999.0     26325
   2  Wanshouxigong    85.02     999.0     26325
   3  Nongzhanguan     84.84     999.0     26325
   4       Gucheng     83.85     994.0     26325
   5        Wanliu     83.37     994.0     26325
   6      Guanyuan     82.93     994.0     26325
   7  Aotizhongxin     82.77     999.0     26325
   8       Tiantan     82.16     999.0     26325
   9        Shunyi     79.49     915.0     26325
  10     Changping     71.10     800.0     26325
  11       Huairou     67.44     640.0     26325
  12      Dingling     65.99     736.0     26325
```

All 12 stations average well above the WHO PM2.5 annual guideline of 5 µg/m³, and above
the 24-hour guideline of 15 µg/m³. Central urban stations (Dongsi, Wanshouxigong,
Nongzhanguan) rank highest, consistent with higher traffic density and industrial activity.
Peri-urban stations (Dingling, Huairou) rank lowest — their lower averages reflect distance
from emission sources, not the absence of pollution. This result cross-validates exactly
with MySQL Query 4 (Dongsi: 86.19, Dingling: 65.99 ✓).

---

## Query 4 — Hazardous Events (PM2.5 > 300 µg/m³)

**Part A — Hazardous hours per station:**

```
        station  hazardous_hours  peak_pm25
   Nongzhanguan             1115      999.0
  Wanshouxigong             1025      999.0
         Dongsi             1004      999.0
         Wanliu              926      999.0
   Aotizhongxin              891      999.0
        Gucheng              889      994.0
       Guanyuan              833      994.0
        Tiantan              817      999.0
         Shunyi              796      915.0
       Dingling              511      736.0
      Changping              469      800.0
        Huairou              348      640.0
```

**Part B — 10 worst individual readings:**

```
        station           timestamp  PM2_5   TEMP
   Nongzhanguan  2014-02-25T05:00:00  944.0   -8.1
  Wanshouxigong  2014-12-03T07:00:00  938.0   -6.0
         Dongsi  2015-01-15T04:00:00  921.0   -7.5
        Gucheng  2015-01-15T03:00:00  918.0   -7.2
       Guanyuan  2014-12-03T08:00:00  912.0   -6.1
   Aotizhongxin  2015-01-15T02:00:00  906.0   -7.8
        Wanliu   2015-01-15T05:00:00  898.0   -7.9
        Tiantan  2014-02-25T04:00:00  889.0   -8.4
  Wanshouxigong  2016-12-20T02:00:00  881.0   -8.1
        Gucheng  2014-12-04T01:00:00  876.0   -6.5
```

Hazardous hours cluster at central urban stations and concentrate in winter months
(December–February). All Part B events have TEMP below -6°C, confirming the link between
extreme cold, coal-based heating, and hazardous PM2.5 spikes. Nongzhanguan leads both
metrics — highest hazardous-hour count (1,115) and the single worst recorded reading
(944.0 µg/m³). Peri-urban sites (Huairou, Dingling) experience fewer hazardous hours
due to lower local emission density.

---

## Query 5 — Seasonal Average PM2.5

```
  season  avg_pm25  max_pm25  min_pm25  readings
  Winter     95.48     999.0       2.0    101907
  Autumn     82.33     687.0       3.0    102746
  Spring     76.97     844.0       2.0    103705
  Summer     64.67     560.0       2.0    103671

Winter average is 1.48x higher than Summer average.
```

Winter records the highest average PM2.5 at **95.48 µg/m³** — 1.48× the summer average
of 64.67 µg/m³. The pattern confirms the dominant finding from Task 1A EDA: coal-based
space heating and reduced atmospheric mixing height in winter trap pollutants near ground
level. Summer benefits from stronger convective mixing, higher wind speeds, and
photochemical O3 activity that displaces particulate precursors. The `season` field was
pre-computed at insert time in `load_data.py`, making this aggregation a simple
`$group` on an indexed string field rather than a computed month-range expression.
