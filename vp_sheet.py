"""Pull every check-in call from ElevenLabs and write the VP's pre-meeting sheet.

  export ELEVENLABS_API_KEY=...
  python caller/vp_sheet.py                 # writes caller/out/VP_prep_<date>.xlsx

Sheet 1 "Before the meeting": one row per rep, latest call first. The VP reads this and nothing else.
Sheet 3 "Calls":   every call with its summary, duration and a link to the recording in ElevenLabs.
Salesforce columns (June won, target, gap) come from the same briefs the agent uses, so the
rep's own number sits next to the system's number on one line.
"""
import json, os, re, sys, datetime as dt
import requests
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

API = "https://api.elevenlabs.io/v1/convai"
HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ.get("ELEVENLABS_API_KEY") or sys.exit("Set ELEVENLABS_API_KEY first.")
H = {"xi-api-key": KEY}
state = json.load(open(os.path.join(HERE, "agent_state.json")))
AGENT = state["agent_id"]

FIELDS = ["rep_name", "what_changed", "june_number", "june_commit", "flagged_deals", "salesforce_fixes", "help_needed"]


def rep_numbers(name):
    """June won, target and gap from the rep brief (same source as the agent)."""
    index = json.load(open(os.path.join(HERE, "kb", "rep_index.json")))
    fn = index.get(name) or next((v for k, v in index.items() if k.lower() == str(name).lower()), None)
    if not fn:
        return {}
    txt = open(os.path.join(HERE, "kb", fn)).read()
    out = {}
    m = re.search(r"June so far: won (\d+) deals for \$([\d,]+), which is (\d+)% of the monthly target. Still needed for 100%: \$([\d,]+)", txt)
    if m:
        out = {"june_won_sf": int(m.group(2).replace(",", "")), "june_pct_sf": int(m.group(3)), "june_gap_sf": int(m.group(4).replace(",", ""))}
    m = re.search(r"Closing by 30 June: (\d+) deals, \$([\d,]+) unweighted, \$([\d,]+) weighted", txt)
    if m:
        out.update({"june_pipe_n": int(m.group(1)), "june_pipe_w": int(m.group(3).replace(",", ""))})
    return out


def fetch_calls():
    calls, cursor = [], None
    while True:
        r = requests.get(f"{API}/conversations", headers=H, params={"agent_id": AGENT, "page_size": 100, **({"cursor": cursor} if cursor else {})})
        r.raise_for_status(); j = r.json()
        for c in j["conversations"]:
            d = requests.get(f"{API}/conversations/{c['conversation_id']}", headers=H).json()
            an = d.get("analysis") or {}
            dc = {k: (v or {}).get("value") for k, v in (an.get("data_collection_results") or {}).items()}
            calls.append({
                "id": c["conversation_id"],
                "when": dt.datetime.fromtimestamp((d.get("metadata") or {}).get("start_time_unix_secs", 0)),
                "secs": (d.get("metadata") or {}).get("call_duration_secs", 0),
                "summary": an.get("transcript_summary", ""),
                "link": f"https://elevenlabs.io/app/conversational-ai/history/{c['conversation_id']}",
                **{f: dc.get(f) for f in FIELDS},
            })
        if not j.get("has_more"):
            break
        cursor = j.get("next_cursor")
    return sorted(calls, key=lambda c: c["when"], reverse=True)


def main():
    calls = fetch_calls()
    if not calls:
        sys.exit("No calls yet.")
    wb = Workbook()
    head = Font(bold=True, color="FFFFFF", name="Arial"); fill = PatternFill("solid", fgColor="0B3D91")
    body = Font(name="Arial"); red = PatternFill("solid", fgColor="FDE2E2"); amber = PatternFill("solid", fgColor="FFF4CE")

    def sheet(ws, cols, rows, widths):
        ws.append(cols)
        for c in ws[1]:
            c.font = head; c.fill = fill; c.alignment = Alignment(wrap_text=True, vertical="top")
        for r in rows:
            ws.append(r)
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.font = body; c.alignment = Alignment(wrap_text=True, vertical="top")
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "B2"

    # Sheet 1: latest call per rep. One row, read in ten seconds.
    latest = {}
    for c in calls:
        if c["rep_name"] and c["rep_name"] not in latest:
            latest[c["rep_name"]] = c
    rows = []
    for name, c in sorted(latest.items()):
        sf = rep_numbers(name)
        rows.append([name, c["when"].strftime("%d %b %H:%M"), sf.get("june_won_sf"), sf.get("june_gap_sf"), c["june_number"], c["june_commit"],
                     c["what_changed"], c["flagged_deals"], c["salesforce_fixes"], c["help_needed"], c["link"]])
    ws = wb.active; ws.title = "Before the meeting"
    sheet(ws, ["Rep", "Check-in", "June won (Salesforce)", "Gap to target (Salesforce)", "Rep's June number", "Committed",
               "What changed since last week", "Flagged top-20 deals: next step and date", "Salesforce fixes needed", "Help asked for", "Recording"],
          rows, [20, 13, 14, 14, 14, 12, 50, 50, 35, 35, 40])
    for row in ws.iter_rows(min_row=2):
        try:
            if row[4].value is not None and row[3].value is not None and float(row[4].value) < float(row[3].value):
                row[4].fill = red
        except (TypeError, ValueError):
            pass
        if row[7].value and "no date" in str(row[7].value).lower():
            row[7].fill = amber
        if row[9].value:
            row[9].fill = amber
    for r in range(2, ws.max_row + 1):
        c = ws.cell(r, 11); c.hyperlink = c.value; c.font = Font(name="Arial", color="0563C1", underline="single")

    # Sheet 3: calls
    ws3 = wb.create_sheet("Calls")
    sheet(ws3, ["Rep", "When", "Minutes", "Summary", "Recording"],
          [[c["rep_name"], c["when"].strftime("%d %b %H:%M"), round(c["secs"] / 60, 1), c["summary"], c["link"]] for c in calls],
          [20, 14, 9, 90, 40])
    for r in range(2, ws3.max_row + 1):
        c = ws3.cell(r, 5); c.hyperlink = c.value; c.font = Font(name="Arial", color="0563C1", underline="single")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    fn = os.path.join(HERE, "out", f"VP_prep_{dt.date.today():%Y-%m-%d}.xlsx")
    wb.save(fn); print("wrote", fn, "with", len(latest), "reps and", len(calls), "calls")


if __name__ == "__main__":
    main()
