"""Builds review/index.html from out/metrics.json. Same numbers as the deck, one page, inline SVG charts."""
import json, html
from pathlib import Path
ROOT = Path(__file__).parent
M = json.load(open(ROOT / "out/metrics.json"))
sc, g, t, cal = M["scorecard"], M["growth"], M["trend"], M.get("calibration", {})
esc = html.escape
usd = lambda v: f"${v/1e6:.2f}M" if v >= 1e6 else f"${v/1e3:.0f}k" if v >= 1e4 else f"${v/1e3:.1f}k" if v >= 1e3 else f"${v:.0f}"
pct = lambda v: f"{'+' if v >= 0 else ''}{round(v*100)}%"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
mlabel = lambda m: MON[int(m[5:7]) - 1] + " " + m[2:4]

# ---------- SVG helpers (values in k USD unless noted) ----------
def grouped_bars(groups, series, colors, w=760, h=300, unit="$k", legend=True):
    """groups: list of labels; series: list of (name, [values]); one scale."""
    pad_l, pad_r, pad_t, pad_b = 48, 12, 28 if legend else 12, 36
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    mx = max(max(v) for _, v in series) or 1
    step = 10 ** (len(str(int(mx))) - 1); step = step * (1 if mx / step <= 5 else 2) if mx / step <= 10 else step * 2
    top = (int(mx / step) + 1) * step
    gw = pw / len(groups); bw = min(28, (gw * 0.8) / len(series)); gap = 2
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart">']
    y = lambda v: pad_t + ph - v / top * ph
    k = 0
    while k <= top:
        out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{y(k):.1f}" y2="{y(k):.1f}" class="grid"/><text x="{pad_l-6}" y="{y(k)+4:.1f}" class="tick" text-anchor="end">{k:,.0f}</text>')
        k += step
    for gi, gl in enumerate(groups):
        x0 = pad_l + gi * gw + (gw - (bw + gap) * len(series)) / 2
        for si, (name, vals) in enumerate(series):
            v = vals[gi]; x = x0 + si * (bw + gap); hh = max(0, y(0) - y(v))
            out.append(f'<rect x="{x:.1f}" y="{y(v):.1f}" width="{bw:.1f}" height="{hh:.1f}" rx="3" fill="{colors[si]}"><title>{esc(name)}, {esc(gl)}: {v:,.0f}{unit}</title></rect>')
        out.append(f'<text x="{pad_l + gi*gw + gw/2:.1f}" y="{h-pad_b+16}" class="tick" text-anchor="middle">{esc(gl)}</text>')
    if legend:
        lx = pad_l
        for si, (name, _) in enumerate(series):
            out.append(f'<rect x="{lx}" y="6" width="10" height="10" rx="2" fill="{colors[si]}"/><text x="{lx+14}" y="15" class="tick">{esc(name)}</text>'); lx += 14 + 7 * len(name) + 18
    out.append("</svg>"); return "".join(out)

def hbars(labels, vals, color, w=760, fmt=lambda v: f"{v:,.0f}", unit="", h_row=26, colors=None, maxv=None):
    pad_l = 170; pad_r = 70; h = h_row * len(labels) + 10
    mx = maxv or max(vals) or 1; pw = w - pad_l - pad_r
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart">']
    for i, (l, v) in enumerate(zip(labels, vals)):
        y = 5 + i * h_row; bw = v / mx * pw; c = (colors[i] if colors else color)
        out.append(f'<text x="{pad_l-8}" y="{y+h_row/2+4}" class="tick" text-anchor="end">{esc(l[:26])}</text><rect x="{pad_l}" y="{y+4}" width="{bw:.1f}" height="{h_row-8}" rx="3" fill="{c}"><title>{esc(l)}: {fmt(v)}{unit}</title></rect><text x="{pad_l+bw+6:.1f}" y="{y+h_row/2+4}" class="val">{fmt(v)}{unit}</text>')
    out.append("</svg>"); return "".join(out)

