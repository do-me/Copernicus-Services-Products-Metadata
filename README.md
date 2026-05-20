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
*   **TSV (`outputs/tsv/`):** Tab-separated values for better compatibility with certain tools.
*   **JSON (`outputs/json/`):** Standard JSON format (records-oriented) for web integrations.

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

### Consolidating all tables (Python+DuckDB)

```python
import duckdb
import pandas as pd

# 1. Define the base URL for the raw files
base_url = "https://raw.githubusercontent.com/do-me/Copernicus-Services-Products-Metadata/main/outputs/parquet"

# 2. Define the specific list of files you need
files = [
    "atmosphere.parquet",
    "climate.parquet",
    "emergency.parquet",
    #"emergency_activities_since_2012.parquet",
    "land.parquet",
    "marine.parquet"
]

# 3. Create a list of full URLs
file_urls = [f"{base_url}/{f}" for f in files]

# 4. Pass the LIST of URLs to read_parquet
# DuckDB handles the list automatically, and union_by_name normalizes the columns
query = """
    SELECT *
    FROM read_parquet(?, union_by_name=True)
"""

# Execute using parameters to inject the list safely
df = duckdb.execute(query, [file_urls]).df()

# Display
print(f"Loaded {len(df)} rows.")
df = df.astype(object).fillna("")
df # 781 rows
```

## AI Product Discovery Skill

This repository includes a lean skill for Claude Code and Codex at `skills/copernicus-product-discovery/`. It helps an agent turn a natural-language data need into ranked Copernicus product recommendations using the checked-in metadata.

[![skills.sh](https://skills.sh/b/do-me/Copernicus-Services-Products-Metadata)](https://skills.sh/do-me/Copernicus-Services-Products-Metadata)

The skill uses a retrieve-then-rerank workflow:

1. Load the local metadata from `outputs/csv/copernicus_*.csv`.
2. Build compact searchable product documents from each service's schema.
3. Retrieve a cheap lexical candidate set.
4. Rerank those candidates with Hugging Face's `cross-encoder/ettin-reranker-17m-v1`.

Run it with `uv`:

```bash
uv run skills/copernicus-product-discovery/scripts/discover_products.py \
  "daily sea surface temperature forecast for the Mediterranean" \
  --top-k 5
```

If `uv` is not installed, install it first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For a cheap lexical-only search without loading the reranker:

```bash
uv run skills/copernicus-product-discovery/scripts/discover_products.py \
  "daily sea surface temperature forecast for the Mediterranean" \
  --top-k 5 \
  --no-rerank
```

### Does the Reranker Add Value?

Yes, for natural-language discovery queries where intent matters. Lexical search is useful and cheap, but it tends to over-rank records that repeat the exact words in the query and under-rank records whose metadata expresses the same need differently.

Quality checks on the current metadata showed:

* Query: `daily sea surface temperature forecast for the Mediterranean`
  * Lexical-only ranked several observation/reprocessing SST records above the operational forecast.
  * Ettin promoted `Mediterranean Sea Physics Analysis and Forecast` into the top results because it matched the forecast intent, temporal currency, and Mediterranean coverage.
* Query: `global atmospheric methane and carbon dioxide forecasts`
  * Lexical-only ranked generic CAMS atmospheric composition forecasts first.
  * Ettin ranked `CAMS global greenhouse gas forecasts` first, matching methane, carbon dioxide, and forecast intent.
* Query: `flood emergency mapping activations in Bolivia damage assessment`
  * Ettin ranked the Bolivia flood activation records first and kept other flood-risk records lower.

Use `--no-rerank` when the user gives an exact product title, product id, service name, or a very simple keyword lookup. Use the default reranker path for open-ended product discovery, mixed constraints, or when the user asks for the "best" or "most suitable" product.

### First-Run Download Size

The repository metadata is already checked in. Current local sizes are approximately:

* `outputs/csv/`: 2.1 MB, used by the discovery script.
* `outputs/`: 9.9 MB total across CSV, TSV, JSON, Excel, and Parquet copies.
* `skills/copernicus-product-discovery/`: 24 KB.

On first reranked use, `uv` resolves Python dependencies and Sentence Transformers downloads `cross-encoder/ettin-reranker-17m-v1` into the Hugging Face cache. The measured model cache size is about 68 MB, with the main model weights file about 64 MB. Subsequent runs reuse the cache.

The reranker backend is selected automatically: CUDA if available, then Apple MPS, then CPU. You can override this for benchmarking or troubleshooting with `--device cpu`, `--device cuda`, or `--device mps`.

The default reranker batch size is `128`, tuned for better throughput than the Sentence Transformers default on local GPU/MPS backends. You can override it with `--batch-size`.

### Installing the Skill

Install from GitHub with the `skills.sh` CLI:

```bash
npx skills add https://github.com/do-me/Copernicus-Services-Products-Metadata --skill copernicus-product-discovery
```

Or use it directly from a local clone by pointing your agent at:

```text
skills/copernicus-product-discovery/SKILL.md
```

The skill follows the Agent Skills `SKILL.md` folder format, so compatible agents can load the same folder without service-specific changes.

### Publishing to Skill Directories

For `skills.sh`, no extra package manifest is required. The skill is installable directly from this GitHub repository with `npx skills add ...`; the public listing and install counts are driven by the `skills` CLI ecosystem.

For `agentskill.sh`, submit the GitHub repository at:

```text
https://agentskill.sh/submit
```

Use this repository URL:

```text
https://github.com/do-me/Copernicus-Services-Products-Metadata
```

`agentskill.sh` scans repositories for `SKILL.md` files. To keep the listing current immediately after pushes, add its GitHub webhook:

```text
https://agentskill.sh/api/webhooks/github
```

Use content type `application/json` and push events only.

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
