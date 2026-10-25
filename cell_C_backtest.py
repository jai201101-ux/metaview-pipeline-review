# HEX CELL C. Replaces the whole backtest cell (the one that starts with `def pa_build_backtest():`).
# Three changes from the July version, marked CHANGED below:
#   1. Products are read from "Product Names" (one row per deal now), with "Product Name" as a fallback.
#   2. "Created Date" in this export is a migration date (every deal says April or May 2026), so the
#      July backtest found nothing to test. A deal's effective created date is now its EARLIEST recorded
#      date: Created Date or any stage entered date, whichever came first.
#   3. The last validation check no longer expects one row per product line.

def pa_build_backtest():
    prediction_date = pd.Timestamp("2025-12-31")
    training_end = pd.Timestamp("2025-12-31")
    test_start = pd.Timestamp("2026-01-01")
    test_end = pd.Timestamp("2026-03-31")
    date_columns = [
        "Created Date", "Stage 1 Entered Date", "Stage 2 Entered Date", "Stage 3 Entered Date",
        "Stage 4 Entered Date", "Stage 5 Entered Date", "Stage 6 Entered Date",
        "Stage 7L Entered Date", "Stage 7W Entered Date",
    ]
    stage_map = {
        1: ("Stage 1 Entered Date", "Meeting booked"),
        2: ("Stage 2 Entered Date", "Discovery"),
        3: ("Stage 3 Entered Date", "Scoping"),
        4: ("Stage 4 Entered Date", "Evaluation"),
        5: ("Stage 5 Entered Date", "EB Go/No Go"),
        6: ("Stage 6 Entered Date", "Paper Process"),
    }
    raw_signature_before = (len(raw_df), int(pd.util.hash_pandas_object(raw_df, index=True).sum()))
    deal_signature_before = (len(deal_df), int(pd.util.hash_pandas_object(deal_df, index=True).sum()))
    queue_signature_before = (
        len(pa_executive_queue_df),
        tuple(pa_executive_queue_df["Opportunity ID"].astype("string")),
        tuple(pa_executive_queue_df["Priority"]),
        tuple(pa_executive_queue_df["Management Action"]),
    )
    source = deal_df.copy()
    for column in date_columns:
        source[column] = pd.to_datetime(source[column], errors="coerce")
    source["Opportunity ID"] = source["Opportunity ID"].astype("string")
    source = source.loc[source["Opportunity ID"].notna() & source["Opportunity ID"].str.strip().ne("")].copy()
    source = source.sort_values("Deal Row ID", kind="stable")
    product_column = "Product Names" if "Product Names" in source.columns else "Product Name"  # CHANGED 1

    def first_nonblank(series):
        values = series.dropna()
        if values.dtype == "object" or pd.api.types.is_string_dtype(values):
            values = values.loc[values.astype("string").str.strip().ne("")]
        return values.iloc[0] if len(values) else pd.NA

    def unique_dates(series):
        return pd.DatetimeIndex(pd.to_datetime(series, errors="coerce").dropna().unique()).sort_values()

    opportunity_records = []
    for opportunity_id, group in source.groupby("Opportunity ID", sort=False):
        won_dates = unique_dates(group["Stage 7W Entered Date"])
        lost_dates = unique_dates(group["Stage 7L Entered Date"])
        products = sorted({
            part.strip()
            for value in group[product_column].dropna()
            for part in str(value).split(",")
            if part.strip() not in {"", "nan", "None", "<NA>"}
        })  # CHANGED 1
        won_date = won_dates.max() if len(won_dates) else pd.NaT
        lost_date = lost_dates.max() if len(lost_dates) else pd.NaT
        effective_created = pd.concat(
            [pd.to_datetime(group[column], errors="coerce") for column in date_columns], axis=0
        ).min()  # CHANGED 2: earliest recorded date, because Created Date is a migration date
        record = {
            "Opportunity ID": str(opportunity_id),
            "Opportunity Owner": first_nonblank(group["Opportunity Owner"]),
            "Region": first_nonblank(group["Region"]),
            "Segment": first_nonblank(group["Segment"]),
            "Product": ", ".join(products) if products else "Not specified",
            "Opportunity Type": first_nonblank(group["Type"]),
            "Created Date": effective_created,
            "Salesforce Comparison Probability": pd.to_numeric(group["Probability Decimal"], errors="coerce").dropna().iloc[0] if pd.to_numeric(group["Probability Decimal"], errors="coerce").notna().any() else np.nan,
            "Won Date": won_date,
            "Lost Date": lost_date,
            "Outcome Conflict": pd.notna(won_date) and pd.notna(lost_date) and won_date == lost_date,
        }
        for stage_number, (stage_column, _) in stage_map.items():
            record[stage_column] = pd.to_datetime(group[stage_column], errors="coerce").min()
        opportunity_records.append(record)
    opportunities = pd.DataFrame(opportunity_records)
    final_won = opportunities["Won Date"].notna() & (
        opportunities["Lost Date"].isna() | opportunities["Won Date"].gt(opportunities["Lost Date"])
    )
    final_lost = opportunities["Lost Date"].notna() & (
        opportunities["Won Date"].isna() | opportunities["Lost Date"].gt(opportunities["Won Date"])
    )
    opportunities["Outcome"] = np.select([final_won, final_lost], [1, 0], default=np.nan)
    opportunities["Outcome Date"] = opportunities[["Won Date", "Lost Date"]].max(axis=1)

    def reconstruct_stage(row, cutoff):
        candidates = []
        for stage_number, (stage_column, stage_name) in stage_map.items():
            stage_date = row[stage_column]
            if pd.notna(stage_date) and stage_date <= cutoff:
                candidates.append((stage_date, stage_number, stage_name))
        if not candidates:
            return pd.Series([pd.NA, pd.NaT], index=["Reconstructed Stage", "Prediction Stage Date"])
        selected = max(candidates, key=lambda value: (value[0], value[1]))
        return pd.Series([selected[2], selected[0]], index=["Reconstructed Stage", "Prediction Stage Date"])

    reconstructed = opportunities.apply(lambda row: reconstruct_stage(row, prediction_date), axis=1)
    opportunities[["Reconstructed Stage", "Prediction Stage Date"]] = reconstructed
    known_outcome = opportunities["Outcome"].notna() & ~opportunities["Outcome Conflict"]
    training = opportunities.loc[
        known_outcome
        & opportunities["Outcome Date"].lt(test_start)
        & opportunities["Created Date"].le(training_end)
    ].copy()
    open_at_prediction = (
        opportunities["Created Date"].le(prediction_date)
        & (opportunities["Won Date"].isna() | opportunities["Won Date"].gt(prediction_date))
        & (opportunities["Lost Date"].isna() | opportunities["Lost Date"].gt(prediction_date))
        & opportunities["Reconstructed Stage"].notna()
    )
    test = opportunities.loc[
        known_outcome
        & open_at_prediction
        & opportunities["Outcome Date"].between(test_start, test_end, inclusive="both")
    ].copy()

    overall_win_rate = training["Outcome"].mean() if len(training) else np.nan
    predictions = []
    level_definitions = [
        ("Level 1", ["Region", "Segment", "Product", "Opportunity Type"], 20),
        ("Level 2", ["Region", "Segment", "Opportunity Type"], 20),
        ("Level 3", ["Region", "Segment"], 20),
        ("Level 4", ["Segment"], 20),
        ("Level 5", [], 5),
    ]
    stage_column_by_name = {stage_name: stage_column for _, (stage_column, stage_name) in stage_map.items()}
    for _, test_row in test.sort_values("Opportunity ID", kind="stable").iterrows():
        stage_name = test_row["Reconstructed Stage"]
        stage_column = stage_column_by_name[stage_name]
        reached_stage = training[stage_column].notna() & training[stage_column].le(training["Outcome Date"])
        stage_history = training.loc[reached_stage].copy()
        stage_prior = stage_history["Outcome"].mean() if len(stage_history) else overall_win_rate
        selected_history = None
        selected_level = "Overall fallback"
        for level_name, dimensions, minimum_sample in level_definitions:
            candidate = stage_history
            for dimension in dimensions:
                if pd.isna(test_row[dimension]):
                    candidate = candidate.iloc[0:0]
                    break
                candidate = candidate.loc[candidate[dimension].fillna("<missing>").eq(test_row[dimension])]
            if len(candidate) >= minimum_sample:
                selected_history = candidate
                selected_level = level_name
                break
        if selected_history is None:
            selected_history = training.copy()
        sample_size = len(selected_history)
        historical_wins = int(selected_history["Outcome"].sum()) if sample_size else 0
        raw_win_rate = selected_history["Outcome"].mean() if sample_size else np.nan
        if sample_size and pd.notna(stage_prior):
            adjusted_probability = (historical_wins + 20 * stage_prior) / (sample_size + 20)
        else:
            adjusted_probability = overall_win_rate
        adjusted_probability = float(np.clip(adjusted_probability, 0, 1)) if pd.notna(adjusted_probability) else np.nan
        sample_category = (
            "High (100+)" if sample_size >= 100 else
            "Medium (30–99)" if sample_size >= 30 else
            "Low (20–29)" if sample_size >= 20 else
            "Very low (<20)"
        )
        actual = int(test_row["Outcome"])
        # CHANGED 4: today's stored probability is 100% or 0% for a deal that has since resolved, which
        # would make Salesforce look perfect. Use the standard probability of the stage the deal was in
        # on the prediction date instead (read from the data in the snapshot cell).
        stage_number = next(n for n, (_, name) in stage_map.items() if name == stage_name)
        salesforce_probability = pa_stage_standard_probability.get(str(stage_number), np.nan) if "pa_stage_standard_probability" in globals() else np.nan
        salesforce_probability = float(np.clip(salesforce_probability, 0, 1)) if pd.notna(salesforce_probability) else np.nan
        predictions.append({
            "Opportunity ID": test_row["Opportunity ID"],
            "Opportunity Owner": test_row["Opportunity Owner"],
            "Region": test_row["Region"],
            "Segment": test_row["Segment"],
            "Product": test_row["Product"],
            "Opportunity Type": test_row["Opportunity Type"],
            "Reconstructed Stage at Prediction Date": stage_name,
            "Actual Result": actual,
            "Historically Adjusted Probability": adjusted_probability,
            "Salesforce Comparison Probability": salesforce_probability,
            "Comparison Level Used": selected_level,
            "Historical Sample Size": int(sample_size),
            "Raw Historical Win Rate": raw_win_rate,
            "Stage Prior Win Rate": stage_prior,
            "Historical Model Absolute Prediction Error": abs(adjusted_probability - actual) if pd.notna(adjusted_probability) else np.nan,
            "Salesforce Absolute Prediction Error": abs(salesforce_probability - actual) if pd.notna(salesforce_probability) else np.nan,
            "Confidence/Sample-Size Category": sample_category,
            "Prediction Stage Date": test_row["Prediction Stage Date"],
            "Created Date": test_row["Created Date"],
            "Outcome Date": test_row["Outcome Date"],
            "Open at Prediction Date": bool(open_at_prediction.loc[test_row.name]),
        })
    prediction_columns = [
        "Opportunity ID", "Opportunity Owner", "Region", "Segment", "Product", "Opportunity Type",
        "Reconstructed Stage at Prediction Date", "Actual Result", "Historically Adjusted Probability",
        "Salesforce Comparison Probability", "Comparison Level Used", "Historical Sample Size",
        "Raw Historical Win Rate", "Stage Prior Win Rate", "Historical Model Absolute Prediction Error",
        "Salesforce Absolute Prediction Error", "Confidence/Sample-Size Category", "Prediction Stage Date",
        "Created Date", "Outcome Date", "Open at Prediction Date",
    ]
    predictions_df = pd.DataFrame(predictions, columns=prediction_columns)

    if len(predictions_df):
        actuals = predictions_df["Actual Result"].astype(float)
        historical_probabilities = predictions_df["Historically Adjusted Probability"].astype(float)
        historical_brier = float(np.mean((historical_probabilities - actuals) ** 2))
        epsilon = 1e-15
        clipped_historical = historical_probabilities.clip(epsilon, 1 - epsilon)
        historical_log_loss = float(-np.mean(actuals * np.log(clipped_historical) + (1 - actuals) * np.log(1 - clipped_historical)))
        salesforce_available = predictions_df["Salesforce Comparison Probability"].notna()
        secondary_salesforce_brier = float(np.mean((predictions_df.loc[salesforce_available, "Salesforce Comparison Probability"] - actuals.loc[salesforce_available]) ** 2)) if salesforce_available.any() else np.nan
        clipped_salesforce = predictions_df.loc[salesforce_available, "Salesforce Comparison Probability"].clip(epsilon, 1 - epsilon)
        secondary_salesforce_log_loss = float(-np.mean(actuals.loc[salesforce_available] * np.log(clipped_salesforce) + (1 - actuals.loc[salesforce_available]) * np.log(1 - clipped_salesforce))) if salesforce_available.any() else np.nan
    else:
        historical_brier = historical_log_loss = secondary_salesforce_brier = secondary_salesforce_log_loss = np.nan

    valid_historical_snapshot = len(predictions_df) >= 20  # CHANGED 2: the test population now exists
    conclusion = "Insufficient Evidence" if not valid_historical_snapshot else (
        "Better" if historical_brier < secondary_salesforce_brier - 0.01 else
        "Worse" if historical_brier > secondary_salesforce_brier + 0.01 else
        "Similar"
    )
    summary_df = pd.DataFrame([{
        "Prediction Date": prediction_date,
        "Training Period End": training_end,
        "Unique Training Opportunities": int(training["Opportunity ID"].nunique()),
        "Unique Test Opportunities": int(predictions_df["Opportunity ID"].nunique()) if len(predictions_df) else 0,
        "Test Wins": int(predictions_df["Actual Result"].sum()) if len(predictions_df) else 0,
        "Test Losses": int(len(predictions_df) - predictions_df["Actual Result"].sum()) if len(predictions_df) else 0,
        "Actual Test Win Rate": predictions_df["Actual Result"].mean() if len(predictions_df) else np.nan,
        "Average Historically Adjusted Probability": predictions_df["Historically Adjusted Probability"].mean() if len(predictions_df) else np.nan,
        "Average Salesforce Probability": predictions_df["Salesforce Comparison Probability"].mean() if len(predictions_df) else np.nan,
        "Historical Model Brier Score": historical_brier,
        "Salesforce Brier Score": np.nan,
        "Historical Model Log Loss": historical_log_loss,
        "Salesforce Log Loss": np.nan,
        "Difference in Brier Score": historical_brier - secondary_salesforce_brier if len(predictions_df) else np.nan,
        "Secondary Export Salesforce Brier Score": secondary_salesforce_brier,
        "Secondary Export Salesforce Log Loss": secondary_salesforce_log_loss,
        "Conclusion": conclusion,
        "Earliest Source Created Date": opportunities["Created Date"].min(),
        "Source Date Limitation": "Created Date in the export is a migration date, so each deal's earliest recorded date (created or any stage entry) is used instead.",
        "Salesforce Comparison Limitation": "Historical probability snapshots are not in the export. The Salesforce benchmark is the standard probability of the stage each deal was in on the prediction date.",
    }])

    band_edges = np.linspace(0, 1, 11)
    band_labels = [f"{start}–{start + 10}%" for start in range(0, 100, 10)]
    if len(predictions_df):
        band_values = pd.cut(
            predictions_df["Historically Adjusted Probability"].clip(upper=1 - 1e-12),
            bins=band_edges,
            labels=band_labels,
            right=False,
            include_lowest=True,
        )
        band_records = []
        for band_label in band_labels:
            band_rows = predictions_df.loc[band_values.eq(band_label)]
            count = len(band_rows)
            average_probability = band_rows["Historically Adjusted Probability"].mean() if count else np.nan
            actual_rate = band_rows["Actual Result"].mean() if count else np.nan
            if count:
                z = 1.959963984540054
                denominator = 1 + z ** 2 / count
                center = (actual_rate + z ** 2 / (2 * count)) / denominator
                margin = z * np.sqrt(actual_rate * (1 - actual_rate) / count + z ** 2 / (4 * count ** 2)) / denominator
                ci_lower, ci_upper = max(0, center - margin), min(1, center + margin)
            else:
                ci_lower = ci_upper = np.nan
            band_records.append({
                "Probability Band": band_label,
                "Number of Test Opportunities": count,
                "Average Predicted Probability": average_probability,
                "Actual Win Rate": actual_rate,
                "Calibration Gap": average_probability - actual_rate if count else np.nan,
                "Actual Win Rate 95% CI Lower": ci_lower,
                "Actual Win Rate 95% CI Upper": ci_upper,
            })
        calibration_df = pd.DataFrame(band_records)
    else:
        calibration_df = pd.DataFrame({
            "Probability Band": band_labels,
            "Number of Test Opportunities": 0,
            "Average Predicted Probability": np.nan,
            "Actual Win Rate": np.nan,
            "Calibration Gap": np.nan,
            "Actual Win Rate 95% CI Lower": np.nan,
            "Actual Win Rate 95% CI Upper": np.nan,
        })

    segment_records = []
    breakdowns = {
        "Reconstructed Stage": "Reconstructed Stage at Prediction Date",
        "Region": "Region",
        "Segment": "Segment",
        "Comparison Level": "Comparison Level Used",
        "Confidence/Sample-Size Category": "Confidence/Sample-Size Category",
    }
    for breakdown_type, column in breakdowns.items():
        for breakdown_value, group in predictions_df.groupby(column, dropna=False):
            count = len(group)
            predicted_rate = group["Historically Adjusted Probability"].mean()
            actual_rate = group["Actual Result"].mean()
            segment_records.append({
                "Breakdown Type": breakdown_type,
                "Breakdown Value": breakdown_value if pd.notna(breakdown_value) else "Missing",
                "Test Opportunity Count": count,
                "Predicted Win Rate": predicted_rate,
                "Actual Win Rate": actual_rate,
                "Calibration Gap": predicted_rate - actual_rate,
                "Brier Score": np.mean((group["Historically Adjusted Probability"] - group["Actual Result"]) ** 2),
                "Small Group Flag": "Flag: fewer than 20 test opportunities" if count < 20 else "Sufficient group size",
            })
    segment_result_columns = [
        "Breakdown Type", "Breakdown Value", "Test Opportunity Count", "Predicted Win Rate",
        "Actual Win Rate", "Calibration Gap", "Brier Score", "Small Group Flag",
    ]
    segment_results_df = pd.DataFrame(segment_records, columns=segment_result_columns)

    raw_signature_after = (len(raw_df), int(pd.util.hash_pandas_object(raw_df, index=True).sum()))
    deal_signature_after = (len(deal_df), int(pd.util.hash_pandas_object(deal_df, index=True).sum()))
    queue_signature_after = (
        len(pa_executive_queue_df),
        tuple(pa_executive_queue_df["Opportunity ID"].astype("string")),
        tuple(pa_executive_queue_df["Priority"]),
        tuple(pa_executive_queue_df["Management Action"]),
    )
    validation_checks = [
        ("Training population is non-empty", "> 0 unique opportunities", int(training["Opportunity ID"].nunique()), training["Opportunity ID"].nunique() > 0),
        ("Test population is non-empty", "> 0 unique opportunities", int(predictions_df["Opportunity ID"].nunique()) if len(predictions_df) else 0, len(predictions_df) > 0),
        ("One row per unique tested Opportunity ID", len(predictions_df), predictions_df["Opportunity ID"].nunique() if len(predictions_df) else 0, predictions_df["Opportunity ID"].is_unique if len(predictions_df) else True),
        ("No training outcome on or after the test start", f"All before {test_start.date()}", training["Outcome Date"].max(), training["Outcome Date"].lt(test_start).all()),
        ("No test opportunity created after the prediction date", f"All on/before {prediction_date.date()}", predictions_df["Created Date"].max() if len(predictions_df) else pd.NaT, predictions_df["Created Date"].le(prediction_date).all() if len(predictions_df) else True),
        ("Every test opportunity was open at the prediction date", "All open", int(predictions_df["Open at Prediction Date"].sum()) if len(predictions_df) else 0, predictions_df["Open at Prediction Date"].all() if len(predictions_df) else True),
        ("Every test opportunity resolved in the test window", f"{test_start.date()} to {test_end.date()}", f"{predictions_df['Outcome Date'].min()} to {predictions_df['Outcome Date'].max()}" if len(predictions_df) else "No test rows", predictions_df["Outcome Date"].between(test_start, test_end, inclusive="both").all() if len(predictions_df) else True),
        ("No post-prediction stage date used", f"All on/before {prediction_date.date()}", predictions_df["Prediction Stage Date"].max() if len(predictions_df) else pd.NaT, predictions_df["Prediction Stage Date"].le(prediction_date).all() if len(predictions_df) else True),
        ("Probabilities remain between 0 and 1", "All historical probabilities", bool(predictions_df["Historically Adjusted Probability"].between(0, 1, inclusive="both").all()) if len(predictions_df) else True, predictions_df["Historically Adjusted Probability"].between(0, 1, inclusive="both").all() if len(predictions_df) else True),
        ("No missing actual outcomes", 0, int(predictions_df["Actual Result"].isna().sum()) if len(predictions_df) else 0, predictions_df["Actual Result"].notna().all() if len(predictions_df) else True),
        ("Existing app dataframes and calculations were not changed", "Unchanged signatures", "Unchanged" if raw_signature_before == raw_signature_after and deal_signature_before == deal_signature_after and queue_signature_before == queue_signature_after else "Changed", raw_signature_before == raw_signature_after and deal_signature_before == deal_signature_after and queue_signature_before == queue_signature_after),
        ("One row per deal in deal_df", raw_df["Opportunity ID"].nunique(), len(deal_df), deal_df["Opportunity ID"].is_unique and len(deal_df) == raw_df["Opportunity ID"].nunique()),  # CHANGED 3
    ]
    validation_df = pd.DataFrame(validation_checks, columns=["Validation Check", "Expected", "Actual", "Passed"])
    validation_df["Status"] = np.where(validation_df["Passed"], "Pass", "Fail")
    validation_df = validation_df.drop(columns="Passed")
    predictions_df = predictions_df.drop(columns=["Prediction Stage Date", "Created Date", "Outcome Date", "Open at Prediction Date", "Confidence/Sample-Size Category"])
    return summary_df, predictions_df, calibration_df, segment_results_df, validation_df


