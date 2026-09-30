# Data Directory (`data/`)

This directory houses all raw datasets, road network graphs, sample camera video clips, and generated simulation logs.

## 📂 Subfolder Structure

```
data/
├── raw/            # Downloaded real-world videos, test images, and external datasets
├── networks/       # Cached OpenStreetMap road networks (GraphML or GeoPackage)
├── simulated/      # Output logs from Module 1 simulator (CSV / Parquet ANPR events)
└── sample/         # Lightweight fixture samples used for unit tests
```

> **Note:** The contents of this folder are excluded from Git tracking via `.gitignore` to keep the repository lightweight. Use automated simulator scripts or data ingestion pipelines to populate this folder locally.
