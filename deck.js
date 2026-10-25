const pptxgen = require("pptxgenjs");
const fs = require("fs");
const { applyTheme } = require("/root/.claude/skills/synced/dac4eedf-15c3-4e65-aa15-a92c1fe4cf97_7e976be3-4b44-46b9-a910-37821a9d990f/pptx/scripts/apply_theme.js");
const M = JSON.parse(fs.readFileSync(__dirname + "/out/metrics.json"));

const THEME = { name: "Metaview Dark", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "F3F4F6", lt1: "0B0F14", dk2: "9CA3AF", lt2: "161B22", accent1: "22D3EE", accent2: "22C55E", accent3: "F87171", accent4: "A5B4FC", accent5: "F59E0B", accent6: "6B7280", hlink: "22D3EE", folHlink: "A5B4FC" } };
const H = THEME.colors;
const pres = new pptxgen(); pres.layout = "LAYOUT_WIDE"; pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };
pres.author = "Jai Singhal"; pres.title = "Metaview Monthly Business Review, May 2026";
const C = pres.SchemeColor;
const W = 13.33, FOOT = "Metaview MBR, May 2026 | Prepared by Jai Singhal | Source: Salesforce export, one row per deal";

pres.defineSlideMaster({ title: "TITLE", background: { color: H.lt1 }, objects: [
  { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 2.1, w: 11.9, h: 1.3, fontSize: 44, bold: true, color: C.text1, margin: 0 } } },
  { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 3.5, w: 11.9, h: 1.6, fontSize: 18, color: C.text2, margin: 0 } } } ] });
pres.defineSlideMaster({ title: "CONTENT", background: { color: H.lt1 }, margin: [0.5, 0.5, 0.9, 0.5], objects: [
  { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.35, w: 12.3, h: 0.8, fontSize: 28, bold: true, color: C.text1, margin: 0, valign: "top" } } },
  { text: { text: FOOT, options: { x: 0.5, y: 7.05, w: 10.5, h: 0.3, fontSize: 9, color: C.text2, margin: 0 } } },
  { slideNumber: { x: 12.3, y: 7.05, w: 0.6, h: 0.3, fontSize: 9, color: H.dk2 } } ] });

const usd = v => v >= 1e6 ? "$" + (v / 1e6).toFixed(2) + "M" : v >= 1e4 ? "$" + Math.round(v / 1e3) + "k" : v >= 1e3 ? "$" + (v / 1e3).toFixed(1) + "k" : "$" + Math.round(v);
const pct = v => (v >= 0 ? "+" : "") + Math.round(v * 100) + "%";
const chartBase = { chartColors: [H.accent1], catAxisLabelColor: H.dk2, valAxisLabelColor: H.dk2, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  valGridLine: { color: "1F2937", size: 0.5 }, catGridLine: { style: "none" }, dataLabelColor: H.dk1, dataLabelFontSize: 9, legendColor: H.dk2, legendFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", titleFontFace: "+mn-lt", showTitle: false, plotArea: { fill: { color: H.lt1 } } };
const card = (s, x, y, w, h) => s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: C.background2 }, line: { color: "1F2937", width: 0.5 }, rectRadius: 0.08 });
const stat = (s, x, y, w, label, value, sub, color) => { card(s, x, y, w, 1.35);
  s.addText(label.toUpperCase(), { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: 0.3, fontSize: 9, color: C.text2, margin: 0, isTextBox: true, charSpacing: 1 });
  s.addText(value, { x: x + 0.2, y: y + 0.4, w: w - 0.4, h: 0.55, fontSize: 26, bold: true, color: color || C.accent1, margin: 0, isTextBox: true });
  if (sub) s.addText(sub, { x: x + 0.2, y: y + 0.95, w: w - 0.4, h: 0.3, fontSize: 10, color: C.text2, margin: 0, isTextBox: true }); };
const note = (s, text, y = 6.35, h = 0.6) => s.addText(text, { x: 0.5, y, w: 12.3, h, fontSize: 12, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
const bullets = (s, items, x, y, w, h, size = 14) => s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 8 } })), { x, y, w, h, fontSize: size, color: C.text1, margin: 0, isTextBox: true, valign: "top" });

