# HEX CELL B. Insert as a new Python cell immediately AFTER the cell that builds
# pa_base_df["pa_snapshot_stage"] (the snapshot reconstruction cell) and BEFORE the cell that
# starts with pa_base_df["pa_close_timing_status"].
#
# Fix: the July version read each deal's probability as it stands today. A deal that was open on
# 31 May but has since closed lost carries 0% today, so the model flagged it as "Salesforce too
# conservative". This cell restores the probability as it stood at the snapshot: the stored
# value when the deal is still in the same stage, otherwise the stage's standard probability.

import numpy as np
import pandas as pd

pa_stage_standard_probability = {"1": 0.10, "2": 0.20, "3": 0.30, "4": 0.50, "5": 0.75, "6": 0.90}
pa_current_stage_code = pa_base_df["Stage"].astype(str).str.extract(r"^(\d)", expand=False)
pa_open_at_snapshot = pa_base_df["pa_snapshot_status"].eq("Open")
pa_same_stage_now = pa_current_stage_code.eq(pa_base_df["pa_snapshot_stage_number"].astype(str))

pa_base_df["Probability At Snapshot"] = np.where(
    pa_open_at_snapshot & pa_same_stage_now,
    pd.to_numeric(pa_base_df["Probability Decimal"], errors="coerce"),
    pa_base_df["pa_snapshot_stage_number"].astype(str).map(pa_stage_standard_probability),
)
pa_base_df.loc[~pa_open_at_snapshot, "Probability At Snapshot"] = np.nan
pa_base_df["Probability Decimal"] = pa_base_df["Probability At Snapshot"].fillna(pa_base_df["Probability Decimal"])
pa_base_df["Weighted Pipeline USD"] = pa_base_df["Amount USD"].fillna(0) * pa_base_df["Probability Decimal"].fillna(0)

pa_snapshot_probability_check = pd.DataFrame({
    "Check": [
        "Deals open at snapshot",
        "Of which still in the same stage today (stored probability kept)",
        "Of which moved or closed since (stage standard probability restored)",
    ],
    "Result": [
        int(pa_open_at_snapshot.sum()),
        int((pa_open_at_snapshot & pa_same_stage_now).sum()),
        int((pa_open_at_snapshot & ~pa_same_stage_now).sum()),
    ],
})
display(pa_snapshot_probability_check)