def lines(labels, series, colors, w=760, h=280, ymax=80, unit="%"):
    pad_l, pad_r, pad_t, pad_b = 40, 80, 28, 30; pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    y = lambda v: pad_t + ph - v / ymax * ph; x = lambda i: pad_l + i * pw / (len(labels) - 1)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart">']
    for k in range(0, ymax + 1, 20):
        out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{y(k):.1f}" y2="{y(k):.1f}" class="grid"/><text x="{pad_l-6}" y="{y(k)+4:.1f}" class="tick" text-anchor="end">{k}{unit}</text>')
    for i, l in enumerate(labels): out.append(f'<text x="{x(i):.1f}" y="{h-pad_b+16}" class="tick" text-anchor="middle">{l}</text>')
    lx = pad_l
    for si, (name, vals) in enumerate(series):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals) if v is not None)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{colors[si]}" stroke-width="2.5" stroke-linejoin="round"/>')
        for i, v in enumerate(vals):
            if v is None: continue
            out.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4.5" fill="{colors[si]}" class="dot"><title>{esc(name)}, {labels[i]}: {v:.0f}{unit}</title></circle>')
        out.append(f'<rect x="{lx}" y="6" width="10" height="10" rx="2" fill="{colors[si]}"/><text x="{lx+14}" y="15" class="tick">{esc(name)}</text>'); lx += 14 + 7 * len(name) + 18
    # end labels, spread so they do not overlap
    ends = sorted([(([v for v in vals if v is not None][-1]), name) for name, vals in series], reverse=True)
    ys = [y(v) for v, _ in ends]
    for i in range(1, len(ys)):
        if ys[i] - ys[i-1] < 14: ys[i] = ys[i-1] + 14
    for (v, name), yy in zip(ends, ys):
        out.append(f'<text x="{w-pad_r:.1f}" y="{yy+4:.1f}" class="val" text-anchor="end">{esc(name)} {v:.0f}{unit}</text>')
    out.append("</svg>"); return "".join(out)

C = dict(a="var(--s1)", b="var(--s2)", c="var(--s3)", d="var(--s4)", g="var(--muted)", good="var(--good)", warn="var(--warn)", bad="var(--bad)")
seg = {r["key"]: r for r in M["segment"]}; reg = {r["key"]: r for r in M["region"]}
stg = M["stages"]; ae = M["ae"]; pr = M["products"]
wr = M["seg_wr"]; lt = M["lost_trend"]
hit = sum(a["att"] >= 1 for a in ae); near = sum(0.9 <= a["att"] < 1 for a in ae)
queue = cal.get("queue", [])

def card(title, body, note=""):
    return f'<section class="card"><h2>{esc(title)}</h2>{body}{f"<p class=note>{note}</p>" if note else ""}</section>'
def stat(label, value, sub, cls=""):
    return f'<div class="stat"><div class="l">{esc(label)}</div><div class="v {cls}">{esc(value)}</div><div class="s">{esc(sub)}</div></div>'
def table(headers, rows, cls=""):
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'