const sc = M.scorecard, g = M.growth, t = M.trend;
// 1 Title
pres.addSection({ title: "Summary" });
let s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Summary" });
s.addText("Monthly Business Review", { placeholder: "title" });
s.addText([{ text: "May 2026. Pre-read for the June MBR.\n", options: { color: H.dk1 } }, { text: "Prepared by Jai Singhal from the Salesforce export, Jan 2025 to May 2026, counted one row per deal.", options: {} }], { placeholder: "body" });
s.addShape(pres.ShapeType.ellipse, { x: 0.7, y: 1.3, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { color: C.accent1 } });

// 2 Headline
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Summary" });
s.addText("May in one line: fewer, bigger deals, and a win rate a third of January\u2019s", { placeholder: "title" });
stat(s, 0.5, 1.4, 2.95, "Won in May", usd(sc.won_v), `${sc.won_n} deals, ${pct(g.change)} vs April`, H.dk1);
stat(s, 3.6, 1.4, 2.95, "Win rate", Math.round(sc.win_rate * 100) + "%", `${Math.round(t[7].win_rate * 100)}% in January`, H.accent3);
stat(s, 6.7, 1.4, 2.95, "Average won deal", usd(sc.avg_won), `${usd(sc.prev_won_v / sc.prev_won_n)} in April`, H.accent2);
stat(s, 9.8, 1.4, 2.95, "June coverage", g.cov_w.toFixed(1) + "x weighted", `${usd(g.next_w)} against ${usd(g.need_next)} needed`, H.accent2);
bullets(s, [
  `Growth: May won ${usd(sc.won_v)}, down ${Math.round(-g.change * 100)}% on April. The 20% growth target was ${usd(g.target_this)}. Missed.`,
  `Conversion: the win rate has fallen from ${Math.round(t[7].win_rate * 100)}% in January to ${Math.round(sc.win_rate * 100)}% in May, in every segment. Real lost deals, not the data clean-up.`,
  `Mix: deals are bigger. Mid-market and enterprise grew, SMB fell ${Math.round(-M.segment.find(x => x.key == "SMB").change * 100)}% with a ${Math.round(M.segment.find(x => x.key == "SMB").win_rate * 100)}% win rate.`,
  `June: ${usd(g.next_w)} of weighted pipeline closes in June against ${usd(g.need_next)} needed for 20% growth. Coverage is fine. Conversion is the risk.`,
], 0.5, 3.1, 12.3, 3.1, 15);
note(s, "Numbers count each deal once. A one-prompt analysis of the same file counted product lines as deals and reported May won at $3.25M, up 29%. See the next page.");

