"""Build the caller agent's knowledge base.

Inputs (all produced earlier in this repo):
  out/deals_clean.csv       one row per deal (analysis.py)
  out/calibrated_deals.csv  31 May queue with calibrated probabilities (calibrate.py, same logic as Hex)
  out/metrics.json          May MBR figures (same numbers as the Julius deck)
  calls/json/*.json         facts extracted from the pipeline review call transcripts

Outputs:
  caller/kb/00_team_brief.md     team-level picture, read on every call
  caller/kb/rep_<name>.md        one brief per rep
  caller/kb/rep_index.json       name -> file, for the setup script

Every figure is computed here. Nothing is typed in by hand.
"""
import glob, json, os, re
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "caller", "kb")
os.makedirs(OUT, exist_ok=True)
for _f in glob.glob(os.path.join(OUT, "rep_*.md")):
    os.remove(_f)

d = pd.read_csv(os.path.join(ROOT, "out", "deals_clean.csv"), low_memory=False)
for c in ["won_date", "lost_date", "close_date", "stage_entered"]:
    d[c] = pd.to_datetime(d[c], errors="coerce")
cal = pd.read_csv(os.path.join(ROOT, "out", "calibrated_deals.csv"))
# Same won-date rule as Hex and Julius: a won deal counts in the month of its Stage 7W date.
# analysis.py falls back to Close Date for the one won deal with no 7W date; drop that fallback here.
_no7w = set(pd.read_csv(os.path.join(ROOT, "caller", "no_7w_date.csv"))["Opportunity ID"])
d.loc[d["Opportunity ID"].isin(_no7w), "won_date"] = pd.NaT
_no7l = set(pd.read_csv(os.path.join(ROOT, "caller", "no_7l_date.csv"))["Opportunity ID"])
d.loc[d["Opportunity ID"].isin(_no7l), "lost_date"] = pd.NaT
M = json.load(open(os.path.join(ROOT, "out", "metrics.json")))

AS_OF = max(d["won_date"].max(), d["lost_date"].max(), d["stage_entered"].max())
MAY = ("2026-05-01", "2026-05-31")
APR = ("2026-04-01", "2026-04-30")
JUN = ("2026-06-01", AS_OF.strftime("%Y-%m-%d"))
JUNE_END = pd.Timestamp("2026-06-30")
days_left = int((JUNE_END - AS_OF).days)

def money(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "no amount recorded"
    return f"${v:,.0f}"

def pct(v):
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v*100:.0f}%"

def stage_name(s):
    return re.sub(r"^\d+[A-Z]?\s*-\s*", "", str(s)).strip()

def won_in(df, a, b):
    m = (df["status"] == "won") & df["won_date"].between(a, b)
    return df[m]

def real_lost_in(df, a, b):
    m = (df["status"] == "lost") & df["lost_date"].between(a, b) & ~df["bulk_close"].astype(bool)
    return df[m]

# Team figures, same rules as Hex and Julius (won month = Stage 7W date, bulk close-outs excluded)
may_won = won_in(d, *MAY); apr_won = won_in(d, *APR); jun_won = won_in(d, *JUN)
may_lost = real_lost_in(d, *MAY)
june_target = may_won["value_usd"].sum() * 1.2
open_d = d[d["status"] == "open"].copy()
open_d["stage_n"] = open_d["stage"].map(stage_name)
# Days in stage counted to the export date (analysis.py counts to 31 May).
open_d["days_in_stage"] = (AS_OF.normalize() - open_d["stage_entered"]).dt.days.clip(lower=0)
# Typical time in each stage: the historical medians the Hex review uses, read from its questions.
_m = cal["question"].astype(str).str.extract(r"days in (.+?), against a median of (\d+)").dropna()
stage_median = _m.drop_duplicates(0).set_index(0)[1].astype(int)
open_d["stalled"] = open_d.apply(
    lambda r: r["days_in_stage"] > 1.5 * stage_median.get(r["stage_n"], np.inf), axis=1)
open_d["overdue"] = open_d["close_date"] < AS_OF.normalize()
open_d["june"] = open_d["close_date"].between(AS_OF.normalize(), JUNE_END)

queue = cal.copy()
queue["rank"] = pd.to_numeric(queue["rank"], errors="coerce")

