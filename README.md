# Copernicus Services Products Metadata

![Update Copernicus Metadata](https://github.com/do-me/Copernicus-Services-Products-Metadata/actions/workflows/update_data.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14-blue.svg)
![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)

This repository serves as an automated, centralized archive of product metadata from various **Copernicus Services**. 

A script runs automatically **every Sunday at 00:00 UTC** via GitHub Actions to mine the latest product catalogs. The results are committed directly to this repository, ensuring a history of dataset availability.

## Covered Services

The script aggregates metadata from the following 5/6 services:

| Service | Source URL | Output Filename |
| :--- | :--- | :--- |
| **Marine** (CMEMS) | [data.marine.copernicus.eu](https://data.marine.copernicus.eu/products) | `marine.*` |
| **Land** (CLMS) | [land.copernicus.eu](https://land.copernicus.eu/en/dataset-catalog) | `land.*` |
| **Atmosphere** (CAMS) | [ads.atmosphere.copernicus.eu](https://ads.atmosphere.copernicus.eu/datasets) | `atmosphere.*` |
| **Climate** (C3S) | [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu/datasets) | `climate.*` |
| **Emergency** (CEMS) | [emergency.copernicus.eu](https://emergency.copernicus.eu/data/) | `emergency.*` & `emergency_activities...*` |

Note that Security does not offer any EO products at the time of writing.

## Data Format & Access

All data is overwritten weekly to reflect the current state of the catalogs. Files are organized by format in the `outputs/` directory:

*   **Parquet (`outputs/parquet/`):** Best for programmatic access (Python/Pandas). Preserves data types.
*   **Excel (`outputs/excel/`):** Best for human review and manual filtering.
*   **CSV (`outputs/csv/`):** Universal compatibility.

### Quick Usage (Python)

You can load the latest metadata directly from this repository without cloning it:

```python
import pandas as pd

# Example: Load the Marine catalog
base_url = "https://github.com/do-me/Copernicus-Services-Products-Metadata/raw/main/outputs/parquet"
df_marine = pd.read_parquet(f"{base_url}/marine.parquet")

df_marine
```
<img width="1159" height="636" alt="image" src="https://github.com/user-attachments/assets/ceefe219-1588-4b36-a113-f047b31fec82" />


## Local Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and script execution.

1.  **Install uv** (if you haven't already):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Run the script:**
    There is no need to manually create a virtual environment or `pip install` dependencies. `uv` handles the inline script metadata automatically.
    ```bash
    uv run main.py
    ```

## Disclaimer

This is an unofficial mining script.
*   APIs used by this script are subject to change by the Copernicus providers.
*   Most APIs require a `limit` parameter; currently, the script is set to fetch up to 5,000 records per service to ensure full coverage.
*   If the number of products exceeds this limit in the future, the script may need adjustment.

**Author:** [Dominik Weckmüller](https://geo.rocks)
