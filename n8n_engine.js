// Pipeline check-in engine. Runs inside an n8n Code node (no libraries) and locally for testing.
// Input: rows of the Salesforce export (one row per product line). Output: the agent's system prompt.
// Every period is read from the data: "today" is the latest date in the export, the review month is the
// last complete month before it. Nothing is tied to May or June 2026.

function buildCheckin(rows, NOTES, PROMPT_TEMPLATE) {
  const DAY = 86400000;
  const toDate = (v) => {
    if (v === null || v === undefined || v === '') return null;
    if (typeof v === 'number') return new Date(Math.round((Math.floor(v) - 25569) * DAY));
    const s = String(v).trim();
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})/); // day first, as the export is UK format
    if (m) { const y = +m[3] < 100 ? 2000 + +m[3] : +m[3]; return new Date(Date.UTC(y, +m[2] - 1, +m[1])); }
    const d = new Date(s); return isNaN(d) ? null : new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  };
  const num = (v) => { if (typeof v === 'number') return v; const n = parseFloat(String(v ?? '').replace(/[^0-9.\-]/g, '')); return isNaN(n) ? null : n; };
  const money = (v) => (v === null || v === undefined || isNaN(v)) ? 'no amount recorded' : '$' + Math.round(v).toLocaleString('en-US');
  const pct = (v) => (v === null || v === undefined || isNaN(v)) ? 'n/a' : Math.round(v * 100) + '%';
  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const MON = MONTHS.map((x) => x.slice(0, 3));
  const dm = (d) => `${String(d.getUTCDate()).padStart(2, '0')} ${MON[d.getUTCMonth()]}`;
  const stageName = (s) => String(s || '').replace(/^\d+[A-Z]?\s*-\s*/, '').trim();
  const sum = (a, f) => a.reduce((t, x) => t + (f(x) || 0), 0);

  // 1. One row per deal. Deal value = sum of converted line totals.
  const byId = new Map();
  for (const r of rows) {
    const id = r['Opportunity ID']; if (!id) continue;
    let d = byId.get(id);
    if (!d) {
      d = { id, owner: r['Opportunity Owner'], role: r['Owner Role'] || '', type: r['Type'], stage: String(r['Stage'] || '').replace(/^Closed Lost$/, '7L - Closed Lost'),
        prob: num(r['Probability (%)']), close: toDate(r['Close Date']), won: toDate(r['Stage 7W Entered Date']), lost: toDate(r['Stage 7L Entered Date']),
        reason: r['Closed Lost Reason'], s: [1, 2, 3, 4, 5, 6].map((i) => toDate(r[`Stage ${i} Entered Date`])), value: 0, products: new Set() };
      byId.set(id, d);
    }
    d.value += num(r['Total Price (converted)']) || 0;
    if (r['Product Name']) d.products.add(r['Product Name']);
  }
  const deals = [...byId.values()];
  for (const d of deals) {
    if (!d.value) d.value = null;
    d.status = d.stage.startsWith('7W') ? 'won' : d.stage.startsWith('7L') ? 'lost' : 'open';
    d.segment = (d.role.match(/(SMB|MM|ENT)/) || [])[1] || 'Other';
    d.region = (d.role.match(/^(EMEA|AMER)/) || [])[1] || 'Other';
    d.isAE = /\bAE\b/.test(d.role);
    d.weighted = (d.value || 0) * (d.prob || 0);
    const ds = d.s.filter(Boolean); d.entered = ds.length ? new Date(Math.max(...ds)) : null;
  }

  // 2. Periods from the data
  const allDates = deals.flatMap((d) => [d.won, d.lost, d.entered]).filter(Boolean);
  const TODAY = new Date(Math.max(...allDates));
  const mStart = (y, m) => new Date(Date.UTC(y, m, 1));
  const M0s = mStart(TODAY.getUTCFullYear(), TODAY.getUTCMonth()); const M0e = new Date(mStart(TODAY.getUTCFullYear(), TODAY.getUTCMonth() + 1) - DAY);
  const M1s = mStart(TODAY.getUTCFullYear(), TODAY.getUTCMonth() - 1); const M1e = new Date(M0s - DAY);
  const M2s = mStart(TODAY.getUTCFullYear(), TODAY.getUTCMonth() - 2); const M2e = new Date(M1s - DAY);
  const M0 = MONTHS[M0s.getUTCMonth()], M1 = MONTHS[M1s.getUTCMonth()], M2 = MONTHS[M2s.getUTCMonth()];
  const daysLeft = Math.round((M0e - TODAY) / DAY);
  const inR = (d, a, b) => d && d >= a && d <= b;

  // 3. Bulk close-out days: 50+ deals lost on one day, 75%+ reason Unknown
  const byDay = {};
  for (const d of deals) if (d.status === 'lost' && d.lost) { const k = +d.lost; (byDay[k] ||= { n: 0, u: 0 }); byDay[k].n++; if (d.reason === 'Unknown') byDay[k].u++; }
  const bulkDays = new Set(Object.entries(byDay).filter(([, v]) => v.n >= 50 && v.u / v.n >= 0.75).map(([k]) => +k));
  for (const d of deals) d.bulk = d.status === 'lost' && d.lost && bulkDays.has(+d.lost);

  const won = (ds, a, b) => ds.filter((d) => d.status === 'won' && inR(d.won, a, b));
  const realLost = (ds, a, b) => ds.filter((d) => d.status === 'lost' && !d.bulk && inR(d.lost, a, b));
  const target = (d) => d.segment === 'ENT' ? 125000 : 100000;

  // 4. Attention ranking (port of calibrate.py, same as the Hex workbook): snapshot at end of review month
  const SNAP = M1e, CUTOFF = M2e, WIN = new Date(+CUTOFF - 90 * DAY), PRIOR = 20;
  const STAGE_PROB = { 1: 0.1, 2: 0.2, 3: 0.3, 4: 0.5, 5: 0.75, 6: 0.9 };
  const SN = { 1: 'Meeting booked', 2: 'Discovery', 3: 'Scoping', 4: 'Evaluation', 5: 'EB Go/No Go', 6: 'Paper Process' };
  for (const d of deals) {
    let latest = null, st = null;
    d.s.forEach((x, i) => { if (x && x <= SNAP && (!latest || x >= latest)) { latest = x; st = i + 1; } });
    const wonBy = d.won && d.won <= SNAP, lostBy = d.lost && d.lost <= SNAP;
    d.snapStatus = wonBy && (!lostBy || d.won >= d.lost) ? 'won' : lostBy ? 'lost' : 'open';
    if (st === null && d.snapStatus === 'open') d.snapStatus = 'unknown';
    d.snapStage = st; d.snapDays = latest ? Math.max(0, Math.round((SNAP - latest) / DAY)) : null;
    const cur = parseInt(d.stage[0], 10);
    d.probSnap = d.snapStatus === 'open' ? (d.status === 'open' && cur === st ? d.prob : STAGE_PROB[st]) : null;
  }
  const train = [];
  for (const d of deals) {
    const od = d.won && d.lost ? new Date(Math.max(d.won, d.lost)) : d.won || d.lost;
    if (!od || od > CUTOFF || od < WIN) continue;
    if (d.won && d.lost && +d.won === +d.lost) continue;
    const y = d.won && (!d.lost || d.won > d.lost) ? 1 : 0;
    d.s.forEach((x, i) => { if (x && x <= od) train.push({ st: i + 1, region: d.region, segment: d.segment, type: d.type, y }); });
  }
  const LEVELS = [['region', 'segment', 'type'], ['region', 'segment'], ['segment'], []];
  const tables = LEVELS.map((l) => { const t = {}; for (const r of train) { const k = [r.st, ...l.map((c) => r[c])].join('|'); (t[k] ||= { n: 0, w: 0 }); t[k].n++; t[k].w += r.y; } return t; });
  const stPrior = {}; for (const r of train) { (stPrior[r.st] ||= { n: 0, w: 0 }); stPrior[r.st].n++; stPrior[r.st].w += r.y; }
  const overall = sum(train, (r) => r.y) / train.length;
  const tgt = deals.filter((d) => d.snapStatus === 'open' && d.close && d.close <= M0e);
  for (const d of tgt) {
    let pick = null;
    for (let i = 0; i < LEVELS.length; i++) {
      const k = [d.snapStage, ...LEVELS[i].map((c) => d[c])].join('|'); const m = tables[i][k];
      if (m && m.n >= (LEVELS[i].length ? 20 : 5)) { pick = m; break; }
    }
    if (!pick) pick = { n: train.length, w: sum(train, (r) => r.y) };
    const prior = stPrior[d.snapStage] ? stPrior[d.snapStage].w / stPrior[d.snapStage].n : overall;
    d.pcal = Math.round(((pick.w + PRIOR * prior) / (pick.n + PRIOR)) * 1000) / 1000;
    d.pn = pick.n; d.pw = pick.w;
    d.evCal = d.value === null ? null : d.value * d.pcal;
    d.gap = d.probSnap - d.pcal;
    d.disagree = d.value === null ? null : d.value * Math.abs(d.gap);
    d.dir = d.gap > 0.1 ? 'opt' : d.gap < -0.1 ? 'cons' : 'ok';
    d.overdue = d.close < M0s;
  }
  const med = {}; for (const st of new Set(tgt.map((d) => d.snapStage))) {
    const v = tgt.filter((d) => d.snapStage === st && d.snapDays !== null).map((d) => d.snapDays).sort((a, b) => a - b);
    med[st] = v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
  }
  const pctRank = (key) => { // pandas rank(pct=True), average ties, NaN stays NaN
    const v = tgt.filter((d) => d[key] !== null && !isNaN(d[key])).sort((a, b) => a[key] - b[key]);
    let i = 0; while (i < v.length) { let j = i; while (j + 1 < v.length && v[j + 1][key] === v[i][key]) j++; const r = (i + j + 2) / 2; for (let k = i; k <= j; k++) v[k]['r_' + key] = r / v.length; i = j + 1; }
  };
  pctRank('evCal'); pctRank('disagree');
  for (const d of tgt) {
    d.stale = d.snapDays > med[d.snapStage] * 1.5;
    const sn = SN[d.snapStage];
    d.question = d.overdue ? `Close date ${dm(d.close)} has passed. What is the new date, and what changed?`
      : d.dir === 'opt' ? `Salesforce says ${pct(d.probSnap)}. Similar deals at ${sn} won ${d.pw} of ${d.pn} times (${pct(d.pcal)}). What makes this one different?`
      : d.stale ? `${d.snapDays} days in ${sn}, against a median of ${(() => { const x = med[d.snapStage], f = Math.floor(x); return x - f === 0.5 ? (f % 2 ? f + 1 : f) : Math.round(x); })()}. What is the next dated step?`
      : d.dir === 'cons' ? `Salesforce says ${pct(d.probSnap)} but similar deals won ${pct(d.pcal)} of the time. Is it further along than the stage shows?`
      : `On track at ${pct(d.pcal)}. Is ${dm(d.close)} still the close date, and who signs?`;
    d.attention = d.r_evCal === undefined || d.r_disagree === undefined ? null
      : 0.65 * d.r_evCal * 100 + 0.35 * (d.r_disagree * 60 + (d.stale ? 20 : 0) + (d.overdue ? 20 : 0));
  }
  const ranked = tgt.filter((d) => d.attention !== null).sort((a, b) => b.attention - a.attention);
  ranked.forEach((d, i) => { d.rank = i + 1; });
  const top20 = ranked.slice(0, 20);

  // 5. Team brief
  const m1won = won(deals, M1s, M1e), m2won = won(deals, M2s, M2e), m0won = won(deals, M0s, TODAY), m1lost = realLost(deals, M1s, M1e);
  const m0target = sum(m1won, (d) => d.value) * 1.2;
  const open = deals.filter((d) => d.status === 'open');
  const m0open = open.filter((d) => inR(d.close, TODAY, M0e));
  const trend = [4, 3, 2, 1].map((k) => { const s = mStart(TODAY.getUTCFullYear(), TODAY.getUTCMonth() - k), e = new Date(mStart(TODAY.getUTCFullYear(), TODAY.getUTCMonth() - k + 1) - DAY);
    const w = won(deals, s, e).length, l = realLost(deals, s, e).length; return `${MONTHS[s.getUTCMonth()]} ${w + l ? Math.round((100 * w) / (w + l)) : 0}%`; });
  const aes = {}; for (const d of deals) if (d.isAE && d.owner) aes[d.owner] = target(d);
  const att = Object.entries(aes).map(([o, t]) => ({ o, a: sum(m1won.filter((d) => d.owner === o), (d) => d.value) / t })).sort((a, b) => b.a - a.a);
  const reasons = {}; for (const d of m1lost) reasons[d.reason || 'Unknown'] = (reasons[d.reason || 'Unknown'] || 0) + 1;
  const bulkN = deals.filter((d) => d.bulk).length;
  const team = [
    `Data as of ${TODAY.getUTCDate()} ${M0} ${TODAY.getUTCFullYear()}. Treat this as today. ${daysLeft} days remain in ${M0}.`,
    `${M1}: won ${m1won.length} deals for ${money(sum(m1won, (d) => d.value))}. ${M2}: ${m2won.length} deals for ${money(sum(m2won, (d) => d.value))}.`,
    `${M1} win rate excluding clean-up days: ${Math.round((100 * m1won.length) / (m1won.length + m1lost.length))}%. Trend: ${trend.join(', ')}.`,
    `Clean-up days: ${bulkN.toLocaleString('en-US')} deals closed lost in bulk with reason Unknown on ${[...bulkDays].sort().map((k) => dm(new Date(k))).join(', ')}. Hygiene, not real losses. Never count them against a rep.`,
    `AEs at or above target in ${M1}: ${att.filter((x) => x.a >= 1).map((x) => `${x.o} ${Math.round(x.a * 100)}%`).join(', ') || 'none'}. That is ${att.filter((x) => x.a >= 1).length} of ${att.length}. Monthly targets: Enterprise $125,000, Mid-Market and SMB $100,000.`,
    `Top loss reasons in ${M1}: ${Object.entries(reasons).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k, v]) => `${k} ${v}`).join(', ')}.`,
    `${M0} target: ${money(m0target)} (${M1} plus 20%). Won so far: ${m0won.length} deals, ${money(sum(m0won, (d) => d.value))}, ${Math.round((100 * sum(m0won, (d) => d.value)) / m0target)}% of target. Open deals closing by ${dm(M0e)}: ${m0open.length}, ${money(sum(m0open, (d) => d.weighted))} weighted.`,
    `Open pipeline: ${open.length} deals, ${money(sum(open, (d) => d.value))}, weighted ${money(sum(open, (d) => d.weighted))}.`,
    `The top 20 deals were ranked on ${dm(SNAP)} by how much management attention they need (the Hex review). Its history-based win chance runs high, so it is a second opinion only.`,
    `The export has account IDs, not company names. Ask the rep which account a deal is.`,
  ].map((x) => '- ' + x).join('\n');

  // 6. Rep briefs
  const people = new Set([...open.map((d) => d.owner), ...m1won.map((d) => d.owner), ...m0won.map((d) => d.owner), ...Object.keys(NOTES || {})]);
  people.delete('Salesforce Admin'); people.delete(undefined);
  const reps = [...people].sort().map((p) => {
    const mine = deals.filter((d) => d.owner === p);
    const role = (mine[0] && mine[0].role) || 'not in Salesforce';
    const w1 = won(mine, M1s, M1e), w0 = won(mine, M0s, TODAY);
    const t = aes[p];
    const L = [`## ${p} (${role})`];
    if (t) L.push(`${M1}: ${money(sum(w1, (d) => d.value))} won, ${Math.round((100 * sum(w1, (d) => d.value)) / t)}% of the ${money(t)} target. ${M0} so far: ${money(sum(w0, (d) => d.value))}, still needed ${money(Math.max(t - sum(w0, (d) => d.value), 0))}.`);
    else L.push(`${M1}: ${money(sum(w1, (d) => d.value))} won. ${M0} so far: ${money(sum(w0, (d) => d.value))}. No AE target.`);
    const mo = mine.filter((d) => d.status === 'open' && inR(d.close, TODAY, M0e));
    const od = mine.filter((d) => d.status === 'open' && d.close && d.close < TODAY);
    L.push(`Open deals closing by ${dm(M0e)}: ${mo.length}, ${money(sum(mo, (d) => d.weighted))} weighted. Close date already passed: ${od.length}.`);
    for (const d of top20.filter((x) => x.owner === p)) {
      if (d.status === 'open') {
        const days = d.entered ? Math.max(0, Math.round((TODAY - d.entered) / DAY)) : null;
        L.push(`Top 20 deal, rank ${d.rank}: ${money(d.value)}, now ${stageName(d.stage)} (${pct(d.prob)}), close ${d.close ? dm(d.close) : 'none'}, ${days} days in stage. Flagged on ${dm(SNAP)}: ${d.question}`);
      } else L.push(`Top 20 deal, rank ${d.rank}: ${money(d.value)}, closed ${d.status} since ${dm(SNAP)}. Do not raise unless the rep does.`);
    }
    for (const n of (NOTES && NOTES[p]) || []) L.push(n);
    return L.join('\n');
  });

  const prompt = PROMPT_TEMPLATE.replace('{{TODAY}}', `${TODAY.getUTCDate()} ${M0} ${TODAY.getUTCFullYear()}`).replace('{{DAYS_LEFT}}', String(daysLeft))
    .replace(/{{MONTH}}/g, M0).replace('{{TEAM_BRIEF}}', team).replace('{{REP_BRIEFS}}', reps.join('\n\n'));
  return { prompt, today: TODAY.toISOString().slice(0, 10), reviewMonth: M1, month: M0, deals: deals.length, reps: reps.length,
    top20: top20.map((d) => ({ rank: d.rank, owner: d.owner, value: d.value, stage: stageName(d.stage), status: d.status, id: d.id })) };
}

if (typeof module !== 'undefined') module.exports = { buildCheckin };