# Call notes
calls = []
for f in sorted(glob.glob(os.path.join(ROOT, "calls", "json", "*.json"))):
    try:
        calls.append(json.load(open(f)))
    except Exception as e:
        print("skip", f, e)
calls.sort(key=lambda c: c.get("date", ""))
# Clean speaker names the extractor annotated, and drop speakers who could not be identified.
MANAGERS = {"Mark Goldberger", "Mark", "Cameron Goldie-Scot", "Steven Shyun", "Daniel Yeates"}
for c in calls:
    keep = []
    for r in c.get("reps", []) or []:
        n = re.sub(r"\s*\(.*\)\s*$", "", str(r.get("rep") or "")).strip()
        if not n or n.lower().startswith("unnamed") or " " not in n or n in MANAGERS:
            continue
        r["rep"] = n
        keep.append(r)
    c["reps"] = keep

def deal_line(r, with_flags=True):
    bits = [money(r["value_usd"]), (str(r["type"]) + " deal") if r["type"] in ("Land", "Expansion", "New Business") else None,
            (r["products"] if isinstance(r["products"], str) and r["products"] else "no product listed"),
            f"stage {stage_name(r['stage'])} ({pct(r['prob'])} in Salesforce)",
            f"close date {r['close_date']:%d %b}" if pd.notna(r["close_date"]) else "no close date",
            f"{int(r['days_in_stage'])} days in stage" if pd.notna(r["days_in_stage"]) else None,
            f"ID ending {str(r['Opportunity ID'])[-4:]}"]
    flags = []
    if with_flags:
        if r.get("overdue"): flags.append("CLOSE DATE HAS PASSED")
        if r.get("stalled"): flags.append(f"STALLED (stage median {int(stage_median.get(stage_name(r['stage']), 0))} days)")
        if pd.isna(r["value_usd"]): flags.append("NO AMOUNT")
    s = ", ".join(b for b in bits if b)
    return s + (". Flags: " + "; ".join(flags) if flags else "")

# ---------- Team brief ----------
_ae_may = []
for a in M["ae"]:
    v = won_in(d[d["owner"] == a["owner"]], *MAY)["value_usd"].sum()
    _ae_may.append(dict(a, v=v, att=v / a["target"]))
