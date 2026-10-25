# Fixing the Hex workbook (free plan, in the browser, about 20 minutes)

Two pastes and a handful of expected-value edits. Nothing else changes.

## 1. Replace the "Prepare graph data" cell

Open the cell titled "Prepare graph data". Select all its code and replace it with the contents of
`cell_A_prepare_deal_data.py`. Run it.

Expected output (the preparation check table):

| Check | Result |
|---|---|
| Source rows (product lines) | 15510 |
| Deals (one row each) | 15056 |
| Lines collapsed | 454 |
| Deals with no amount | 1224 |
| Bulk close-out flagged | 1330 |

## 2. Re-run "Calculate reporting period and KPIs"

No edit needed. With Review date 2026-05-31 and Previous complete month, the KPI table should now read:

| Metric | Value |
|---|---|
| Won count | 136 |
| Won value | 1,110,259 |
| Average won deal | 8,164 |
| Lost count | 1,678 (of which 1,330 are the 13 May bulk close-out) |
| Win rate | 7.5% raw, 28.1% excluding the bulk close-out |
| Open pipeline count | 926 |
| Open pipeline value | 18,740,429 |
| Weighted open pipeline | 6,602,438 |

If you see 231 and 3,245,789 the old cell is still running. Check step 1 saved.

## 3. Add the snapshot probability cell

In Stage 1, find the cell that builds `pa_base_df["pa_snapshot_stage"]` (it starts with
`pa_stage_date_map = {`). Add a new Python cell directly below it and paste
`cell_B_snapshot_probability.py`. Run it.

Expected: roughly 1,100 deals open at snapshot, around 850 still in the same stage, around 250 moved or closed since.

## 4. Flip the checks that were written to enforce the old rule

These checks were written in July to confirm that NO deduplication happened. They will now show
Fail. Each is one line. Change the expected text and the pass condition, or simply delete the line.

- Readiness check cell: `"No Opportunity ID deduplication occurred"` and `"deal_df row count matches raw_df"`.
  Replace the `raw_df["Opportunity ID"]...equals(...)` comparison with `deal_df["Opportunity ID"].is_unique`.
- Stage 1 validation cell: checks 1, 2, 3, 24, 28 (they compare `pa_source_row_count` to `len(deal_df)`, which is now 15,056, so 1 and 2 still pass; 3, 24 and 28 need `pa_original_repeated_additional` set to 0).
  Simplest: at the top of that cell add `pa_original_repeated_additional = 0` after it is first computed.
- Stage 2 validation cell: checks 3, 20, 25. Same fix: after `pa_forecast_repeated_additional` is computed add `pa_forecast_repeated_additional = 0`.
- Release 1 cell: `("Raw source rows remain 15,510", ...)` still passes because `raw_df` is untouched. `("No raw rows were deleted", len(raw_df), len(deal_df), ...)` will fail; change the third argument to `len(raw_df)`.

## 5. What the Stage 2 queue should look like afterwards

The top ten by management attention will contain ten different deals (no owner repeated four times for one deal). The "Salesforce assigns 0%" entries disappear. The growth target reads about 1,332,000 (May won 1,110,259 x 1.2), not 3,894,947.

## 6. Known limitation, worth saying out loud

The calibration trains on 2025 history where deals won 58% of the time. In 2026 the win rate is
in the twenties. So the calibrated probabilities run high. The Python version in the repo adds a
90-day training window for that reason. The workbook's own check 32 ("historical calibration may
not represent current market conditions") was right.
