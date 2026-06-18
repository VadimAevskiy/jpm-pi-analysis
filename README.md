# JPM Private Investments: SSM Analysis Pipeline

End-to-end guide for mapping update, beta analysis, SSM price upload, and portfolio risk computation for 63 Burgiss MSCI funds across 6 currencies and 10 PI portfolios.

## Prerequisites

- Go toolchain (`go test` for voldorak)
- Python 3 with `openpyxl`, `pandas`, `matplotlib`, `requests`
- `sesame-cli` for EdgeLab API authentication
- `grpcurl` for direct Voldorak gRPC access (optional, debugging only)
- Access to EdgeLab DEV environment
- Excel with EdgeLab add-in (ELRISKMEASURE / ELSTRESSSCENARIO)

## Directory Layout

```
~/Desktop/voldorak/                          # voldorak repo
~/Desktop/voldorak/deployment/private_asset_mapping.csv  # active mapping
~/Desktop/cerberus_extract/                  # SSM pipeline output
~/Desktop/cerberus_extract/rolling/stats/    # rolling stats CSV
~/Desktop/cerberus_extract/rolling/params/   # rolling params CSV
~/Desktop/beta_analysis_output/              # beta visualization PDFs (7 folders)
```

## Step 1: Update Proxy Mapping

The mapping CSV is at `deployment/private_asset_mapping.csv` in the voldorak repo.

Columns: `label, nav_asset_id, fund_type, proxy_uuid, broad_uuid, proxy_weight, broad_weight`

For JPM, 20 strategies were updated:
- 12 PE/VC funds: `broad_uuid` changed to JPM market indices (MSCI EM, MSCI Europe, S&P 500 SPXT)
- 8 RE Value-Added funds: `proxy_uuid` changed to S&P Global REIT (SREITTGL)

JPM market index UUIDs:
```
MSCI EM (NDUEEGF):           7e4d92cc-bc34-4ada-9175-41b8953eac42
MSCI Europe (NDDUE15):       8a8d9a6c-b780-4196-aab2-017d64433220
S&P 500 (SPXT):              e6d2255d-b226-4fcd-8b49-3d72c2aa6b00
S&P Global REIT (SREITTGL):  cd3b61ad-08af-49f7-a429-ea935c8942d4
```

After editing, commit and push:
```bash
cd ~/Desktop/voldorak
git checkout -b feature/jpm-mapping-update
git add deployment/private_asset_mapping.csv
git commit -m "feat: update 20 PI fund mappings per JPM agreed indices"
git push origin feature/jpm-mapping-update
```

## Step 2: Run SSM Pipeline (63 funds)

Generate daily SSM prices for all 63 funds:
```bash
cd ~/Desktop/voldorak
go test -tags local -run TestLocalPipeline_All -timeout 30m -v ./internal/nowcasting/
```

Output: `~/Desktop/cerberus_extract/prices_*.csv` (one per fund, ~515 daily points each).

Note: Go sanitizes `+` to `p` in filenames. The correct file for USD Buyout is
`prices_USD___Eq_-_Buyout_p_Expansion_-_USD.csv` (not `_+_`).

## Step 3: Run Rolling Beta Analysis (63 funds x 535 dates)

```bash
cd ~/Desktop/voldorak
go clean -testcache
SSM_ROLLING_START=2006-01-01 SSM_ROLLING_END=2026-06-30 \
  go test -tags local -run TestLocalRolling -timeout 120m -v ./internal/nowcasting/
```

Output: `~/Desktop/cerberus_extract/rolling/stats/rolling_stats_by_asset.csv`
        `~/Desktop/cerberus_extract/rolling/params/rolling_params_by_asset.csv`

Runtime: ~11 minutes (12 cores).

## Step 4: Generate Beta Visualization PDFs

```bash
python3 ~/Downloads/beta_v4.py \
  ~/Desktop/cerberus_extract/rolling/params/rolling_params_by_asset.csv \
  ~/Downloads/etp_mapping.csv
```

Output: `~/Desktop/beta_analysis_output/` with 7 subfolders (16-page PDFs each).

## Step 5: Upload SSM Prices to DEV Cerberus

Authenticate and upload the 6 USD Burgiss indices used by the 10 PI portfolios:

```bash
export CERBERUS_TOKEN=$(sesame-cli impersonate --env=DEV "EdgeLab Employees")
python3 scripts/jpm/upload_ssm_prices.py ~/Desktop/cerberus_extract
```

Custom Asset IDs (DEV):
```
Eq Buyout Expansion USD:    04cc4f53-e24f-45aa-85d0-5e975e67bfbd
Venture Capital USD:        0f53a356-651b-485b-b70f-4a024f6aac0a
Debt Senior USD:            d91d5307-2c1b-46ce-a33b-cdd2ba61be42
RE Value-Added USA USD:     3c20198f-2c5c-433d-a72d-b2de598f381b
Infrastructure USD:         364b461b-96cb-4c73-9048-e7f78eb8c407
Timber USD:                 4464fe55-26c7-4e3b-bfc0-c691901b4590
```

## Step 6: Trigger Repricing via Maestro