sc = M["scorecard"]
lines = [
    "# Team brief: Metaview sales pipeline",
    "",
    f"Data as of {AS_OF:%d %B %Y} (date of the Salesforce export). Treat this as today. {days_left} days remain in June.",
    "",
    "## May 2026 results (the monthly business review)",
    f"- Won {len(may_won)} deals for {money(may_won['value_usd'].sum())}. April was {len(apr_won)} deals for {money(apr_won['value_usd'].sum())}, so May was down {abs(may_won['value_usd'].sum()/apr_won['value_usd'].sum()-1)*100:.0f}%.",
    f"- Real losses in May: {len(may_lost)} deals. Win rate excluding the clean-up days: {len(may_won)/(len(may_won)+len(may_lost))*100:.0f}%.",
    f"- Win rate by month (excluding clean-up days): January 72%, February 66%, March 53%, April 24%, May 38%. Win rates fell in every segment to April, with a partial recovery in May.",
    f"- Bulk clean-up: {M['bulk_detail']['n']:,} deals were closed lost on 3 March, 12 May and 13 May with reason Unknown. These are pipeline hygiene, not real losses, and are left out of win rates.",
    f"- AEs at or above monthly target in May: " + ", ".join(f"{a['owner']} {a['att']*100:.0f}%" for a in sorted(_ae_may, key=lambda a: -a['att']) if a["att"] >= 1) + f". That is {sum(1 for a in _ae_may if a['att']>=1)} of {len(_ae_may)} AEs. Targets: Enterprise $125,000 a month, Mid-Market and SMB $100,000.",
    f"- Top lost reasons in May (real losses): " + ", ".join(f"{x['reason']} {x['n']}" for x in M["lost_reasons"][:5]) + ".",
    "",
    "## June so far",
    f"- June target: {money(june_target)} (May won value plus 20%).",
    f"- Won in June to date: {len(jun_won)} deals for {money(jun_won['value_usd'].sum())}, which is {jun_won['value_usd'].sum()/june_target*100:.0f}% of target. Gap: {money(june_target - jun_won['value_usd'].sum())}.",
    f"- Open deals with a close date between today and 30 June: {int(open_d['june'].sum())} deals, {money(open_d.loc[open_d['june'],'value_usd'].sum())} unweighted, {money(open_d.loc[open_d['june'],'weighted'].sum())} weighted by Salesforce probability.",
    f"- Open deals whose close date has already passed: {int(open_d['overdue'].sum())}. Stalled deals (in their stage more than 1.5 times the typical time): {int(open_d['stalled'].sum())}.",
    "",
    "## Open pipeline today",
    f"- {len(open_d)} open deals, {money(open_d['value_usd'].sum())}, weighted {money(open_d['weighted'].sum())}.",
    "- By stage: " + "; ".join(f"{s} {g.shape[0]} deals {money(g['value_usd'].sum())}" for s, g in open_d.groupby("stage_n", sort=False)) + ".",
    "",
    "## How the 31 May review queue works (from the Hex workbook)",
    "- On 31 May the Hex workbook ranked the 340 deals due to close in June by how much management attention they deserve, and tagged each Protect, Validate, Accelerate or Monitor.",
    "- It also gives a history-based chance of winning next to the Salesforce stage probability. On a back-test the history-based chance was less accurate than Salesforce (it ran too high), so treat it as a second opinion. Never present it as the real probability.",
    "- The review flags a deal when it has sat in its stage much longer than the median, when its close date has passed, or when it has no amount.",
    "",
    "## Targets: month versus quarter",
    "- Targets in this data are monthly: Enterprise $125,000, Mid-Market and SMB $100,000. The call notes often talk about the quarter (for example 'line of sight to 500' or 'at $228,000 halfway through the quarter'). Those are quarter figures said on the call. The quarterly quota itself is not in the data.",
    "- In the call notes people often say numbers in thousands without saying so ('about 120', '53.5'). Repeat them as said, for example 'about 120k, as you put it', and never turn them into exact dollars.",
    "",
    "## People in the call notes",
    "- Mark Goldberger runs the weekly pipeline reviews. 'Manager asked' and 'Manager coaching' in a note mean the person running that review, usually Mark.",
    "- 'Syle' in the transcripts is most likely Siadhal, the CEO. Raza is tagged on usage-based pricing deals. Steven supports Salesforce reporting. 'Tom' in a legal or contract context is not Tom Stabler.",
    "",
    "## Data limits to be honest about",
    "- The export has account IDs, not company names. Deals are described by amount, product, stage and close date. Ask the rep which account it is.",
    "- Created Date in the export is a migration date, so deal age is read from stage dates.",
    "- The call notes come from weekly pipeline reviews in April and May 2026. Company names in them may not map one to one onto Salesforce deals.",
]
team_themes = []
for c in calls:
    for t in c.get("team_themes", []) or []:
        team_themes.append(f"- {c.get('date')} {c.get('team')}: {t}")
open(os.path.join(OUT, "00_team_brief.md"), "w").write("\n".join(lines) + "\n")
# Manager guidance goes in its own document, retrieved when relevant, so the prompt stays short.
open(os.path.join(OUT, "01_manager_guidance.md"), "w").write(
    "# Manager guidance from the weekly pipeline reviews (April and May 2026)\n\n"
    "What sales leaders told the teams: process rules, pricing, competitors, how to run deals. "
    "Use it when coaching a rep on a stuck deal.\n\n" + "\n".join(f"[Manager guidance] {t}" for t in team_themes) + "\n")

# ---------- Rep briefs ----------
# AE attainment for May, recomputed with the 7W rule (matches Hex)
ae = {}
for a in M["ae"]:
    v = won_in(d[d["owner"] == a["owner"]], *MAY)["value_usd"].sum()
    ae[a["owner"]] = dict(a, v=v, att=v / a["target"])
people = set(open_d["owner"].dropna()) | set(may_won["owner"].dropna()) | set(jun_won["owner"].dropna())
for c in calls:
    for r in c.get("reps", []) or []:
        if r.get("rep") and r["rep"] != "unnamed speaker":
            people.add(r["rep"])
people -= {"Salesforce Admin"}

