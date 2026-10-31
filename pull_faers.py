"""
Step 1 of the Medication Coding AI project: pull messy drug names from openFDA.

What it does:
  - Downloads FDA adverse event reports (FAERS) from the openFDA API
  - Pulls out every drug name exactly as the reporter typed it (medicinalproduct)
  - Keeps openFDA's own RxCUI codes when it found a match (your "silver labels")
  - Saves everything to faers_drug_names.csv

How to run (from a terminal, in the folder where this file is saved):
  pip install requests pandas
  python pull_faers.py

Optional: get a free API key at https://open.fda.gov/apis/authentication/
and paste it into API_KEY below. Without one you're limited to 1,000 requests
per day, which is still plenty for this script (it makes about 5).
"""

import time
import requests
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FDA_API_KEY", "")
TOTAL_REPORTS = 5000         # how many reports to pull
PAGE_SIZE = 1000             # openFDA's maximum per request
DATE_RANGE = "[20250101 TO 20251231]"   # reports received in 2025
OUTPUT_FILE = "faers_drug_names.csv"

BASE_URL = "https://api.fda.gov/drug/event.json"


def fetch_page(skip):
    params = {
        "search": f"receivedate:{DATE_RANGE}",
        "limit": PAGE_SIZE,
        "skip": skip,
    }
    if API_KEY:
        params["api_key"] = API_KEY

    for attempt in range(3):
        resp = requests.get(BASE_URL, params=params, timeout=60)
        if resp.status_code == 200:
            return resp.json().get("results", [])
        if resp.status_code == 429:          # rate limited: wait and retry
            print("  Rate limited, waiting 30 seconds...")
            time.sleep(30)
            continue
        print(f"  Error {resp.status_code}: {resp.text[:200]}")
        resp.raise_for_status()
    raise RuntimeError("Gave up after 3 attempts")


def main():
    rows = []
    for skip in range(0, TOTAL_REPORTS, PAGE_SIZE):
        print(f"Fetching reports {skip + 1}-{skip + PAGE_SIZE}...")
        reports = fetch_page(skip)
        if not reports:
            break

        for report in reports:
            report_id = report.get("safetyreportid")
            for drug in report.get("patient", {}).get("drug", []):
                raw_name = drug.get("medicinalproduct")
                if not raw_name:
                    continue
                openfda = drug.get("openfda", {})
                rows.append({
                    "report_id": report_id,
                    "raw_name": raw_name.strip(),
                    "rxcui": "|".join(openfda.get("rxcui", [])),
                    "generic_name": "|".join(openfda.get("generic_name", [])),
                    "brand_name": "|".join(openfda.get("brand_name", [])),
                })
        time.sleep(1)  # be polite to the API

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)

    # Quick sanity check so you know it worked
    print("\nDone!")
    print(f"Drug mentions saved:      {len(df):,}")
    print(f"Unique raw drug names:    {df['raw_name'].nunique():,}")
    print(f"Mentions with an RxCUI:   {(df['rxcui'] != '').mean():.0%}")
    print(f"Saved to: {OUTPUT_FILE}")
    print("\nA few examples without a code (these are your interesting cases):")
    print(df[df["rxcui"] == ""]["raw_name"].drop_duplicates().head(10).to_string(index=False))


if __name__ == "__main__":
    main()