parts = []
parts.append(f'''<header><p class="eyebrow">Metaview · Monthly Business Review · May 2026</p>
<h1>May in one line: fewer, bigger deals, and a win rate a third of January's</h1>
<p class="lede">Pre-read for the June MBR. Built from the Salesforce export, Jan 2025 to May 2026, counted one row per deal. Prepared by Jai Singhal.</p></header>''')
parts.append('<div class="stats">' + stat("Won in May", usd(sc["won_v"]), f'{sc["won_n"]} deals, {pct(g["change"])} vs April') + stat("Win rate", f'{round(sc["win_rate"]*100)}%', f'{round(t[7]["win_rate"]*100)}% in January', "bad") + stat("Average won deal", usd(sc["avg_won"]), f'{usd(sc["prev_won_v"]/sc["prev_won_n"])} in April', "good") + stat("June coverage", f'{g["cov_w"]:.1f}x weighted', f'{usd(g["next_w"])} against {usd(g["need_next"])} needed', "good") + '</div>')
parts.append(card("What May says", f'''<ul class="bul">
<li><b>Growth.</b> May won {usd(sc["won_v"])}, down {round(-g["change"]*100)}% on April. The 20% growth target was {usd(g["target_this"])}. Missed.</li>
<li><b>Conversion.</b> The win rate has fallen from {round(t[7]["win_rate"]*100)}% in January to {round(sc["win_rate"]*100)}% in May, in every segment. Real lost deals, not the data clean-up.</li>
<li><b>Mix.</b> Deals are bigger. Mid-market and enterprise grew, SMB fell {round(-seg["SMB"]["change"]*100)}% with a {round(seg["SMB"]["win_rate"]*100)}% win rate.</li>
<li><b>June.</b> {usd(g["next_w"])} of weighted pipeline closes in June against {usd(g["need_next"])} needed for 20% growth. Coverage is fine. Conversion is the risk.</li></ul>''',
"A one-prompt analysis of the same file counted product lines as deals and reported May won at $3.25M, up 29%. The next section explains."))
parts.append(card("Before the numbers: three things in the export that change the story", f'''<div class="fixes">
<div><span class="n">1</span><h3>One row per product, not per deal</h3><p>{M["meta"]["rows"]:,} rows are {M["meta"]["deals"]:,} deals. A deal with four products appears four times with the full amount on each row. Counting rows gives May won of $3.25M. Counting deals gives {usd(sc["won_v"])}. The first analysis said growth was up 29%. It is down {round(-g["change"]*100)}%.</p></div>
<div><span class="n">2</span><h3>A bulk close-out on 13 May</h3><p>{M["bulk_detail"]["n"]:,} deals were closed lost on one day, 83% with reason Unknown and the note "no email or call activity found". {M["bulk_detail"]["smb"]:,} are SMB. This is pipeline hygiene, not May performance. Kept, flagged, shown separately. Without it May still has {sc["lost_n"]} real losses.</p></div>
<div><span class="n">3</span><h3>Created dates are a migration date</h3><p>Every deal, including ones closed in 2025, has a created date in April or May 2026. The pipeline was loaded into Salesforce then. Deal age uses stage entered dates instead; 1,134 of 1,137 open deals have one.</p></div></div>'''))
labels = [mlabel(x["month"]) for x in t]
parts.append(card("Won value has plateaued since February while real losses have kept rising",
    grouped_bars(labels, [("Won", [x["won_v"]/1e3 for x in t]), ("Lost", [x["lost_v"]/1e3 for x in t]), ("Bulk close-out, 13 May", [x["bulk_v"]/1e3 for x in t])], [C["a"], C["b"], C["g"]]),
    f'USD thousands. Won value {usd(t[8]["won_v"])} in Feb, {usd(t[9]["won_v"])}, {usd(t[10]["won_v"])}, {usd(sc["won_v"])} in May. Won count {t[8]["won_n"]} in Feb to {sc["won_n"]} in May. Real losses {t[8]["lost_n"]} to {sc["lost_n"]}. Losses before the April migration may be under-recorded, which would flatter early-2026 rates; the direction since February is not in doubt.'))
parts.append(card("The win rate has fallen in every segment since January, with no recovery in May",
    lines(["Jan", "Feb", "Mar", "Apr", "May"], [(k, [None if v is None else v*100 for v in wr[k]]) for k in ["ENT", "MM", "SMB"]], [C["d"], C["a"], C["b"]]) +
    f'<p class="inline">Why deals are lost in May, real losses: ' + ", ".join(f'{esc(r["reason"])} {r["n"]}' for r in M["lost_reasons"]) + f'. "Not a priority" went from {lt["Not a priority"][0]} in January to {lt["Not a priority"][1]} in May, "Unresponsive" from {lt["Unresponsive"][0]} to {lt["Unresponsive"][1]}. A qualification and follow-up problem, not a pricing one.</p>',
    "Win rate = won / (won + lost) by month closed, AE roles, bulk close-out excluded."))
rg = [reg[k] for k in ["AMER", "EMEA"]]; sg = [seg[k] for k in ["ENT", "MM", "SMB"]]
parts.append(card("EMEA and mid-market carried May. AMER and SMB fell",
    '<div class="two">' + grouped_bars([r["key"] for r in rg], [("April", [r["pv"]/1e3 for r in rg]), ("May", [r["v"]/1e3 for r in rg])], [C["g"], C["a"]], w=370, h=260) + grouped_bars([r["key"] for r in sg], [("April", [r["pv"]/1e3 for r in sg]), ("May", [r["v"]/1e3 for r in sg])], [C["g"], C["a"]], w=370, h=260) + '</div>' +
    table(["", "Won", "Deals", "vs April", "Win rate"], [[esc(r["key"]), usd(r["v"]), int(r["n"]), f'<span class="{"bad" if r["change"]<0 else "good"}">{pct(r["change"])}</span>', f'{round(r["win_rate"]*100)}%'] for r in rg + sg]),
    f'Other (Admin, Engagement, CEO owned) won {usd(reg["Other"]["v"])} in May, down from {usd(reg["Other"]["pv"])}, and is left off the charts.'))
