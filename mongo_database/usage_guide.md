# Usage Guide — MongoDB

## Setup Instructions

1. Create a free M0 cluster on [MongoDB Atlas](https://cloud.mongodb.com) and copy your connection string.
2. Set `MONGO_URI` in your environment or in a `.env` file at the project root.
3. Run `load_data.py` to load all 12 CSV files into the `air_quality_readings` collection.
4. Run `queries.py` to reproduce all five analytical queries.

---

## Environment Setup

The loader and query scripts read credentials from a local `.env` file first, so you do not
need to export the variable every time you open a terminal.

Create a file named `.env` in the project root with this value:

```env
MONGO_URI=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/
```

Replace `<user>` and `<password>` with the database user credentials you created in Atlas.
The `.env` file is listed in `.gitignore` — it is safe for local credentials and will never
be committed to the repository.

You can also set the variable manually in your terminal if you prefer:

```bash
# macOS / Linux / WSL
export MONGO_URI="mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/"

# Windows (PowerShell)
$env:MONGO_URI="mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/"
```

---

## Loading the CSV Files

Run from the repo root (not from inside `mongo_database/`):

```bash
pip install pymongo[srv] pandas
python mongo_database/load_data.py
```

Expected output:

```
Connected to MongoDB Atlas — database: beijing_air_quality

CSV files found: 12
  Loaded: PRSA_Data_Aotizhongxin_20130301-20170228.csv
  Loaded: PRSA_Data_Changping_20130301-20170228.csv
  Loaded: PRSA_Data_Dingling_20130301-20170228.csv
  Loaded: PRSA_Data_Dongsi_20130301-20170228.csv
  Loaded: PRSA_Data_Guanyuan_20130301-20170228.csv
  Loaded: PRSA_Data_Gucheng_20130301-20170228.csv
  Loaded: PRSA_Data_Huairou_20130301-20170228.csv
  Loaded: PRSA_Data_Nongzhanguan_20130301-20170228.csv
  Loaded: PRSA_Data_Shunyi_20130301-20170228.csv
  Loaded: PRSA_Data_Tiantan_20130301-20170228.csv
  Loaded: PRSA_Data_Wanliu_20130301-20170228.csv
  Loaded: PRSA_Data_Wanshouxigong_20130301-20170228.csv
Combined shape : (420768, 18)

Indexes created:
  _id_
  idx_station_timestamp
  idx_timestamp
  idx_pm25

Inserted : 420,768
Skipped  : 0
Total    : 420,768

Verification — documents in collection: 420,768
Load complete.
```

420,768 = 12 stations × 35,064 hourly readings each (1 March 2013 → 28 February 2017).

Re-running the script is safe — the deterministic `_id` format (`station_timestamp`) causes
duplicate documents to be skipped silently, so `Inserted` will show 0 and `Skipped` will
show 420,768 on subsequent runs.

---

## Running the Queries

```bash
python mongo_database/queries.py
```

Pre-run results for all five queries are documented in `query_results.md`.

---

## Files in this folder

| File | Purpose |
|---|---|
| `collection_design.md` | Schema definition, sample documents, design rationale, SQL mapping |
| `load_data.py` | ETL script — loads all 12 CSVs into MongoDB Atlas |
| `queries.py` | Five analytical queries with printed results |
| `query_results.md` | Pre-run results with interpretation for all five queries |
| `usage_guide.md` | This file |

---

## Collection created

| Collection | Documents | Description |
|---|---|---|
| `air_quality_readings` | 420,768 | One document per hourly observation per station |
