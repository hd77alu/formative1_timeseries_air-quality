# Beijing Multi-Site Air Quality — Time-Series Pipeline

**Group 5 | African Leadership University | Formative Assignment 1**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hd77alu/formative1_timeseries_air-quality/blob/main/Group_5_Formative_1_TimeSeries.ipynb)

---

## Project Overview

This project builds an end-to-end time-series machine learning pipeline for hourly PM2.5
forecasting using the Beijing Multi-Site Air Quality dataset (2013–2017). The pipeline
covers exploratory data analysis, feature engineering, model training, relational and
non-relational database design, a unified REST API, and a consolidated prediction script.

**Prediction target:** PM2.5 concentration (µg/m³) — fine particulate matter, the primary
indicator of harmful air pollution with direct public health implications.

**Best model:** Random Forest with log-transformed target — Test MAE: 9.03 µg/m³, R²: 0.9534

---

## Dataset

| Detail | Value |
|---|---|
| Name | Beijing Multi-Site Air-Quality Data Set |
| Source | [Kaggle](https://www.kaggle.com/datasets/sid321axn/beijing-multisite-airquality-data-set) |
| Coverage | 1 March 2013 → 28 February 2017 (1,461 days, hourly) |
| Stations | 12 monitoring sites across Beijing |
| Size | 420,768 rows × 18 columns |

> The dataset is committed to this repository but if it's inaccsessible due to size constraints.
> Download instructions are in the [Data Setup](#data-setup) section below.

---

## Repository Structure

```
formative1_timeseries_air-quality/
│
├── Group_5_Formative_1_TimeSeries.ipynb   # Main notebook: Tasks 1A, 1B, 1C
├── app.py                                  # FastAPI gateway — Task 3
├── predict.py                              # End-to-end prediction script — Task 4
│
├── beijing_air_quality_data/               # Raw CSVs (downloaded separately)
│   ├── PRSA_Data_Aotizhongxin_20130301-20170228.csv
│   └── ... (12 files total)
│
├── mysql_database/                         # Task 2A — Relational database
│   ├── schema.sql                          # CREATE TABLE statements (4 tables + view)
│   ├── etl_load.py                         # Python ETL — loads CSVs into MySQL
│   ├── load_from_staging.sql               # Normalisation script
│   ├── queries.sql                         # 6 analytical queries with results
│   ├── erd.md                              # ERD (Mermaid source)
│   ├── mysql-erd.png                       # ERD rendered as PNG
│   └── usage_guide.md                      # Step-by-step setup instructions
│
├── mongo_database/                         # Task 2B — Non-relational database
│   ├── collection_design.md                # Schema, sample documents, design rationale
│   ├── load_data.py                        # Python ETL — loads CSVs into MongoDB Atlas
│   ├── queries.py                          # 5 analytical queries with printed results
│   ├── query_results.md                    # Pre-run results with interpretations
│   └── usage_guide.md                      # Step-by-step setup instructions
│
└── .gitignore
```

---

## Quickstart

### Prerequisites

- Python 3.10+
- A Kaggle account (free) — for dataset download
- A MongoDB Atlas account (free M0 tier) — for Task 2B and MongoDB API endpoints
- A MySQL 8+ instance — for Task 2A and SQL API endpoints

---

## Data Setup

The dataset is loaded inside the notebook via the Kaggle API using Colab Secrets.

**One-time setup:**

1. Go to [kaggle.com/settings](https://www.kaggle.com/settings) → API → **Create New Token**
2. Copy the `KGAT_...` token string
3. In Google Colab: click the **🔑 key icon** (left sidebar) → **+ Add new secret**
   - Name: `KAGGLE_TOKEN` | Value: your token | Toggle **Notebook access ON**
4. Run the data-loading cell — the dataset downloads and extracts automatically

**To run locally:**

```bash
export KAGGLE_API_TOKEN="your_KGAT_token_here"
pip install kaggle
kaggle datasets download -d sid321axn/beijing-multisite-airquality-data-set \
  --unzip -p ./beijing_air_quality_data
```

---

## Task 1 — Main Notebook

Open in Colab using the badge at the top, or locally with Jupyter:

```bash
pip install pandas numpy matplotlib seaborn statsmodels scikit-learn tensorflow
jupyter notebook Group_5_Formative_1_TimeSeries.ipynb
```

| Section | Content | Author |
|---|---|---|
| Problem Definition | Forecasting problem, dataset justification, pipeline overview | All |
| Task 1A — EDA | Time range, granularity, missing values, distributions, correlations | Ajak Chol |
| Task 1B — Analytical Questions | 5 questions incl. lag correlation (Q3) and moving averages (Q4) | Loic Higiro |
| Task 1C — Preprocessing | Imputation, cyclical encoding, wind vectors, lag features, OHE | Hamed Alfatih |
| Task 1C — Random Forest | Baseline + 2 experiments + experiment table | Hamed Alfatih |
| Task 1C — CNN-LSTM | Baseline + 2 experiments + experiment table | Arsene Kabasinga |
| Final Evaluation | Champion model comparison on held-out test set | Hamed Alfatih |

---

## Task 2A — MySQL Database

```bash
cd mysql_database

# 1. Create a .env file with your credentials
cp .env.example .env    # edit MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD

# 2. Create schema
mysql -u root -p < schema.sql

# 3. Load data
pip install mysql-connector-python pandas
python etl_load.py

# 4. Run queries
mysql -u root -p beijing_air_quality < queries.sql
```

**Schema:** 4 normalised tables (`stations`, `observations`, `air_quality_readings`,
`weather_readings`) + 1 staging table + 1 view (`v_hourly_air_quality`)

See `mysql_database/usage_guide.md` for full instructions.

---

## Task 2B — MongoDB Database

```bash
# Run from the project root

# 1. Set your Atlas connection string
echo 'MONGO_URI=mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/' > .env

# 2. Install dependencies
pip install pymongo[srv] pandas python-dotenv

# 3. Load data (~5–10 minutes, 420,768 documents)
python mongo_database/load_data.py

# 4. Run all 5 queries
python mongo_database/queries.py
```

**Schema:** 1 collection (`air_quality_readings`) — 420,768 documents, 3 indexes,
deterministic `_id`, pre-computed `season` field.

See `mongo_database/usage_guide.md` for Atlas cluster setup steps.

---

## Task 3 — REST API

```bash
pip install fastapi uvicorn pymongo[srv] mysql-connector-python python-dotenv

# Set environment variables (or use .env file)
export MONGO_URI="mongodb+srv://..."
export MYSQL_HOST="127.0.0.1"
export MYSQL_USER="root"
export MYSQL_PASSWORD="your_password"
export MYSQL_DATABASE="beijing_air_quality"

# Start the server
uvicorn app:app --reload

# Interactive docs available at:
# http://127.0.0.1:8000/docs
```

**Endpoints (14 total — 7 per database backend):**

| Method | SQL Endpoint | MongoDB Endpoint | Description |
|---|---|---|---|
| POST | `/api/v1/sql/air-quality` | `/api/v1/mongo/air-quality` | Create record |
| GET | `/api/v1/sql/air-quality/{id}` | `/api/v1/mongo/air-quality/{id}` | Read by ID |
| PUT | `/api/v1/sql/air-quality/{id}` | `/api/v1/mongo/air-quality/{id}` | Update record |
| DELETE | `/api/v1/sql/air-quality/{id}` | `/api/v1/mongo/air-quality/{id}` | Delete record |
| GET | `/api/v1/sql/time-series/latest` | `/api/v1/mongo/time-series/latest` | Latest record |
| GET | `/api/v1/sql/time-series/range` | `/api/v1/mongo/time-series/range` | Date range query |

---

## Task 4 — Prediction Script

```bash
# Ensure the API server is running first (see Task 3 above)
python predict.py
```

The script fetches a record from the API, preprocesses it using the same pipeline
as Task 1C, loads the saved Random Forest model, and prints a PM2.5 prediction.

---

## Model Results Summary

| Model | Experiment | Val R² | Val MAE | Test MAE |
|---|---|---|---|---|
| Random Forest | Baseline (max_depth=10) | 0.9542 | 9.27 | — |
| Random Forest | Exp 1: RandomizedSearchCV | 0.9546 | 9.39 | — |
| Random Forest | **Exp 2: Log-transform ✓** | **0.9536** | **9.05** | **9.03** |
| CNN-LSTM | Baseline (64 units, MSE) | 0.9507 | 10.61 | — |
| CNN-LSTM | Exp 1: 128 units + Dropout | 0.9548 | 9.79 | — |
| CNN-LSTM | Exp 2: Huber loss | 0.9545 | 9.64 | 9.95 |

**Champion: Random Forest Experiment 2** — lower test MAE and more stable error distribution.

---

## Team Contributions

| Member | Tasks | Key Deliverables |
|---|---|---|
| Hamed Alfatih | 1C (RF) · 2A (MySQL) | Random Forest pipeline (3 experiments), MySQL schema + ETL + 6 queries, final evaluation |
| Ajak Chol | 1A (EDA) · 2B (MongoDB) · 3 (API) · 4 (Predict) | EDA notebook, MongoDB schema + ETL + 5 queries, FastAPI gateway, prediction script |
| Loic Higiro | 1B (Analytical Questions) | 5 analytical questions with visualisations, lag correlation, moving average analysis |
| Arsene Kabasinga | 1C (DL) | CNN-LSTM pipeline (3 experiments), Huber loss experiment, residual analysis |

---

## References

- Liang, X. et al. (2015). Assessing Beijing's PM2.5 pollution: A time series analysis. *Proc. Royal Society A*, 471(2182).
- Breiman, L. (2001). Random forests. *Machine Learning*, 45(1), 5–32.
- Hochreiter, S. & Schmidhuber, J. (1997). Long short-term memory. *Neural Computation*, 9(8), 1735–1780.
- Huang, C. J. & Kuo, P. H. (2018). A deep CNN-LSTM model for PM2.5 prediction. *Sensors*, 18(7), 2220.