parts.append(card("Sourcing Max and Application Review drove May. Application Review is new",
    hbars([p["name"].replace(" - Annual", "") for p in pr], [p["v"]/1e3 for p in pr], C["a"], fmt=lambda v: f"${v:,.0f}k"),
    f'{pr[0]["name"]}: {usd(pr[0]["v"])} across {pr[0]["deals"]} deals, {pct(pr[0]["change"])} vs April. {pr[1]["name"]}: {usd(pr[1]["v"])} from {pr[1]["deals"]} deals, {pct(pr[1]["change"])}. All {M["product_coverage"]["won_total"]} won deals in May carry a product name. Product value is the converted line total per product, so a multi-product deal is split across them.'))
parts.append(card(f'{usd(sc["open_v"])} open, {usd(sc["open_w"])} weighted. Half of it sits in Discovery',
    grouped_bars([s["stage"] for s in stg], [("Open value", [s["v"]/1e3 for s in stg]), ("Weighted", [s["w"]/1e3 for s in stg])], [C["a"], C["d"]]),
    f'{stg[1]["n"]} deals and {usd(stg[1]["v"])} in Discovery at 20%. Late stage, EB Go/No Go and Paper Process: {stg[4]["n"]+stg[5]["n"]} deals, {usd(stg[4]["v"]+stg[5]["v"])} open, {usd(stg[4]["w"]+stg[5]["w"])} weighted. EMEA holds {round(next(x for x in M["open_region"] if x["key"]=="EMEA")["v"]/sc["open_v"]*100)}% of open value; mid-market {round(next(x for x in M["open_segment"] if x["key"]=="MM")["v"]/sc["open_v"]*100)}%.'))
parts.append(card(f'{hit} of {len(ae)} AEs hit their May target. {near} more within 10%',
    hbars([a["owner"] for a in ae], [a["att"]*100 for a in ae], None, fmt=lambda v: f"{v:.0f}", unit="%", colors=[C["good"] if a["att"] >= 1 else C["warn"] if a["att"] >= 0.5 else C["bad"] for a in ae], maxv=160) +
    '<p class="inline"><span class="sw good"></span> at or above target <span class="sw warn"></span> 50 to 99% <span class="sw bad"></span> under 50%</p>',
    f'Targets: ENT $125k, MM and SMB $100k a month, full month, AE roles only. The row-counted version showed 9 of 20 at target and a top AE at 798%. Neither is true.'))
parts.append(card("20% growth: missed in May, covered for June, if conversion holds",
    '<div class="stats three">' + stat("May target, April + 20%", usd(g["target_this"]), f'Actual {usd(g["actual"])}, {pct(g["change"])}', "bad") + stat("June needs, May + 20%", usd(g["need_next"]), f'{g["next_n"]} deals due to close in June') + stat("June pipeline", usd(g["next_v"]), f'{usd(g["next_w"])} weighted, {g["cov_w"]:.1f}x coverage', "good") + '</div>' +
    hbars(["June needed", "June weighted", "June unweighted"], [g["need_next"]/1e3, g["next_w"]/1e3, g["next_v"]/1e3], None, fmt=lambda v: f"${v:,.0f}k", colors=[C["bad"], C["good"], C["a"]], h_row=30),
    f'Weighted coverage of {g["cov_w"]:.1f}x is healthy on paper, but the May win rate was {round(sc["win_rate"]*100)}% and stage probabilities assume far more. At May conversion, {usd(g["next_v"])} of pipeline yields about {usd(g["next_v"]*sc["win_rate"])}. The gap closes only if the {stg[4]["n"]+stg[5]["n"]} late-stage deals close as scheduled. June is a conversion target, not a pipeline-generation target.'))
