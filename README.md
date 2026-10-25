# Metaview pipeline review, May 2026

One script rebuilds the monthly business review from the Salesforce export.

    python3 analysis.py      # cleans the export, writes out/metrics.json and the CSVs
    node deck.js             # builds out/Metaview_MBR_May_2026.pptx from metrics.json

Outputs in `out/`:
- `Metaview_MBR_May_2026.pptx` and `.pdf`: the review, 13 pages
- `deals_clean.csv`: one row per deal, with status, value in USD, won or lost month, flags
- `removed_and_why.csv`: every cleaning rule and how many deals it touched
- `priority_deals.csv`: open deals closing May or June, ranked by weighted value, with risk flags
- `stalled_deals.csv`: open deals carrying a flag, ranked by weighted value

Cleaning rules: one row per deal (the export has one row per product line); won and lost
month from the stage entered date; the 13 May bulk close-out (1,330 deals, 83% reason Unknown,
no activity found) kept but flagged and excluded from rates; deals with no amount kept for
counts only; created dates not used because every deal carries an April or May 2026 date.

## Added 25 Oct

- `calibrate.py`: calibrated deal ranking, ported from the July Hex workbook with two fixes (one row per deal; probability read as it stood at the snapshot). Writes `out/calibrated_deals.csv`, `out/vp_queue.csv` and a `calibration` block in `metrics.json`. Argument: training window in days before the cutoff (default 90; 0 = all history).
- `build_page.py`: the one-page HTML review from `metrics.json`, same numbers as the deck.
- `HEX_FIX_GUIDE.md`, `cell_A_prepare_deal_data.py`, `cell_B_snapshot_probability.py`: the guide and two paste-in cells to correct the July Hex workbook.
- `julius_prompt.md`: the corrected Julius prompt with sanity values.

Run order: `analysis.py`, `calibrate.py`, `node deck.js`, `build_page.py`.

## Data

The Salesforce export and every output file are confidential and are not in this repository.
To run it, put your own export at `data/deals.xlsx` and run the four scripts in the order above.
Outputs are written to `out/`.
