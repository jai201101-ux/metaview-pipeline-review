"""Metaview pipeline review: clean the Salesforce export, then compute every number the MBR needs.

Rules (all written to out/removed_and_why.csv so a reader can check them):
  1. One deal per Opportunity ID. The export has one row per product line, so a deal with
     four products appears four times. Deal value = sum of 'Total Price (converted)' in USD.
  2. Won / lost month comes from the Stage 7W / 7L entered date, falling back to Close Date.
  3. Deals closed lost on 13 May 2026 with reason 'Unknown' and no recorded activity are a
     bulk hygiene close, not real losses that month. They are kept but flagged, and shown
     separately so they do not distort the win rate.
  4. Deals with no amount are kept for counts but excluded from value sums.
  5. 'Created Date' runs only Apr to May 2026 for every deal, so it is a migration date, not
     the real creation date, and is not used for deal age.
"""
import json, re
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).parent
OUT = ROOT / "out"; OUT.mkdir(exist_ok=True)
PERIOD = pd.Period("2026-05", "M"); PREV = PERIOD - 1; NEXT = PERIOD + 1
TARGET = {"ENT": 125_000, "MM": 100_000, "SMB": 100_000}
GROWTH = 0.20

def money(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")

raw = pd.read_excel(ROOT / "data/deals.xlsx")
raw["line_usd"] = money(raw["Total Price (converted)"])
raw["amount_ccy"] = raw["Amount"].astype(str).str.extract(r"^([A-Z]{3})")[0]

# ---------- 1. one row per deal ----------
first = lambda s: s.iloc[0]
deals = raw.groupby("Opportunity ID", sort=False).agg(
    owner=("Opportunity Owner", first), role=("Owner Role", first), account=("Account ID", first),
    type=("Type", first), stage=("Stage", first), prob=("Probability (%)", first),
    won_date=("Stage 7W Entered Date", first), lost_date=("Stage 7L Entered Date", first),
    close_date=("Close Date", first), created=("Created Date", first),
    s1=("Stage 1 Entered Date", first), s2=("Stage 2 Entered Date", first), s3=("Stage 3 Entered Date", first),
    s4=("Stage 4 Entered Date", first), s5=("Stage 5 Entered Date", first), s6=("Stage 6 Entered Date", first),
    attribution=("Attribution", first), lost_reason=("Closed Lost Reason", first),
    lost_detail=("Closed Lost Reason Detail", first), ccy=("amount_ccy", first),
    value_usd=("line_usd", "sum"), lines=("line_usd", "size"),
    products=("Product Name", lambda s: ", ".join(sorted(set(s.dropna())))),
).reset_index()
deals.loc[deals.value_usd == 0, "value_usd"] = np.nan
deals["stage"] = deals.stage.replace({"Closed Lost": "7L - Closed Lost"})
deals["status"] = np.select([deals.stage.str.startswith("7W"), deals.stage.str.startswith("7L")], ["won", "lost"], "open")
deals["segment"] = deals.role.str.extract(r"(SMB|MM|ENT)")[0].fillna("Other")
deals["region"] = deals.role.str.extract(r"^(EMEA|AMER)")[0].fillna("Other")
deals["is_ae"] = deals.role.str.contains("AE", na=False)
deals["won_date"] = deals.won_date.where(deals.won_date.notna(), deals.close_date.where(deals.status == "won"))
deals["lost_date"] = deals.lost_date.where(deals.lost_date.notna(), deals.close_date.where(deals.status == "lost"))
deals["won_m"] = deals.won_date.dt.to_period("M"); deals["lost_m"] = deals.lost_date.dt.to_period("M")
deals["close_m"] = deals.close_date.dt.to_period("M")
deals["weighted"] = deals.value_usd * deals.prob.fillna(0)
stage_dates = deals[["s1", "s2", "s3", "s4", "s5", "s6"]]
deals["stage_entered"] = stage_dates.max(axis=1)
deals["days_in_stage"] = (pd.Timestamp("2026-05-31") - deals.stage_entered).dt.days.clip(lower=0)

# ---------- 3. bulk hygiene close ----------
bulk = (deals.status == "lost") & (deals.lost_date == "2026-05-13")
deals["bulk_close"] = bulk

# ---------- removed and why ----------
rows = []
dup = raw["Opportunity ID"].duplicated().sum()
rows.append(["Duplicate product lines collapsed", dup, "One row per deal; product lines kept for the product chart only"])
rows.append(["Bulk hygiene close flagged", int(bulk.sum()), "All deals closed lost on 13 May 2026 (83% reason Unknown, no activity found). Shown separately, excluded from win-rate trend"])
rows.append(["Deals with no amount", int(deals.value_usd.isna().sum()), "Kept for counts, excluded from value sums"])
rows.append(["Open deals with close date in the past", int(((deals.status == "open") & (deals.close_date < "2026-06-01")).sum()), "Flagged at risk, left in pipeline"])
rows.append(["Won deals missing a won date", int(((deals.status == "won") & raw.groupby("Opportunity ID")["Stage 7W Entered Date"].first().isna().reindex(deals["Opportunity ID"]).values).sum()), "Close Date used instead"])
rows.append(["'Closed Lost' without stage number", int((raw.Stage == "Closed Lost").sum()), "Normalised to 7L"])
rows.append(["Non USD deals (EUR, GBP)", int(deals.ccy.isin(["EUR", "GBP"]).sum()), "Converted figure from the export used"])
rows.append(["Created Date not used", len(deals), "Every deal is dated Apr to May 2026, a migration date, so deal age uses stage entered dates"])
pd.DataFrame(rows, columns=["Rule", "Deals affected", "What we did"]).to_csv(OUT / "removed_and_why.csv", index=False)
deals.drop(columns=["s1", "s2", "s3", "s4", "s5", "s6"]).to_csv(OUT / "deals_clean.csv", index=False)

# ---------- metrics ----------
M = {}
real_lost = deals[(deals.status == "lost") & ~bulk]
def monthly(df, col):
    g = df.groupby(col).agg(n=("value_usd", "size"), v=("value_usd", "sum"))
    return g
months = [PERIOD - i for i in range(11, -1, -1)]
won_m = monthly(deals[deals.status == "won"], "won_m").reindex(months, fill_value=0)
lost_m = monthly(real_lost, "lost_m").reindex(months, fill_value=0)
bulk_m = monthly(deals[bulk], "lost_m").reindex(months, fill_value=0)
M["trend"] = [dict(month=str(m), won_n=int(won_m.n[m]), won_v=float(won_m.v[m]), lost_n=int(lost_m.n[m]), lost_v=float(lost_m.v[m]),
                   bulk_n=int(bulk_m.n[m]), bulk_v=float(bulk_m.v[m]),
                   win_rate=float(won_m.n[m] / (won_m.n[m] + lost_m.n[m])) if (won_m.n[m] + lost_m.n[m]) else None) for m in months]

cur_won = deals[(deals.status == "won") & (deals.won_m == PERIOD)]
prev_won = deals[(deals.status == "won") & (deals.won_m == PREV)]
cur_lost = real_lost[real_lost.lost_m == PERIOD]
open_ = deals[deals.status == "open"]
M["scorecard"] = dict(
    won_n=len(cur_won), won_v=float(cur_won.value_usd.sum()), avg_won=float(cur_won.value_usd.mean()),
    prev_won_n=len(prev_won), prev_won_v=float(prev_won.value_usd.sum()),
    lost_n=len(cur_lost), lost_v=float(cur_lost.value_usd.sum()), bulk_n=int(bulk.sum()), bulk_v=float(deals[bulk].value_usd.sum()),
    win_rate=len(cur_won) / (len(cur_won) + len(cur_lost)),
    prev_win_rate=len(prev_won) / (len(prev_won) + len(real_lost[real_lost.lost_m == PREV])),
    open_n=len(open_), open_v=float(open_.value_usd.sum()), open_w=float(open_.weighted.sum()),
    julius_won_v=3_245_789, julius_won_n=231, julius_prev_won_v=2_522_111,
)

def by(df_cur, df_prev, key):
    c = df_cur.groupby(key).agg(n=("value_usd", "size"), v=("value_usd", "sum"))
    p = df_prev.groupby(key).agg(pv=("value_usd", "sum"))
    l = cur_lost.groupby(key).agg(ln=("value_usd", "size"))
    t = c.join(p, how="outer").join(l, how="outer").fillna(0)
    t["change"] = (t.v - t.pv) / t.pv.replace(0, np.nan)
    t["win_rate"] = t.n / (t.n + t.ln)
    return [dict(key=k, **{a: (float(b) if isinstance(b, (float, np.floating)) and not np.isnan(b) else (None if isinstance(b, float) else int(b))) for a, b in r.items()}) for k, r in t.iterrows()]
M["region"] = by(cur_won, prev_won, "region")
M["segment"] = by(cur_won, prev_won, "segment")

# products: lines of won deals this month
won_ids = set(cur_won["Opportunity ID"]); prev_ids = set(prev_won["Opportunity ID"])
lines = raw[raw["Product Name"].notna()]
pc = lines[lines["Opportunity ID"].isin(won_ids)].groupby("Product Name").agg(deals=("Opportunity ID", "nunique"), v=("line_usd", "sum"))
pp = lines[lines["Opportunity ID"].isin(prev_ids)].groupby("Product Name").agg(pv=("line_usd", "sum"))
pt = pc.join(pp, how="left").fillna(0).sort_values("v", ascending=False).head(10)
pt["change"] = (pt.v - pt.pv) / pt.pv.replace(0, np.nan)
M["products"] = [dict(name=k, deals=int(r.deals), v=float(r.v), pv=float(r.pv), change=(None if np.isnan(r.change) else float(r.change))) for k, r in pt.iterrows()]
M["product_coverage"] = dict(won_with_product=int(cur_won.products.ne("").sum()), won_total=len(cur_won))

order = ["1 - Meeting booked", "2 - Discovery", "3 -Scoping", "4 - Evaluation", "5 - EB Go/No Go", "6 - Paper Process"]
st = open_.groupby("stage").agg(n=("value_usd", "size"), v=("value_usd", "sum"), w=("weighted", "sum")).reindex(order).fillna(0)
M["stages"] = [dict(stage=re.sub(r"^\d -\s?", "", k), n=int(r.n), v=float(r.v), w=float(r.w)) for k, r in st.iterrows()]
for key in ["region", "segment"]:
    g = open_.groupby(key).agg(n=("value_usd", "size"), v=("value_usd", "sum"), w=("weighted", "sum"))
    M["open_" + key] = [dict(key=k, n=int(r.n), v=float(r.v), w=float(r.w)) for k, r in g.iterrows()]

# AE attainment
ae = deals[deals.is_ae & (deals.segment != "Other")]
roster = ae.groupby(["owner", "role", "segment"]).size().reset_index()[["owner", "role", "segment"]]
att = cur_won[cur_won.is_ae].groupby("owner").agg(v=("value_usd", "sum"), n=("value_usd", "size"))
roster = roster.merge(att, left_on="owner", right_index=True, how="left").fillna({"v": 0, "n": 0})
roster["target"] = roster.segment.map(TARGET); roster["att"] = roster.v / roster.target
roster = roster.sort_values("att", ascending=False)
M["ae"] = [dict(owner=r.owner, role=r.role, segment=r.segment, v=float(r.v), n=int(r.n), target=int(r.target), att=float(r.att)) for _, r in roster.iterrows()]

# growth
need = M["scorecard"]["won_v"] * (1 + GROWTH)
june = open_[open_.close_m == NEXT]
M["growth"] = dict(prev_v=M["scorecard"]["prev_won_v"], target_this=M["scorecard"]["prev_won_v"] * (1 + GROWTH), actual=M["scorecard"]["won_v"],
                   change=M["scorecard"]["won_v"] / M["scorecard"]["prev_won_v"] - 1, need_next=need,
                   next_n=len(june), next_v=float(june.value_usd.sum()), next_w=float(june.weighted.sum()),
                   cov_unw=float(june.value_usd.sum() / need), cov_w=float(june.weighted.sum() / need))

# priority and stalled deals
med = open_.groupby("stage").days_in_stage.median()
def risk(r):
    reasons = []
    if pd.notna(r.close_date) and r.close_date < pd.Timestamp("2026-06-01"): reasons.append("close date passed")
    if pd.isna(r.value_usd): reasons.append("no amount")
    m = med.get(r.stage, np.nan)
    if pd.notna(r.days_in_stage) and r.days_in_stage > 60 and (pd.isna(m) or m <= 0 or r.days_in_stage > m * 1.5):
        reasons.append(f"{int(r.days_in_stage)}d in stage" + (f", median {int(m)}" if pd.notna(m) and m > 0 else ""))
    if pd.isna(r.stage_entered): reasons.append("no stage date")
    return "; ".join(reasons)
open_ = open_.copy(); open_["risk"] = open_.apply(risk, axis=1)
pri = open_[open_.close_m.isin([PERIOD, NEXT])].sort_values("weighted", ascending=False).head(15)
cols = ["Opportunity ID", "owner", "region", "segment", "products", "stage", "value_usd", "prob", "weighted", "days_in_stage", "close_date", "risk"]
pri[cols].to_csv(OUT / "priority_deals.csv", index=False)
M["priority"] = json.loads(pri[cols].assign(close_date=pri.close_date.dt.strftime("%d %b")).to_json(orient="records"))
stalled = open_[(open_.risk != "") & open_.value_usd.notna()].sort_values("weighted", ascending=False).head(15)
stalled[cols].to_csv(OUT / "stalled_deals.csv", index=False)
M["stalled"] = json.loads(stalled[cols].assign(close_date=stalled.close_date.dt.strftime("%d %b")).to_json(orient="records"))
M["risk_summary"] = dict(n=int((open_.risk != "").sum()), v=float(open_[open_.risk != ""].value_usd.sum()),
                         past_close=int(open_.risk.str.contains("passed").sum()), no_stage=int(open_.risk.str.contains("no stage").sum()))
# segment win rate Jan-May and lost reason trend
closed = deals[(deals.status != "open") & ~bulk].copy()
closed["m"] = closed.won_m.where(closed.status == "won", closed.lost_m)
seg_wr = {}
for sgm in ["ENT", "MM", "SMB"]:
    sub = closed[closed.segment == sgm]
    seg_wr[sgm] = [float((sub[sub.m == pm].status == "won").mean()) if (sub.m == pm).any() else None for pm in [PERIOD - i for i in range(4, -1, -1)]]
M["seg_wr"] = seg_wr
jan = real_lost[real_lost.lost_m == PERIOD - 4].lost_reason.value_counts()
M["lost_trend"] = {k: [int(jan.get(k, 0)), int(cur_lost.lost_reason.eq(k).sum())] for k in ["Not a priority", "Unresponsive"]}
# lost reasons (real losses, this month)
lr = cur_lost.lost_reason.fillna("Not recorded").value_counts().head(6)
M["lost_reasons"] = [dict(reason=k, n=int(v)) for k, v in lr.items()]
M["bulk_detail"] = dict(n=int(bulk.sum()), smb=int((deals[bulk].segment == "SMB").sum()), created_apr=int((deals[bulk].created.dt.month == 4).sum()),
                        detail=str(deals[bulk].lost_detail.mode().iloc[0])[:160])
M["meta"] = dict(rows=len(raw), deals=len(deals), dup_lines=int(dup), period="May 2026", prev="April 2026", next="June 2026")
json.dump(M, open(OUT / "metrics.json", "w"), indent=1, default=str)
print(json.dumps(M["scorecard"], indent=1)); print(json.dumps(M["growth"], indent=1)); print(M["risk_summary"]); print(M["bulk_detail"])
print(pd.DataFrame(M["trend"]).to_string()); print(pd.DataFrame(M["ae"]).head(20).to_string())
