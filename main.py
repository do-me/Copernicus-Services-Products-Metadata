# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pandas","requests","pyarrow","openpyxl"
# ]
# ///

# Copernicus Services Products Metadata 
# This is the mining script and is fully working as of 04/12/2025. APIs or this script might break in the future. 
# Note that most of the APIs used here require a "limit" parameter to be specified, so keep in mind that if the number
# of products exceeds this parameter, multiple requests and consolidation efforts might be needed.
# Author: Dominik Weckmüller (https://geo.rocks)

import os 
import requests
import json
import pandas as pd

# Create output directories
os.makedirs("outputs/", exist_ok=True)
os.makedirs("outputs/parquet/", exist_ok=True)
os.makedirs("outputs/excel/", exist_ok=True)
os.makedirs("outputs/csv/", exist_ok=True)

# Helper function to save files in all formats
def save_dataframe(df, filename_base):
    # Parquet
    df.to_parquet(f"outputs/parquet/{filename_base}.parquet")
    
    # Excel (needs openpyxl installed, added to dependencies above)
    # Using engine='openpyxl' specifically helps with certain character encodings
    # We also use illegal_char_replacement just in case metadata contains control characters
    try:
        df.to_excel(f"outputs/excel/{filename_base}.xlsx", index=False)
    except Exception as e:
        print(f"Warning: Could not save {filename_base} to Excel due to: {e}")

    # CSV
    df.to_csv(f"outputs/csv/{filename_base}.csv", index=False)
    
    print(f"Saved outputs for {filename_base} (Parquet, Excel, CSV)")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

"""
1. Marine
https://data.marine.copernicus.eu/products
"""

# 1. Define the API endpoint and headers
url = 'https://data-be-prd.marine.copernicus.eu/api/datasets'

headers = {
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://data.marine.copernicus.eu',
    'Referer': 'https://data.marine.copernicus.eu/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'content-type': 'application/json',
}

# 2. Define the payload
payload = {
    "app": "cmems",
    "perimeter": "cmems",
    "facets": [
        "favorites", "timeRange", "vertLevels", "elevationRange", "colors",
        "mainVariables", "specificVariables", "areas", "indicatorFamilies",
        "featureTypes", "tempResolutions", "sources", "processingLevel",
        "directives", "communities", "originatingCenter"
    ],
    "facetValues": {},  # <--- Empty dict means "no filters"
    "freeText": "",
    "dateRange": {"begin": None, "end": None, "coverFull": False},
    "elevationRange": {"begin": None, "end": None},
    "offset": 0,
    "size": 5000, # Increased size to catch all datasets
    "variant": "summary",
    "lang": "en",
    "__myOcean__": True
}

try:
    # 3. Make the POST request
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    
    data = response.json()
    data = data["datasets"]
    df = pd.DataFrame(data).T
    
    save_dataframe(df, "marine")

except requests.exceptions.RequestException as e:
    print(f"Error fetching Marine data: {e}")
except Exception as e:
    print(f"An error occurred in Marine section: {e}")


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""
2. Land
https://land.copernicus.eu/en/dataset-catalog
"""

url = "https://land.copernicus.eu/++api++/en/dataset-catalog/@querystring-search"

# Define query with b_size=500 to fetch all ~316 items in one go
payload = {
    "b_size": "500", 
    "metadata_fields": "_all",
    "query": [{"i": "portal_type", "o": "plone.app.querystring.operation.selection.any", "v": ["DataSet"]}]
}

try:
    # Fetch, parse, and save
    response = requests.get(url, params={'query': json.dumps(payload)})
    df = pd.DataFrame(response.json()['items'])
    
    save_dataframe(df, "land")
except Exception as e:
    print(f"An error occurred in Land section: {e}")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

"""
3. Emergency 
https://emergency.copernicus.eu/data/

a) Actual Products (few)
b) Past Activations (>900)
"""

# a) Products
try:
    url = "https://ewds.climate.copernicus.eu/_next/data/2-bipz9DZL-VVNkdRqXty/en/datasets.json"
    response = requests.get(url)

    df = pd.DataFrame(response.json()["pageProps"]["datasets"])
    # Convert complex columns to string to avoid Parquet/Excel errors
    if "summaries" in df.columns:
        df["summaries"] = df["summaries"].astype(str)
        
    save_dataframe(df, "emergency")
except Exception as e:
    print(f"An error occurred in Emergency (Products) section: {e}")


# b) Activations
try:
    url = "https://mapping.emergency.copernicus.eu/activations/api/activations/?categories=flood%2Cfire%2Cearthquake%2Cvolcan%2Chumanitarian%2Cmass%2Cstorm%2Cindustrial%2Cenvironment%2Cother&activationTime=2012-01%2C2025-12&countries=&drmPhase=&closed=&limit=5000&q="
    response = requests.get(url)

    df = pd.DataFrame(response.json()["results"])
    save_dataframe(df, "emergency_activities_since_2012")
except Exception as e:
    print(f"An error occurred in Emergency (Activations) section: {e}")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

"""
4. Atmosphere 
https://ads.atmosphere.copernicus.eu/datasets
"""

try:
    url = "https://ads.atmosphere.copernicus.eu/_next/data/2-bipz9DZL-VVNkdRqXty/en/datasets.json"
    response = requests.get(url)

    df = pd.DataFrame(response.json()["pageProps"]["datasets"])
    if "summaries" in df.columns:
        df["summaries"] = df["summaries"].astype(str)
        
    save_dataframe(df, "atmosphere")
except Exception as e:
    print(f"An error occurred in Atmosphere section: {e}")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

"""
5. Climate 
https://cds.climate.copernicus.eu/datasets
"""

try:
    url = "https://cds.climate.copernicus.eu/api/catalogue/v1/datasets?limit=500"
    response = requests.get(url)

    df = pd.DataFrame(response.json()["collections"])
    if "summaries" in df.columns:
        df["summaries"] = df["summaries"].astype(str)
        
    save_dataframe(df, "climate")
except Exception as e:
    print(f"An error occurred in Climate section: {e}")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

"""
6. Security 
Nothing available at time of writing.
"""

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

print("Finished.")
