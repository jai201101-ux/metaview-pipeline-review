# HEX CELL A. Replaces the whole "Prepare graph data" cell.
# Change from July: one row per deal. The export has one row per product line with the deal
# Amount repeated on every line, so counting rows counted a seven-product deal seven times.
# Product lines are kept separately in line_df for the product chart only.

import numpy as np
import pandas as pd

def currency_to_number(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r"[^\d.\-]", "", regex=True).replace("", np.nan),
        errors="coerce",
    )

line_df = raw_df.copy()
line_df["Line Value USD"] = currency_to_number(line_df["Total Price (converted)"])
line_df["Amount USD"] = currency_to_number(line_df["Amount"])

date_columns = [
    "Created Date", "Stage 1 Entered Date", "Stage 2 Entered Date", "Stage 3 Entered Date",
    "Stage 4 Entered Date", "Stage 5 Entered Date", "Stage 6 Entered Date",
    "Stage 7L Entered Date", "Stage 7W Entered Date", "Close Date", "Product Date",
]
for column in date_columns:
    if column in line_df.columns:
        line_df[column] = pd.to_datetime(line_df[column], errors="coerce", dayfirst=True)

# One row per deal. Deal value = sum of converted line totals (equals Amount for USD deals,
# converts the 46 EUR and GBP deals). Every other field is identical across a deal's lines.
first = lambda s: s.iloc[0]
deal_df = (
    line_df.sort_index()
    .groupby("Opportunity ID", sort=False)
    .agg(
        **{c: (c, first) for c in raw_df.columns if c not in ("Opportunity ID", "Product Name", "Quantity",
            "Sales Price", "Sales Price (converted)", "Total Price", "Total Price (converted)", "Product Date",
            "Product: Month", "Product Description", "List Price", "List Price (converted)", "Product Code", "Active Product")},
        **{"Deal Value USD": ("Line Value USD", "sum"),
           "Product Lines": ("Line Value USD", "size"),
           "Product Names": ("Product Name", lambda s: ", ".join(sorted(set(s.dropna()))))},
    )
    .reset_index()
)
deal_df.loc[deal_df["Deal Value USD"] == 0, "Deal Value USD"] = np.nan
deal_df["Deal Row ID"] = range(1, len(deal_df) + 1)
deal_df["Amount USD"] = deal_df["Deal Value USD"]          # downstream cells read Amount USD
deal_df["Product Value USD"] = deal_df["Deal Value USD"]

deal_df["Probability Decimal"] = pd.to_numeric(deal_df["Probability (%)"], errors="coerce").fillna(0)
deal_df["Weighted Pipeline USD"] = deal_df["Amount USD"].fillna(0) * deal_df["Probability Decimal"]

deal_df["Stage Name"] = (
    deal_df["Stage"].astype(str).str.replace(r"^\d+[A-Z]?\s*-\s*", "", regex=True).str.strip()
)
deal_df["Region"] = deal_df["Owner Role"].astype(str).str.extract(r"^(EMEA|AMER)", expand=False).fillna("Other")
deal_df["Segment"] = deal_df["Owner Role"].astype(str).str.extract(r"(SMB|MM|ENT)$", expand=False).fillna("Other")
deal_df["Is AE"] = deal_df["Owner Role"].astype(str).str.contains(r"\bAE\b", regex=True, na=False)
deal_df["Monthly Target USD"] = np.select(
    [deal_df["Is AE"] & deal_df["Segment"].eq("ENT"), deal_df["Is AE"] & deal_df["Segment"].isin(["MM", "SMB"])],
    [125000, 100000], default=np.nan,
)
deal_df["Won Date"] = deal_df["Stage 7W Entered Date"]
deal_df["Lost Date"] = deal_df["Stage 7L Entered Date"]
deal_df["Is Won"] = deal_df["Stage"].eq("7W - Closed Won")
deal_df["Is Lost"] = deal_df["Stage"].isin(["7L - Closed Lost", "Closed Lost"])
deal_df["Is Open"] = ~(deal_df["Is Won"] | deal_df["Is Lost"])

# The 13 May bulk close-out: 1,330 deals closed lost on one day, 83% reason Unknown.
# Flagged so rates can exclude it. Not removed.
deal_df["Bulk Close 13 May"] = deal_df["Is Lost"] & deal_df["Lost Date"].eq(pd.Timestamp("2026-05-13"))

preparation_check = pd.DataFrame({
    "Check": ["Source rows (product lines)", "Deals (one row each)", "Lines collapsed", "Deals with no amount", "Bulk close-out flagged"],
    "Result": [len(raw_df), len(deal_df), len(raw_df) - len(deal_df), int(deal_df["Deal Value USD"].isna().sum()), int(deal_df["Bulk Close 13 May"].sum())],
})
display(preparation_check)
display(deal_df[["Deal Row ID", "Opportunity ID", "Opportunity Owner", "Owner Role", "Amount USD", "Product Lines", "Stage", "Region", "Segment", "Weighted Pipeline USD"]].head(10))