```bash
export CERBERUS_TOKEN=$(sesame-cli impersonate --env=DEV "EdgeLab Employees")

for ID in \
  04cc4f53-e24f-45aa-85d0-5e975e67bfbd \
  0f53a356-651b-485b-b70f-4a024f6aac0a \
  d91d5307-2c1b-46ce-a33b-cdd2ba61be42 \
  3c20198f-2c5c-433d-a72d-b2de598f381b \
  364b461b-96cb-4c73-9048-e7f78eb8c407 \
  4464fe55-26c7-4e3b-bfc0-c691901b4590
do
  curl -sS --request PUT \
    --url "https://api.dev.edge-lab.ch/maestro/pricing/$ID" \
    --header "Authorization: Bearer $CERBERUS_TOKEN" \
    --header "Content-Type: application/json" \
    -w "$ID: HTTP %{http_code}\n" -o /dev/null
done
```

All should return HTTP 202 (Accepted). Wait 1-2 minutes for async processing.

## Step 7: Open Portfolio Risk Excel

Open `JPM_Portfolio_Risk_10_Funds.xlsx` in Excel with EdgeLab add-in connected to DEV.
Press Ctrl+Shift+F9 to compute all formulas.

The workbook contains 10 portfolios (7 public + 1 PI each, 20% PI weight) with:
- ELRISKMEASURE: Vol, ES, VaR (positions + contributions + portfolio)
- ELSTRESSSCENARIO: 2008 GFC (3021), USD +100bps (21148), USD -100bps (21157)

## Step 8: Old vs New Mapping Comparison (optional)

To produce a fair comparison, run the rolling pipeline twice back-to-back
(same data, different mapping):

```bash
cd ~/Desktop/voldorak
go clean -testcache

# Run with OLD mapping
cp OLD_MAPPING.csv deployment/private_asset_mapping.csv
SSM_ROLLING_START=2006-01-01 SSM_ROLLING_END=2026-06-30 \
  go test -tags local -run TestLocalRolling -timeout 120m -v ./internal/nowcasting/
mv ~/Desktop/cerberus_extract/rolling/stats/rolling_stats_by_asset.csv \
   ~/Desktop/cerberus_extract/rolling/stats/rolling_stats_OLD.csv
mv ~/Desktop/cerberus_extract/rolling/params/rolling_params_by_asset.csv \
   ~/Desktop/cerberus_extract/rolling/params/rolling_params_OLD.csv

# Run with NEW mapping
cp NEW_MAPPING.csv deployment/private_asset_mapping.csv
SSM_ROLLING_START=2006-01-01 SSM_ROLLING_END=2026-06-30 \
  go test -tags local -run TestLocalRolling -timeout 120m -v ./internal/nowcasting/
mv ~/Desktop/cerberus_extract/rolling/stats/rolling_stats_by_asset.csv \
   ~/Desktop/cerberus_extract/rolling/stats/rolling_stats_NEW.csv
mv ~/Desktop/cerberus_extract/rolling/params/rolling_params_by_asset.csv \
   ~/Desktop/cerberus_extract/rolling/params/rolling_params_NEW.csv
```

Then generate comparison Excel:
```bash
python3 scripts/jpm/generate_comparison_excel.py \
  rolling_stats_OLD.csv rolling_stats_NEW.csv \
  rolling_params_OLD.csv rolling_params_NEW.csv
```

43 unchanged funds will show zero diff (machine precision). 20 changed funds show real impact.

## Authentication Reference

```bash
# DEV (Cerberus, Maestro, Recco)
sesame-cli impersonate --env=DEV "EdgeLab Employees"
# Audience: https://api.dev.edge-lab.ch
# Org: 12ac923b-313d-4e09-9cf5-0d43e1f630ec

# PROD (Cerberus, Maestro)
sesame-cli impersonate --env=PROD "EdgeLab Employees"
# Audience: https://api.edgelab.ch
# Org: 12ac923b-313d-4e09-9cf5-0d43e1f630ec

# Voldorak gRPC (DEV, direct)
dig +short SRV _voldorak._tcp.service.consul
# Then: grpcurl -plaintext <IP>:<PORT> edgelab.voldorak.v1.VoldorakService/Spot
```

## Stress Scenario IDs

```
3021  = 2008 GFC
21148 = USD yield curve +100 bps
21157 = USD yield curve -100 bps
21151 = EUR yield curve +100 bps
21152 = EUR yield curve -100 bps
10053 = USD yield curve -25 bps
10054 = USD yield curve +25 bps
```

## PI Fund to Burgiss Index Mapping (10 portfolios)

| Fund | JPM ID | Strategy | Burgiss Index | Custom Asset ID |
|------|--------|----------|---------------|-----------------|
| KKR North America XIV | 8104697100 | Core PE / Large Cap | Eq Buyout Expansion USD | 04cc4f53 |
| Riverstone IV | 8104697100 | Core PE / Energy | Eq Buyout Expansion USD | 04cc4f53 |
| Learn Capital IV | 8108570100 | VC / Venture | Venture Capital USD | 0f53a356 |
| DFJ Growth IV | 8108570100 | VC / Growth | Venture Capital USD | 0f53a356 |
| HPS Core Senior Lending II | 8104716100 | Credit / Direct Lending | Debt-Senior-USD | d91d5307 |
| Apollo EPF IV | 8104710100 | Credit / Distressed | Debt-Senior-USD | d91d5307 |
| GSO Energy | 8104710100 | Credit / Real Asset | Debt-Senior-USD | d91d5307 |
| Sculptor RE Fund V | 8104703100 | RA / Opp Value-Add | RE Value-Added USA USD | 3c20198f |
| ASF IX | 8104718100 | RA / Infrastructure | Infrastructure USD | 364b461b |
| Water Property Investor II | 9006185000 | RA / Timber | Timber USD | 4464fe55 |