// 3 Data fixes
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Summary" });
s.addText("Before the numbers: three things in the export that change the story", { placeholder: "title" });
const fixes = [
  ["One row per product, not per deal", `${M.meta.rows.toLocaleString()} rows are ${M.meta.deals.toLocaleString()} deals. A deal with four products appears four times with the full amount on each row.`, `Counting rows gives May won of $3.25M. Counting deals gives ${usd(sc.won_v)}. The first analysis said growth was up 29%. It is down ${Math.round(-g.change * 100)}%.`],
  ["A bulk close-out on 13 May", `${M.bulk_detail.n.toLocaleString()} deals were closed lost on one day. 83% carry reason Unknown and the note "no email or call activity found". ${M.bulk_detail.smb.toLocaleString()} are SMB.`, `This is pipeline hygiene, not May performance. Kept, flagged, and shown separately. Without it May still has ${sc.lost_n} real losses.`],
  ["Created dates are a migration date", "Every deal, including ones closed in 2025, has a created date in April or May 2026. The pipeline was loaded into Salesforce then.", "Deal age uses stage entered dates instead. 1,134 of 1,137 open deals have one, so days in stage is reliable for the open pipeline."],
];
fixes.forEach((f, i) => { const y = 1.4 + i * 1.65; card(s, 0.5, y, 12.3, 1.5);
  s.addText(String(i + 1), { x: 0.7, y: y + 0.35, w: 0.7, h: 0.8, fontSize: 40, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  s.addText(f[0], { x: 1.5, y: y + 0.15, w: 4.2, h: 1.2, fontSize: 16, bold: true, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
  s.addText(f[1], { x: 5.8, y: y + 0.15, w: 3.4, h: 1.25, fontSize: 11, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
  s.addText(f[2], { x: 9.4, y: y + 0.15, w: 3.2, h: 1.25, fontSize: 11, color: C.text1, margin: 0, isTextBox: true, valign: "top" }); });
note(s, "Full rule list with counts: removed_and_why.csv in the repo.", 6.45, 0.4);

// 4 Trend
pres.addSection({ title: "Performance" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Performance" });
s.addText("Won value has plateaued since February while real losses have kept rising", { placeholder: "title" });
const labels = t.map(x => { const [y, m] = x.month.split("-"); return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m - 1] + " " + y.slice(2); });
s.addChart(pres.ChartType.bar, [
  { name: "Won", labels, values: t.map(x => Math.round(x.won_v / 1000)) },
  { name: "Lost", labels, values: t.map(x => Math.round(x.lost_v / 1000)) },
  { name: "Bulk close-out (13 May)", labels, values: t.map(x => Math.round(x.bulk_v / 1000)) },
], { ...chartBase, x: 0.5, y: 1.3, w: 8.4, h: 4.9, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60, chartColors: [H.accent2, H.accent3, H.accent6], showLegend: true, legendPos: "t",
  valAxisTitle: "USD thousands", showValAxisTitle: true, valAxisTitleColor: H.dk2, valAxisTitleFontSize: 10, valAxisTitleFontFace: "+mn-lt", showValue: false });
card(s, 9.2, 1.3, 3.6, 4.9);
s.addText("Read", { x: 9.4, y: 1.45, w: 3.2, h: 0.35, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true });
bullets(s, [
  `Won value: ${usd(t[8].won_v)} in Feb, ${usd(t[9].won_v)}, ${usd(t[10].won_v)}, ${usd(sc.won_v)} in May. Flat to down.`,
  `Won count: ${t[8].won_n} in Feb to ${sc.won_n} in May. Fewer deals, bigger average.`,
  `Real losses: ${t[8].lost_n} in Feb to ${sc.lost_n} in May, worth ${usd(sc.lost_v)}.`,
  `The grey bar is the 13 May clean-up, ${sc.bulk_n.toLocaleString()} deals. Excluded from every rate on the following pages.`,
], 9.4, 1.85, 3.2, 4.2, 11);
note(s, "Caveat: losses before the April migration may be under-recorded, which would flatter early-2026 win rates. The direction since February is not in doubt.");

// 5 Win rate by segment
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Performance" });
s.addText("The win rate has fallen in every segment since January, with no recovery in May", { placeholder: "title" });
const wr = M.seg_wr;
s.addChart(pres.ChartType.line, Object.entries(wr).map(([k, v]) => ({ name: k, labels: ["Jan", "Feb", "Mar", "Apr", "May"], values: v.map(x => Math.round(x * 100)) })),
  { ...chartBase, x: 0.5, y: 1.3, w: 8.4, h: 4.9, chartColors: [H.accent4, H.accent1, H.accent3], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 7, showLegend: true, legendPos: "t", valAxisMaxVal: 80, valAxisMinVal: 0,
    valAxisTitle: "Win rate, %", showValAxisTitle: true, valAxisTitleColor: H.dk2, valAxisTitleFontSize: 10, valAxisTitleFontFace: "+mn-lt", showValue: true, dataLabelPosition: "t" });
card(s, 9.2, 1.3, 3.6, 4.9);
s.addText("Why deals are lost (May, real losses)", { x: 9.4, y: 1.45, w: 3.2, h: 0.5, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true });
const lr = M.lost_reasons.map(r => `${r.reason}: ${r.n}`);
bullets(s, lr, 9.4, 2.0, 3.2, 2.4, 11);
s.addText(`"Not a priority" went from ${M.lost_trend["Not a priority"][0]} in January to ${M.lost_trend["Not a priority"][1]} in May. "Unresponsive" from ${M.lost_trend["Unresponsive"][0]} to ${M.lost_trend["Unresponsive"][1]}. This is a qualification and follow-up problem, not a pricing one.`, { x: 9.4, y: 4.5, w: 3.2, h: 1.6, fontSize: 11, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
note(s, "Win rate = won / (won + lost) by month closed, bulk close-out excluded. Other roles (Admin, Engagement, CEO) not shown.");

// 6 Region and segment
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Performance" });
s.addText("EMEA and mid-market carried May. AMER and SMB fell", { placeholder: "title" });
const reg = M.region.filter(r => r.key != "Other"), seg = M.segment.filter(r => r.key != "Other");
s.addChart(pres.ChartType.bar, [{ name: "April", labels: reg.map(r => r.key), values: reg.map(r => Math.round(r.pv / 1000)) }, { name: "May", labels: reg.map(r => r.key), values: reg.map(r => Math.round(r.v / 1000)) }],
  { ...chartBase, x: 0.5, y: 1.3, w: 6.0, h: 3.6, barDir: "col", barGrouping: "clustered", chartColors: [H.accent6, H.accent1], showLegend: true, legendPos: "t", showValue: true, dataLabelPosition: "outEnd", valAxisTitle: "Won, USD thousands", showValAxisTitle: true, valAxisTitleColor: H.dk2, valAxisTitleFontSize: 10, valAxisTitleFontFace: "+mn-lt" });
s.addChart(pres.ChartType.bar, [{ name: "April", labels: seg.map(r => r.key), values: seg.map(r => Math.round(r.pv / 1000)) }, { name: "May", labels: seg.map(r => r.key), values: seg.map(r => Math.round(r.v / 1000)) }],
  { ...chartBase, x: 6.8, y: 1.3, w: 6.0, h: 3.6, barDir: "col", barGrouping: "clustered", chartColors: [H.accent6, H.accent1], showLegend: true, legendPos: "t", showValue: true, dataLabelPosition: "outEnd", valAxisTitle: "Won, USD thousands", showValAxisTitle: true, valAxisTitleColor: H.dk2, valAxisTitleFontSize: 10, valAxisTitleFontFace: "+mn-lt" });
const rows = [["", "Won", "Deals", "vs April", "Win rate"].map(h => ({ text: h, options: { bold: true, color: H.dk2 } }))];
[...reg, ...seg].forEach(r => rows.push([r.key, usd(r.v), String(r.n), pct(r.change), Math.round(r.win_rate * 100) + "%"].map((c, i) => ({ text: c, options: { color: i == 3 ? (r.change < 0 ? H.accent3 : H.accent2) : H.dk1 } }))));
s.addTable(rows, { x: 0.5, y: 5.05, w: 12.3, colW: [2.3, 2.5, 2.5, 2.5, 2.5], fontSize: 11, fontFace: "Calibri", border: { type: "solid", color: "1F2937", pt: 0.5 }, fill: { color: H.lt2 }, rowH: 0.24, margin: 0.04 });
note(s, `Other (Admin, Engagement, CEO owned) won ${usd(M.region[2].v)} in May, down from ${usd(M.region[2].pv)}, and is left off the charts.`, 6.65, 0.35);

// 7 Products
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Performance" });
s.addText("Sourcing Max and Application Review drove May. Application Review is new", { placeholder: "title" });
const pr = M.products;
s.addChart(pres.ChartType.bar, [{ name: "May won value", labels: pr.map(p => p.name), values: pr.map(p => Math.round(p.v / 1000)) }],
  { ...chartBase, x: 0.5, y: 1.3, w: 8.4, h: 4.9, barDir: "bar", catAxisOrientation: "maxMin", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "$#,##0k", valAxisTitle: "USD thousands", showValAxisTitle: true, valAxisTitleColor: H.dk2, valAxisTitleFontSize: 10, valAxisTitleFontFace: "+mn-lt", catAxisLabelFontSize: 10 });
card(s, 9.2, 1.3, 3.6, 4.9);
s.addText("Read", { x: 9.4, y: 1.45, w: 3.2, h: 0.35, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true });
bullets(s, [
  `Sourcing Max: ${usd(pr[0].v)} across ${pr[0].deals} deals, ${pct(pr[0].change)} vs April. The volume product.`,
  `Application Review: ${usd(pr[1].v)} from ${pr[1].deals} deals, ${pct(pr[1].change)}. Large average, concentrated in a few accounts.`,
  `Notetaker TA: ${pr[2].deals} deals, the most of any product, ${usd(pr[2].v)}.`,
  `All ${M.product_coverage.won_total} won deals in May carry a product name, so this chart is complete. Most open deals do not, so forward product mix is unknown.`,
], 9.4, 1.85, 3.2, 4.2, 11);
note(s, "Product value is the converted line total per product on won deals, so a deal with several products is split across them. Deal-level figures elsewhere are not affected.");

// 8 Pipeline by stage
pres.addSection({ title: "Pipeline" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Pipeline" });
s.addText(`${usd(sc.open_v)} open, ${usd(sc.open_w)} weighted. Half of it sits in Discovery`, { placeholder: "title" });
s.addChart(pres.ChartType.bar, [{ name: "Open value", labels: M.stages.map(x => x.stage), values: M.stages.map(x => Math.round(x.v / 1000)) }, { name: "Weighted", labels: M.stages.map(x => x.stage), values: M.stages.map(x => Math.round(x.w / 1000)) }],
  { ...chartBase, x: 0.5, y: 1.3, w: 8.4, h: 4.9, barDir: "col", barGrouping: "clustered", chartColors: [H.accent1, H.accent4], showLegend: true, legendPos: "t", showValue: true, dataLabelPosition: "outEnd", valAxisTitle: "USD thousands", showValAxisTitle: true, valAxisTitleColor: H.dk2, valAxisTitleFontSize: 10, valAxisTitleFontFace: "+mn-lt" });
card(s, 9.2, 1.3, 3.6, 4.9);
s.addText("Read", { x: 9.4, y: 1.45, w: 3.2, h: 0.35, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true });
const stg = M.stages;
bullets(s, [
  `${stg[1].n} deals and ${usd(stg[1].v)} in Discovery at 20% probability. That is where the number lives or dies.`,
  `Late stage (EB Go/No Go and Paper Process): ${stg[4].n + stg[5].n} deals, ${usd(stg[4].v + stg[5].v)} open, ${usd(stg[4].w + stg[5].w)} weighted.`,
  `By region: EMEA holds ${Math.round(M.open_region.find(x => x.key == "EMEA").v / sc.open_v * 100)}% of open value.`,
  `By segment: mid-market holds ${Math.round(M.open_segment.find(x => x.key == "MM").v / sc.open_v * 100)}%.`,
], 9.4, 1.85, 3.2, 4.2, 11);
note(s, "Weighted = deal value times the stage probability stored in Salesforce (Meeting booked 10%, Discovery 20%, Scoping 30%, Evaluation 47%, EB Go/No Go 75%, Paper Process 89% on average).");

// 9 AE attainment
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Performance" });
const hit = M.ae.filter(a => a.att >= 1).length;
const near = M.ae.filter(a => a.att >= 0.9 && a.att < 1).length;
s.addText(`${hit} of ${M.ae.length} AEs hit their May target. ${near == 1 ? "One more is" : near + " more are"} within 10%`, { placeholder: "title" });
const ae = M.ae;
s.addChart(pres.ChartType.bar, [{ name: "Attainment", labels: ae.map(a => a.owner), values: ae.map(a => Math.round(a.att * 100)) }],
  { ...chartBase, x: 0.5, y: 1.3, w: 8.4, h: 5.0, barDir: "bar", catAxisOrientation: "maxMin", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0\"%\"", catAxisLabelFontSize: 9, valAxisMaxVal: 160, valAxisMinVal: 0,
    chartColors: ae.map(a => a.att >= 1 ? H.accent2 : a.att >= 0.5 ? H.accent5 : H.accent3), valAxisTitle: "Percent of monthly target", showValAxisTitle: true, valAxisTitleColor: H.dk2, valAxisTitleFontSize: 10, valAxisTitleFontFace: "+mn-lt" });
card(s, 9.2, 1.3, 3.6, 5.0);
s.addText("Read", { x: 9.4, y: 1.45, w: 3.2, h: 0.35, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true });
bullets(s, [
  `Targets: ENT $125k, MM and SMB $100k a month, full month.`,
  `Top: ${ae[0].owner} ${Math.round(ae[0].att * 100)}% on ${ae[0].n} deals. ${ae[1].owner} ${Math.round(ae[1].att * 100)}%.`,
  `Within 10%: ${ae.filter(a => a.att >= 0.9 && a.att < 1).map(a => a.owner.split(" ")[0]).join(", ")}.`,
  `Under 25%: ${ae.filter(a => a.att < 0.25).length} AEs, ${ae.filter(a => a.att < 0.25 && a.segment == "SMB").length} of them SMB. Two have no won deal in May.`,
  `The row-counted version showed 9 of 20 hitting target and a top AE at 798%. Neither is true.`,
], 9.4, 1.85, 3.2, 4.3, 11);

// 10 Growth
pres.addSection({ title: "June" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "June" });
s.addText("20% growth: missed in May, covered for June, if conversion holds", { placeholder: "title" });
stat(s, 0.5, 1.4, 3.95, "May target (April + 20%)", usd(g.target_this), `Actual ${usd(g.actual)}, ${pct(g.change)} vs April`, H.accent3);
stat(s, 4.65, 1.4, 3.95, "June needs (May + 20%)", usd(g.need_next), `${g.next_n} deals due to close in June`, H.dk1);
stat(s, 8.8, 1.4, 4.0, "June pipeline", usd(g.next_v), `${usd(g.next_w)} weighted, ${g.cov_w.toFixed(1)}x coverage`, H.accent2);
s.addChart(pres.ChartType.bar, [{ name: "USD thousands", labels: ["June needed", "June weighted", "June unweighted"], values: [g.need_next, g.next_w, g.next_v].map(v => Math.round(v / 1000)) }],
  { ...chartBase, x: 0.5, y: 3.0, w: 6.2, h: 3.2, barDir: "bar", chartColors: [H.accent3, H.accent2, H.accent1], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "$#,##0k", catAxisLabelFontSize: 11 });
card(s, 7.0, 3.0, 5.8, 3.2);
s.addText("What has to be true", { x: 7.2, y: 3.15, w: 5.4, h: 0.35, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true });
bullets(s, [
  `Weighted coverage of ${g.cov_w.toFixed(1)}x is healthy on paper. But the May win rate was ${Math.round(sc.win_rate * 100)}%, and stage probabilities assume far more.`,
  `At May's actual conversion, ${usd(g.next_v)} of pipeline yields about ${usd(g.next_v * sc.win_rate)}. That misses.`,
  `The gap closes if late-stage deals close as scheduled: ${usd(stg[4].v + stg[5].v)} sits in EB Go/No Go and Paper Process.`,
  `So June is a conversion target, not a pipeline-generation target.`,
], 7.2, 3.55, 5.4, 2.6, 11);
note(s, "Target rule as set in the brief: 20% month on month growth in won value. June pipeline = open deals with a close date in June 2026.");

// 11 Calibrated VP queue
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "June" });
const cal = M.calibration || { queue: [] };
s.addText("The fifteen deals the VP should ask about, with the question for each", { placeholder: "title" });
const qh = ["#", "Owner", "Stage", "Value", "Salesforce", "History", "Close", "The question"].map(h => ({ text: h, options: { bold: true, color: H.dk2, fill: { color: H.lt1 } } }));
const qrows = cal.queue.map(q => [q.rank, q.owner, q.stage, usd(q.value || 0), Math.round((q.prob_sf || 0) * 100) + "%", Math.round(q.prob_cal * 100) + "%", q.close, q.question]
  .map((c, i) => ({ text: String(c), options: { color: i == 5 ? (q.prob_cal > (q.prob_sf || 0) + 0.1 ? H.accent2 : H.dk1) : H.dk1 } })));
s.addTable([qh, ...qrows], { x: 0.5, y: 1.3, w: 12.3, colW: [0.4, 1.5, 1.3, 0.8, 0.9, 0.8, 0.8, 5.8], fontSize: 8.5, fontFace: "Calibri", border: { type: "solid", color: "1F2937", pt: 0.5 }, fill: { color: H.lt2 }, rowH: 0.3, margin: 0.04, valign: "middle" });
note(s, `Open deals closing by 30 June as of the 31 May snapshot, ranked by expected value and attention need. "History" is the win rate of deals that reached the same stage in the same region and segment over the 90 days before May, smoothed toward the stage average. These run high against what has happened since (${cal.since_won} won, ${cal.since_lost} lost of those resolved), because 2025 history is rosier than 2026: a conversation starter, not a forecast. Method from the July Hex workbook, rebuilt one row per deal in calibrate.py.`, 6.15, 0.8);

// 12 Findings and actions
pres.addSection({ title: "Actions" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Actions" });
s.addText("Three findings, three actions for the MBR", { placeholder: "title" });
const fa = [
  ["Conversion, not coverage, is the problem", `Win rate ${Math.round(t[7].win_rate * 100)}% in January to ${Math.round(sc.win_rate * 100)}% in May, in every segment. "Not a priority" and "Unresponsive" are the growing loss reasons.`, "Run a loss review on the 50 largest real losses of April and May. Decide whether this is qualification at Meeting booked or follow-up after Discovery. Owner: VP Sales, by the next MBR."],
  ["SMB is where the volume went missing", `SMB won ${usd(seg.find(x => x.key == "SMB").v)}, ${pct(seg.find(x => x.key == "SMB").change)}, at a ${Math.round(seg.find(x => x.key == "SMB").win_rate * 100)}% win rate, while ${M.bulk_detail.smb.toLocaleString()} SMB deals were bulk closed with no activity logged.`, "Set an activity rule: no SMB deal sits in Discovery past 30 days without a logged touch. Review the inbound to SMB handoff. Owner: SMB leads, EMEA and AMER."],
  ["Mid-market and enterprise are working", `MM ${pct(seg.find(x => x.key == "MM").change)}, ENT ${pct(seg.find(x => x.key == "ENT").change)}, average deal ${usd(sc.avg_won)}. Application Review ${pct(pr[1].change)}.`, `Protect the ${stg[4].n + stg[5].n} late-stage deals (${usd(stg[4].v + stg[5].v)}): weekly check on the top 15, exec sponsor on every EB Go/No Go. Owner: MM and ENT leads.`],
];
fa.forEach((f, i) => { const y = 1.4 + i * 1.65; card(s, 0.5, y, 12.3, 1.5);
  s.addText(f[0], { x: 0.7, y: y + 0.15, w: 3.4, h: 1.2, fontSize: 15, bold: true, color: C.accent1, margin: 0, isTextBox: true, valign: "top" });
  s.addText("Finding  ", { x: 4.3, y: y + 0.15, w: 0.8, h: 0.3, fontSize: 9, color: C.text2, margin: 0, isTextBox: true });
  s.addText(f[1], { x: 4.3, y: y + 0.4, w: 3.9, h: 1.05, fontSize: 11, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
  s.addText("Action", { x: 8.5, y: y + 0.15, w: 0.8, h: 0.3, fontSize: 9, color: C.text2, margin: 0, isTextBox: true });
  s.addText(f[2], { x: 8.5, y: y + 0.4, w: 4.1, h: 1.05, fontSize: 11, color: C.text1, margin: 0, isTextBox: true, valign: "top" }); });
note(s, "Fourth, for Ops: backfill stage entered dates from the Salesforce audit trail and require a product on every open deal. Both are free and both make the next MBR sharper.", 6.45, 0.5);

// 13 Method
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Actions" });
s.addText("Method and data quality", { placeholder: "title" });
bullets(s, [
  `Source: Salesforce export, ${M.meta.rows.toLocaleString()} rows, ${M.meta.deals.toLocaleString()} deals, Jan 2025 to May 2026. Reporting period May 2026, compared with April.`,
  "Deal value: sum of Total Price (converted) across a deal's product lines, in USD. Equals Amount for USD deals and converts the 46 EUR and GBP deals.",
  "Won and lost month: Stage 7W or 7L entered date, Close Date where missing (4 deals).",
  `Bulk close-out: ${sc.bulk_n.toLocaleString()} deals lost on 13 May, 83% with reason Unknown and no activity found. All flagged and excluded from rates.`,
  "Win rate: won / (won + lost) by month closed. Weighted pipeline: value times stage probability.",
  "AE attainment: ENT $125k, MM and SMB $100k, full monthly target, AE roles only.",
  "Known gaps: 1,172 rows with no amount, 93% of rows with no product name, 22% with no stage entered date (nearly all closed deals), created dates are migration dates.",
  "Everything here is reproducible: analysis.py in the repo rebuilds every number and chart from the export in one run.",
], 0.5, 1.4, 12.3, 4.9, 13);

(async () => { await pres.writeFile({ fileName: __dirname + "/out/Metaview_MBR_May_2026.pptx" }); await applyTheme(__dirname + "/out/Metaview_MBR_May_2026.pptx", THEME); console.log("ok"); })();