if queue:
    rows = [[q["rank"], esc(q["owner"]), esc((q["products"] or "No product listed").replace(" - Annual", "")[:40]), esc(q["stage"]), usd(q["value"] or 0), f'{round((q["prob_sf"] or 0)*100)}%', f'{round(q["prob_cal"]*100)}%', esc(q["confidence"]), esc(q["close"]), esc(q["question"])] for q in queue]
    parts.append(card("The fifteen deals the VP should ask about, with the question for each",
        table(["#", "Owner", "Products", "Stage", "Value", "Salesforce", "History says", "Confidence", "Close", "The question"], rows, "queue"),
        f'Open deals closing by 30 June as of the 31 May snapshot, ranked by expected value and attention need. "History says" is the win rate of deals that reached the same stage in the same region and segment over the 90 days before May, smoothed toward the stage average ({cal.get("train_n", 0):,} training outcomes). Calibrated probabilities run high against what has happened since the snapshot ({cal.get("since_won",0)} won, {cal.get("since_lost",0)} lost of {cal.get("since_won",0)+cal.get("since_lost",0)} resolved), because 2025 history is rosier than 2026. Treat them as a conversation starter, not a forecast. Method ported from the July Hex workbook, one row per deal.'))
parts.append(card("Three findings, three actions", f'''<div class="fa">
<div><h3>Conversion, not coverage, is the problem</h3><p class="f">Win rate {round(t[7]["win_rate"]*100)}% in January to {round(sc["win_rate"]*100)}% in May, in every segment. "Not a priority" and "Unresponsive" are the growing loss reasons.</p><p class="a">Run a loss review on the 50 largest real losses of April and May. Decide whether this is qualification at Meeting booked or follow-up after Discovery. Owner: VP Sales, by the next MBR.</p></div>
<div><h3>SMB is where the volume went missing</h3><p class="f">SMB won {usd(seg["SMB"]["v"])}, {pct(seg["SMB"]["change"])}, at a {round(seg["SMB"]["win_rate"]*100)}% win rate, while {M["bulk_detail"]["smb"]:,} SMB deals were bulk closed with no activity logged.</p><p class="a">Set an activity rule: no SMB deal sits in Discovery past 30 days without a logged touch. Review the inbound to SMB handoff. Owner: SMB leads, EMEA and AMER.</p></div>
<div><h3>Mid-market and enterprise are working</h3><p class="f">MM {pct(seg["MM"]["change"])}, ENT {pct(seg["ENT"]["change"])}, average deal {usd(sc["avg_won"])}. Application Review {pct(pr[1]["change"])}.</p><p class="a">Protect the {stg[4]["n"]+stg[5]["n"]} late-stage deals ({usd(stg[4]["v"]+stg[5]["v"])}): weekly check on the top 15, exec sponsor on every EB Go/No Go. Owner: MM and ENT leads.</p></div></div>''',
    "Fourth, for Ops: backfill stage entered dates for closed deals from the Salesforce audit trail and require a product on every open deal. Both are free and both make the next MBR sharper."))
parts.append(card("Method and data quality", f'''<ul class="bul small">
<li>Source: Salesforce export, {M["meta"]["rows"]:,} rows, {M["meta"]["deals"]:,} deals, Jan 2025 to May 2026. Reporting period May 2026, compared with April.</li>
<li>Deal value: sum of Total Price (converted) across a deal's product lines, in USD. Equals Amount for USD deals and converts the 46 EUR and GBP deals.</li>
<li>Won and lost month: Stage 7W or 7L entered date, Close Date where missing (4 deals).</li>
<li>Bulk close-out: {sc["bulk_n"]:,} deals lost on 13 May, 83% reason Unknown, no activity found. All flagged and excluded from rates.</li>
<li>Win rate: won / (won + lost) by month closed. Weighted pipeline: value times stage probability.</li>
<li>AE attainment: ENT $125k, MM and SMB $100k, full monthly target, AE roles only.</li>
<li>Known gaps: 1,172 rows with no amount, 93% of rows with no product name, 22% with no stage entered date (nearly all closed deals), created dates are migration dates.</li>
<li>Reproducible: <code>analysis.py</code> and <code>calibrate.py</code> rebuild every number here from the export in one run. <code>deck.js</code> builds the slide version. The same metrics file feeds both, so they cannot disagree.</li></ul>'''))