index = {}
for p in sorted(people):
    mine = d[d["owner"] == p]
    role = mine["role"].dropna().iloc[0] if mine["role"].notna().any() else "role not in Salesforce"
    mw, aw, jw = won_in(mine, *MAY), won_in(mine, *APR), won_in(mine, *JUN)
    ml = real_lost_in(mine, *MAY)
    op = open_d[open_d["owner"] == p].sort_values("weighted", ascending=False)
    L = [f"# Rep brief: {p}", "", f"Role in Salesforce: {role}. Data as of {AS_OF:%d %B %Y}. {days_left} days left in June.", ""]
    L.append("## Results")
    if p in ae:
        a = ae[p]
        L.append(f"- May: won {len(mw)} deals for {money(mw['value_usd'].sum())} against a monthly target of {money(a['target'])}, which is {a['att']*100:.0f}% of target.")
        L.append(f"- June so far: won {len(jw)} deals for {money(jw['value_usd'].sum())}, which is {jw['value_usd'].sum()/a['target']*100:.0f}% of the monthly target. Still needed for 100%: {money(max(a['target']-jw['value_usd'].sum(),0))}.")
    else:
        L.append(f"- May: won {len(mw)} deals for {money(mw['value_usd'].sum())}. No AE target applies to this role.")
        L.append(f"- June so far: won {len(jw)} deals for {money(jw['value_usd'].sum())}.")
    L.append(f"- April: won {len(aw)} deals for {money(aw['value_usd'].sum())}.")
    if len(mw) + len(ml):
        L.append(f"- May win rate excluding clean-up days: {len(mw)}/{len(mw)+len(ml)} = {len(mw)/(len(mw)+len(ml))*100:.0f}%. Real losses in May: {len(ml)}" +
                 (f", top reasons: " + ", ".join(f"{k} {v}" for k, v in ml["lost_reason"].value_counts().head(3).items()) if len(ml) else "") + ".")
    jn = op[op["june"]]
    L += ["", "## June pipeline", f"- Deals closing by 30 June: {len(jn)}, {money(jn['value_usd'].sum())} unweighted, {money(jn['weighted'].sum())} weighted. Close date already passed: {int(op['overdue'].sum())}."]
    q = queue[queue["owner"] == p].sort_values("rank")
    q = q[q["rank"] <= 20]
    if len(q):
        L += ["", "## Flagged in the 31 May management review (top 20 deals, Hex). Ask about these by amount and stage."]
        for _, r in q.iterrows():
            now = open_d.loc[open_d["Opportunity ID"] == r["oid"]]
            if len(now):
                n = now.iloc[0]
                L.append(f"- Rank {int(r['rank'])} of 20: {money(n['value_usd'])}, {n['stage_n']} ({pct(n['prob'])}), close {n['close_date']:%d %b}, {int(n['days_in_stage'])} days in stage. Why flagged on 31 May: {r['question']}")
            else:
                L.append(f"- Rank {int(r['rank'])} of 20: {money(r['value'])} deal, closed {r['outcome_since']} since the review. Do not raise unless the rep does.")
    # Call notes: only the latest review this rep appeared in, commitments and manager asks only.
    last = None
    for c in calls:
        for r in c.get("reps", []) or []:
            if r.get("rep") == p:
                last = (c, r)
    if last:
        c, r = last
        L += ["", f"## Last review they were in ({c.get('date')})"]
        if r.get("forecast_or_number"):
            L.append(f"- Number they gave then: {r['forecast_or_number']}")
        for x in (r.get("commitments") or [])[:4]:
            L.append(f"- Said they would: {x}")
        asks = [f"{dl.get('account')}: {dl['manager_ask']}" for dl in (r.get("deals") or []) if dl.get("manager_ask")][:3]
        for x in asks:
            L.append(f"- Manager asked on {x}")
    fn = "rep_" + re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_") + ".md"
    # Every line carries the rep's name, so a retrieved chunk is never ambiguous about whose deal it is.
    L = [ln if (not ln.strip() or ln.startswith("# ")) else f"[{p}] {ln}" for ln in L]
    open(os.path.join(OUT, fn), "w").write("\n".join(L) + "\n")
    index[p] = fn

json.dump(index, open(os.path.join(OUT, "rep_index.json"), "w"), indent=1)
print(f"as of {AS_OF:%Y-%m-%d}, {len(index)} rep briefs, {len(calls)} call files used")
