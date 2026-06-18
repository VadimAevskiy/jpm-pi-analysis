#!/usr/bin/env python3
"""Upload SSM daily prices to DEV Cerberus for 6 USD Burgiss indices.

Usage:
    export CERBERUS_TOKEN=$(sesame-cli impersonate --env=DEV "EdgeLab Employees")
    python3 upload_ssm_prices.py [prices_dir]

Default prices_dir: ~/Desktop/cerberus_extract
"""
import csv, os, sys, requests

token = os.environ.get("CERBERUS_TOKEN")
if not token:
    import subprocess
    token = subprocess.check_output(
        ["sesame-cli", "impersonate", "--env=DEV", "EdgeLab Employees"]
    ).decode().strip()

HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
BASE = "https://api.dev.edge-lab.ch/cerberus/custom-assets"
DIR = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Desktop/cerberus_extract")

# custom_asset_id, csv_filename, display_name
# Note: Go sanitizes '+' to 'p' in filenames. Use '_p_' variant.
FUNDS = [
    ("04cc4f53-e24f-45aa-85d0-5e975e67bfbd", "prices_USD___Eq_-_Buyout_p_Expansion_-_USD.csv", "Eq Buyout USD"),
    ("0f53a356-651b-485b-b70f-4a024f6aac0a", "prices_USD___Venture_Capital_-_USD.csv",         "VC USD"),
    ("d91d5307-2c1b-46ce-a33b-cdd2ba61be42", "prices_USD___Debt_-_Senior_-_USD.csv",            "Debt Senior USD"),
    ("3c20198f-2c5c-433d-a72d-b2de598f381b", "prices_USD___Real_Estate_-_Value-Added_-_USA_-_USD.csv", "RE VA USA USD"),
    ("364b461b-96cb-4c73-9048-e7f78eb8c407", "prices_USD___Infrastructure_-_USD.csv",           "Infra USD"),
    ("4464fe55-26c7-4e3b-bfc0-c691901b4590", "prices_USD___Timber_-_USD.csv",                   "Timber USD"),
]

print(f"Uploading SSM prices to DEV Cerberus")
print(f"Dir: {DIR}\n")

for aid, csvf, name in FUNDS:
    path = os.path.join(DIR, csvf)
    if not os.path.exists(path):
        print(f"  SKIP {name}: {csvf} not found")
        continue
    values = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            values[row["date"]] = float(row["price"])
    url = f"{BASE}/{aid}/time-series"
    r = requests.delete(url, headers=HEADERS)
    print(f"  {name}: DELETE {r.status_code}", end=" | ")
    r = requests.patch(url, headers=HEADERS, json={"unit": "Nominal", "field": "Price", "values": values})
    print(f"UPLOAD {r.status_code} ({len(values)} pts, {min(values.keys())} to {max(values.keys())})")

print("\nDone. Now run reprice_maestro.sh")