page = f'''<title>Metaview MBR May 2026</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one column of cards, read top to bottom like the deck; stat tiles only where the number is the point. */
:root{{--bg:#0b0f14;--panel:#121820;--line:#243040;--fg:#e8edf3;--muted:#8b97a7;--accent:#22d3ee;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#9085e9;--good:#2fa84f;--warn:#c98500;--bad:#e66767;--grid:#1f2937;
--sans:"IBM Plex Sans",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,monospace;color-scheme:dark}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#f6f8fa;--panel:#fff;--line:#d7dee8;--fg:#0f172a;--muted:#5b6778;--accent:#0891b2;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#6250d6;--good:#008300;--warn:#b45309;--bad:#e34948;--grid:#e5e7eb;color-scheme:light}}}}
:root[data-theme="light"]{{--bg:#f6f8fa;--panel:#fff;--line:#d7dee8;--fg:#0f172a;--muted:#5b6778;--accent:#0891b2;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#6250d6;--good:#008300;--warn:#b45309;--bad:#e34948;--grid:#e5e7eb;color-scheme:light}}
body{{background:var(--bg);color:var(--fg);font-family:var(--sans);margin:0;padding-block:28px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));line-height:1.5}}
.wrap{{max-width:980px;margin:0 auto;display:flex;flex-direction:column;gap:18px}}
.eyebrow{{font-family:var(--mono);font-size:12px;letter-spacing:.08em;color:var(--accent);margin:0 0 8px}}
h1{{font-size:clamp(24px,3.2vw,36px);font-weight:600;margin:0 0 8px;letter-spacing:-.01em;text-wrap:balance}}
.lede{{color:var(--muted);margin:0;max-width:70ch}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
.stats.three{{margin-bottom:12px}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.stat .l{{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}}
.stat .v{{font-size:28px;font-weight:600;margin:4px 0 2px;font-variant-numeric:tabular-nums}}
.stat .v.good{{color:var(--good)}}.stat .v.bad{{color:var(--bad)}}
.stat .s{{font-size:12px;color:var(--muted)}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px 22px;min-width:0}}
.card h2{{font-size:19px;font-weight:600;margin:0 0 14px;text-wrap:balance}}
.card h3{{font-size:15px;font-weight:600;margin:0 0 6px}}
.note{{color:var(--muted);font-size:13px;margin:12px 0 0;max-width:80ch}}
.inline{{font-size:13px;color:var(--fg);margin:10px 0 0}}
.bul{{margin:0;padding-left:20px}}.bul li{{margin:6px 0}}.bul.small{{font-size:13px;color:var(--muted)}}
.chart{{width:100%;height:auto;display:block;overflow:visible}}
.grid{{stroke:var(--grid);stroke-width:1}}.tick{{fill:var(--muted);font-size:11px;font-family:var(--sans)}}.val{{fill:var(--fg);font-size:11px;font-family:var(--sans)}}
.dot{{stroke:var(--panel);stroke-width:2}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-bottom:12px}}
.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:var(--muted);font-weight:500;font-size:12px}}
table.queue{{font-size:12px;min-width:900px}}table.queue td:last-child{{max-width:320px}}
.good{{color:var(--good)}}.bad{{color:var(--bad)}}
.sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}}.sw.good{{background:var(--good)}}.sw.warn{{background:var(--warn)}}.sw.bad{{background:var(--bad)}}
.fixes,.fa{{display:grid;gap:12px}}
.fixes>div,.fa>div{{border:1px solid var(--line);border-radius:10px;padding:14px 16px;position:relative}}
.fixes .n{{font-family:var(--mono);color:var(--accent);font-size:22px;font-weight:600;display:block;margin-bottom:4px}}
.fixes p,.fa p{{margin:0;font-size:13.5px;color:var(--muted)}}
.fa .f{{color:var(--fg)}}.fa .a::before{{content:"Action: ";color:var(--accent);font-weight:600}}.fa .a{{margin-top:6px;color:var(--fg)}}
code{{font-family:var(--mono);font-size:12px;background:var(--bg);padding:1px 5px;border-radius:4px}}
@media (min-width:760px){{.fixes,.fa{{grid-template-columns:1fr 1fr 1fr}}}}
</style>
<div class="wrap">{"".join(parts)}</div>'''
Path(ROOT / "review").mkdir(exist_ok=True)
(ROOT / "review/index.html").write_text(page)
print("ok", len(page))
