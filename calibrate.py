"""Calibrated deal ranking. Port of the July Hex workbook, with two fixes:
  1. One row per deal (the Hex version ranked product lines).
  2. A deal's probability is read as it stood on the snapshot date. The Hex version read today's
     probability, which is 0 for deals that have since closed lost, so it flagged dead deals as
     "Salesforce too conservative".

Method, unchanged from Hex:
  - Snapshot: the pipeline as it stood on 31 May 2026, rebuilt from stage entered dates.
  - Training: deals whose final outcome (won or lost) happened on or before 30 April 2026. Nothing
    after the snapshot is used, so there is no look ahead.
  - For each open deal, find historical deals that reached the same stage, matched at the most
    specific level with at least 20 examples: region + segment + type, then region + segment,
    then segment, then stage alone (min 5). Calibrated probability = (wins + 20 x stage prior) /
    (n + 20). Confidence by sample size.
Outputs: out/calibrated_deals.csv, out/vp_queue.csv, and a block in out/metrics.json.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).parent; OUT = ROOT / "out"
SNAP = pd.Timestamp("2026-05-31"); CUTOFF = pd.Timestamp("2026-04-30")
TARGET_START, TARGET_END = pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-30")
PRIOR = 20; MIN_N = 20; MIN_STAGE = 5
STAGE_NAMES = {1: "Meeting booked", 2: "Discovery", 3: "Scoping", 4: "Evaluation", 5: "EB Go/No Go", 6: "Paper Process"}
# Salesforce's own stage probabilities (mode of the open pipeline), used for the snapshot probability
STAGE_PROB = {1: 0.10, 2: 0.20, 3: 0.30, 4: 0.50, 5: 0.75, 6: 0.90}

raw = pd.read_excel(ROOT / "data/deals.xlsx")
money = lambda s: pd.to_numeric(s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
raw["line_usd"] = money(raw["Total Price (converted)"])
first = lambda s: s.iloc[0]
d = raw.groupby("Opportunity ID", sort=False).agg(
    owner=("Opportunity Owner", first), role=("Owner Role", first), account=("Account ID", first), type=("Type", first),
    stage=("Stage", first), prob_now=("Probability (%)", first), close=("Close Date", first), created=("Created Date", first),
    won=("Stage 7W Entered Date", first), lost=("Stage 7L Entered Date", first),
    **{f"s{i}": (f"Stage {i} Entered Date", first) for i in range(1, 7)},
    value=("line_usd", "sum"), products=("Product Name", lambda s: ", ".join(sorted(set(s.dropna())))),
).reset_index()
d.loc[d.value == 0, "value"] = np.nan
d["segment"] = d.role.str.extract(r"(SMB|MM|ENT)")[0].fillna("Other")
d["region"] = d.role.str.extract(r"^(EMEA|AMER)")[0].fillna("Other")

# ---- snapshot stage on SNAP: latest stage entered on or before SNAP, furthest stage breaks ties ----
sd = pd.DataFrame({i: d[f"s{i}"].where(d[f"s{i}"] <= SNAP) for i in range(1, 7)})
latest = sd.max(axis=1)
snap_stage = pd.Series(np.nan, index=d.index)
for i in range(1, 7):
    snap_stage[(sd[i].notna()) & (sd[i] == latest)] = i
won_by = d.won.notna() & (d.won <= SNAP); lost_by = d.lost.notna() & (d.lost <= SNAP)
d["snap_stage"] = snap_stage; d["snap_entered"] = latest
d["snap_status"] = np.select([won_by & (~lost_by | (d.won >= d.lost)), lost_by], ["won", "lost"], "open")
d.loc[d.snap_stage.isna() & (d.snap_status == "open"), "snap_status"] = "unknown"
d["days_in_stage"] = (SNAP - d.snap_entered).dt.days.clip(lower=0)
# fix 2: probability as it stood at the snapshot
d["prob_snap"] = np.where(d.snap_status == "open", d.snap_stage.map(STAGE_PROB), np.nan)
still_open = d.stage.str.match(r"^[1-6]")
cur_stage = pd.to_numeric(d.stage.str.extract(r"^(\d)")[0], errors="coerce")
same = (d.snap_status == "open") & still_open & (cur_stage == d.snap_stage)
d.loc[same, "prob_snap"] = d.loc[same, "prob_now"]

# ---- training set: outcomes on or before CUTOFF ----
outcome_date = pd.concat([d.won, d.lost], axis=1).max(axis=1)
final = np.select([d.won.notna() & (d.lost.isna() | (d.won > d.lost)), d.lost.notna()], ["won", "lost"], None)
import sys
WINDOW_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 90   # default: last 90 days before the cutoff; 0 = all history
win_start = CUTOFF - pd.Timedelta(days=WINDOW_DAYS) if WINDOW_DAYS else pd.Timestamp("2000-01-01")
train = d[(outcome_date <= CUTOFF) & (outcome_date >= win_start) & pd.notna(final) & (d.won != d.lost)].copy()
train["y"] = (final[train.index] == "won").astype(int)
train["odate"] = outcome_date[train.index]
long = []
for i in range(1, 7):
    reached = train[train[f"s{i}"].notna() & (train[f"s{i}"] <= train.odate)]
    long.append(reached.assign(cal_stage=i)[["cal_stage", "region", "segment", "type", "y"]])
long = pd.concat(long)
levels = [["region", "segment", "type"], ["region", "segment"], ["segment"], []]
tables = {tuple(l): long.groupby(["cal_stage"] + l).y.agg(n="size", w="sum").reset_index() for l in levels}
stage_prior = long.groupby("cal_stage").y.mean().to_dict()
overall = long.y.mean()

# ---- target pipeline: open at snapshot, close date in target month or overdue ----
tgt = d[(d.snap_status == "open") & (d.close <= TARGET_END)].copy()
rows = []
for _, r in tgt.iterrows():
    st = int(r.snap_stage); pick = None
    for l in levels:
        t = tables[tuple(l)]
        m = t[t.cal_stage == st]
        for c in l: m = m[m[c] == r[c]]
        if len(m) and m.n.iloc[0] >= (MIN_STAGE if not l else MIN_N):
            pick = (" + ".join(l) if l else "stage only", int(m.n.iloc[0]), int(m.w.iloc[0])); break
    if pick is None: pick = ("all history", len(long), int(long.y.sum()))
    prior = stage_prior.get(st, overall)
    p = (pick[2] + PRIOR * prior) / (pick[1] + PRIOR)
    conf = "High" if pick[1] >= 100 else "Medium" if pick[1] >= 30 else "Low"
    rows.append(dict(oid=r["Opportunity ID"], owner=r.owner, region=r.region, segment=r.segment, type=r.type, products=r.products,
                     stage=STAGE_NAMES[st], days_in_stage=int(r.days_in_stage) if pd.notna(r.days_in_stage) else None, close=r.close,
                     value=r.value, prob_sf=r.prob_snap, prob_cal=round(p, 3), evidence=pick[0], n=pick[1], wins=pick[2], confidence=conf,
                     still_open=bool(still_open[_]), outcome_since=("won" if pd.notna(r.won) and r.won > SNAP else "lost" if pd.notna(r.lost) and r.lost > SNAP else "")))
c = pd.DataFrame(rows)
c["ev_sf"] = c.value * c.prob_sf; c["ev_cal"] = c.value * c.prob_cal
c["gap"] = c.prob_sf - c.prob_cal; c["disagreement"] = (c.value * c.gap.abs())
c["direction"] = np.select([c.gap > 0.10, c.gap < -0.10], ["Salesforce optimistic", "Salesforce conservative"], "Aligned")
med = c.groupby("stage").days_in_stage.median()
c["stale"] = c.days_in_stage > c.stage.map(med) * 1.5
c["overdue"] = c.close < TARGET_START
def question(r):
    if r.overdue: return f"Close date {r.close:%d %b} has passed. What is the new date, and what changed?"
    if r.direction == "Salesforce optimistic": return f"Salesforce says {r.prob_sf:.0%}. Similar deals at {r.stage} won {r.wins} of {r.n} times ({r.prob_cal:.0%}). What makes this one different?"
    if r.stale: return f"{r.days_in_stage} days in {r.stage}, against a median of {med[r.stage]:.0f}. What is the next dated step?"
    if r.direction == "Salesforce conservative": return f"Salesforce says {r.prob_sf:.0%} but similar deals won {r.prob_cal:.0%} of the time. Is it further along than the stage shows?"
    return f"On track at {r.prob_cal:.0%}. Is {r.close:%d %b} still the close date, and who signs?"
c["question"] = c.apply(question, axis=1)
c["attention"] = 0.65 * c.ev_cal.rank(pct=True) * 100 + 0.35 * (c.disagreement.rank(pct=True) * 60 + c.stale * 20 + c.overdue * 20)
c = c.sort_values("attention", ascending=False).reset_index(drop=True); c["rank"] = c.index + 1
c.to_csv(OUT / "calibrated_deals.csv", index=False)
q = c[c.still_open].head(15).copy(); q["rank"] = range(1, len(q) + 1)
q.to_csv(OUT / "vp_queue.csv", index=False)

# ---- summary ----
usd = lambda v: float(v)
summary = dict(
    window_days=WINDOW_DAYS, snapshot=str(SNAP.date()), cutoff=str(CUTOFF.date()), train_n=int(len(train)), train_win_rate=float(train.y.mean()),
    target_n=int(len(c)), target_value=usd(c.value.sum()), ev_sf=usd(c.ev_sf.sum()), ev_cal=usd(c.ev_cal.sum()),
    optimistic_n=int((c.direction == "Salesforce optimistic").sum()), conservative_n=int((c.direction == "Salesforce conservative").sum()),
    optimistic_value=usd(c.loc[c.direction == "Salesforce optimistic", "disagreement"].sum()),
    since_won=int((c.outcome_since == "won").sum()), since_lost=int((c.outcome_since == "lost").sum()),
    # how did calibrated vs Salesforce do on the deals that have since resolved?
    resolved=json.loads(c[c.outcome_since != ""].assign(y=lambda x: (x.outcome_since == "won").astype(int))[["prob_sf", "prob_cal", "y"]].mean().to_json()),
    queue=json.loads(q.assign(close=q.close.dt.strftime("%d %b"))[["rank", "owner", "products", "stage", "value", "prob_sf", "prob_cal", "confidence", "ev_cal", "close", "question", "outcome_since"]].to_json(orient="records")),
)
M = json.load(open(OUT / "metrics.json")); M["calibration"] = summary
json.dump(M, open(OUT / "metrics.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in summary.items() if k != "queue"}, indent=1))
print(q[["rank", "owner", "stage", "value", "prob_sf", "prob_cal", "confidence", "close", "outcome_since"]].to_string())