(
    pa_backtest_summary_df,
    pa_backtest_predictions_df,
    pa_backtest_calibration_df,
    pa_backtest_segment_results_df,
    pa_backtest_validation_df,
) = pa_build_backtest()
_s = pa_backtest_summary_df.loc[0]
pa_backtest_verdict = (
    "Insufficient Evidence: fewer than 20 deals were open on the prediction date and resolved in the test window."
    if int(_s["Unique Test Opportunities"]) < 20
    else (
        f"Backtest on {int(_s['Unique Test Opportunities'])} deals open on {_s['Prediction Date']:%d %b %Y} and resolved by {pd.Timestamp('2026-03-31'):%d %b %Y}: "
        f"they actually won {_s['Actual Test Win Rate']:.0%} of the time. The history-based model predicted {_s['Average Historically Adjusted Probability']:.0%} on average "
        f"(Brier {_s['Historical Model Brier Score']:.3f}); Salesforce's stage probabilities averaged {_s['Average Salesforce Probability']:.0%} "
        f"(Brier {_s['Secondary Export Salesforce Brier Score']:.3f}, using each deal's stage probability on the prediction date). "
        f"Conclusion: the history-based model is {_s['Conclusion'].lower()} than Salesforce on this test."
    )
)
pa_backtest_limitations_note = (
    "Created Date in this export is a migration date, so each deal's earliest recorded date stands in for it. "
    "The Salesforce benchmark is the stage probability on the prediction date, not a stored snapshot. "
    "Win rates fell sharply in early 2026, so any model trained on 2025 outcomes will run optimistic."
)
pa_backtest_brier_note = "Brier score measures the average squared difference between the predicted probability and the actual outcome. Lower is better; zero is perfect."
pa_backtest_validation_df
