// Builds the two n8n workflows as JSON. Usage: node build_workflows.js <AGENT_ID> <CRED_ID>
const fs = require('fs');
const AGENT = process.argv[2] || 'AGENT_ID';
const CRED = process.argv[3] ? { httpHeaderAuth: { id: process.argv[3], name: 'ElevenLabs' } } : undefined;
const engine = fs.readFileSync(__dirname + '/n8n_engine.js', 'utf8').replace(/\nif \(typeof module[^\n]*\n?/, '\n');
const notes = fs.readFileSync(__dirname + '/notes.json', 'utf8');
const template = fs.readFileSync(__dirname + '/agent_prompt.md', 'utf8');

const http = (name, method, url, extra = {}, pos) => ({
  id: name.replace(/\W/g, '').toLowerCase(), name, type: 'n8n-nodes-base.httpRequest', typeVersion: 4.2, position: pos,
  parameters: { method, url, authentication: 'genericCredentialType', genericAuthType: 'httpHeaderAuth', options: {}, ...extra },
  ...(CRED ? { credentials: CRED } : {}),
});

// ---------- Workflow 1: upload export -> rebuild briefs -> update agent ----------
const code1 = `// Rebuilds every rep brief and the top 20 from this week's export, then hands the prompt to ElevenLabs.
${engine}
const NOTES = ${notes};
const TEMPLATE = ${JSON.stringify(template)};
const rows = $input.all().map((i) => i.json);
const out = buildCheckin(rows, NOTES, TEMPLATE);
const top = out.top20.filter((d) => d.status === 'open').slice(0, 5).map((d) => '#' + d.rank + ' ' + d.owner + ' $' + Math.round(d.value || 0).toLocaleString('en-US') + ' ' + d.stage).join(' | ');
return [{ json: { ...out, rows: rows.length, summary: 'Data as of ' + out.today + '. ' + out.deals + ' deals from ' + rows.length + ' rows. ' + out.reps + ' rep briefs. Top open deals: ' + top } }];`;

const wf1 = {
  name: '1. Weekly export -> check-in agent',
  nodes: [
    { id: 'form', name: 'Upload export', type: 'n8n-nodes-base.formTrigger', typeVersion: 2.5, position: [0, 0], webhookId: 'pipeline-upload',
      parameters: { path: 'pipeline-upload', formTitle: 'Upload this week\'s Salesforce export',
        formDescription: 'Drop in the opportunity export (.xlsx). The check-in agent is rebuilt from it: every rep\'s numbers, this month\'s target, and the top 20 deals that need management attention. Takes about a minute.',
        formFields: { values: [{ fieldName: 'export', fieldLabel: 'Salesforce export (.xlsx)', fieldType: 'file', multipleFiles: false, acceptFileTypes: '.xlsx', requiredField: true }] },
        responseMode: 'lastNode', options: { buttonLabel: 'Rebuild the agent' } } },
    { id: 'extract', name: 'Read spreadsheet', type: 'n8n-nodes-base.extractFromFile', typeVersion: 1.1, position: [250, 0],
      parameters: { operation: 'xlsx', binaryPropertyName: 'export', options: {} } },
    { id: 'build', name: 'Build briefs and top 20', type: 'n8n-nodes-base.code', typeVersion: 2, position: [500, 0],
      parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: code1 } },
    http('Update agent', 'PATCH', `https://api.elevenlabs.io/v1/convai/agents/${AGENT}`,
      { sendBody: true, specifyBody: 'json', jsonBody: '={{ JSON.stringify({ conversation_config: { agent: { prompt: { prompt: $json.prompt } } } }) }}' }, [750, 0]),
    { id: 'done', name: 'Done', type: 'n8n-nodes-base.form', typeVersion: 2.5, position: [1000, 0], webhookId: 'pipeline-upload-done',
      parameters: { operation: 'completion', respondWith: 'text', completionTitle: 'Agent updated',
        completionMessage: "={{ $('Build briefs and top 20').first().json.summary }}", options: {} } },
  ],
  connections: {
    'Upload export': { main: [[{ node: 'Read spreadsheet', type: 'main', index: 0 }]] },
    'Read spreadsheet': { main: [[{ node: 'Build briefs and top 20', type: 'main', index: 0 }]] },
    'Build briefs and top 20': { main: [[{ node: 'Update agent', type: 'main', index: 0 }]] },
    'Update agent': { main: [[{ node: 'Done', type: 'main', index: 0 }]] },
  },
  settings: { executionOrder: 'v1' },
};

// ---------- Workflow 2: VP clicks -> pull check-in calls -> download Excel ----------
const code2a = `// One item per call in the chosen window.
const days = { 'Last 7 days': 7, 'Last 30 days': 30, 'All calls': 100000 }[$('VP prep sheet').first().json.window] || 7;
const since = Date.now() / 1000 - days * 86400;
const calls = ($json.conversations || []).filter((c) => (c.start_time_unix_secs || 0) >= since);
return calls.map((c) => ({ json: { conversation_id: c.conversation_id } }));`;
const code2b = `// One row per rep (latest call), next to the Salesforce figures from the agent's own briefs.
const prompt = $('Get agent').first().json.conversation_config.agent.prompt.prompt || '';
const sf = {};
for (const block of prompt.split('\\n## ').slice(1)) {
  const name = block.split(' (')[0].trim();
  const so = block.match(/so far: \\$([\\d,]+)/); const need = block.match(/still needed \\$([\\d,]+)/);
  sf[name.toLowerCase()] = { won: so ? +so[1].replace(/,/g, '') : null, gap: need ? +need[1].replace(/,/g, '') : null };
}
const calls = $input.all().map((i) => i.json).filter((c) => c.analysis);
calls.sort((a, b) => (b.metadata?.start_time_unix_secs || 0) - (a.metadata?.start_time_unix_secs || 0));
const v = (c, k) => c.analysis?.data_collection_results?.[k]?.value ?? '';
const seen = new Set(); const rows = [];
for (const c of calls) {
  const rep = String(v(c, 'rep_name') || 'Unknown caller').trim();
  if (seen.has(rep.toLowerCase())) continue; seen.add(rep.toLowerCase());
  const s = sf[rep.toLowerCase()] || {};
  const t = new Date((c.metadata?.start_time_unix_secs || 0) * 1000);
  rows.push({ json: {
    'Rep': rep, 'Check-in': t.toISOString().slice(0, 16).replace('T', ' '),
    'Won this month (Salesforce)': s.won, 'Still needed for target (Salesforce)': s.gap,
    "Rep's number this month": v(c, 'month_number'), 'Committed': v(c, 'month_commit'),
    'What changed since last week': v(c, 'what_changed'), 'Top 20 deals: next step and date': v(c, 'flagged_deals'),
    'Salesforce fixes needed': v(c, 'salesforce_fixes'), 'Help asked for': v(c, 'help_needed'),
    'Call summary': c.analysis?.transcript_summary || '',
    'Recording': 'https://elevenlabs.io/app/conversational-ai/history/' + c.conversation_id,
  } });
}
if (!rows.length) rows.push({ json: { 'Rep': 'No check-in calls in this window yet' } });
return rows.sort((a, b) => String(a.json.Rep).localeCompare(String(b.json.Rep)));`;

const wf2 = {
  name: '2. VP prep sheet',
  nodes: [
    { id: 'form2', name: 'VP prep sheet', type: 'n8n-nodes-base.formTrigger', typeVersion: 2.5, position: [0, 0], webhookId: 'vp-prep',
      parameters: { path: 'vp-prep', formTitle: 'Pipeline review prep sheet',
        formDescription: 'One row per rep from their three-minute check-in: what changed, their number for the month, the top 20 deals with next steps, Salesforce fixes and the help they need. Next to it, the Salesforce figures.',
        formFields: { values: [{ fieldName: 'window', fieldLabel: 'Which calls', fieldType: 'dropdown', fieldOptions: { values: [{ option: 'Last 7 days' }, { option: 'Last 30 days' }, { option: 'All calls' }] }, requiredField: true }] },
        responseMode: 'lastNode', options: { buttonLabel: 'Build my prep sheet' } } },
    http('Get agent', 'GET', `https://api.elevenlabs.io/v1/convai/agents/${AGENT}`, {}, [250, 0]),
    http('List calls', 'GET', 'https://api.elevenlabs.io/v1/convai/conversations',
      { sendQuery: true, queryParameters: { parameters: [{ name: 'agent_id', value: AGENT }, { name: 'page_size', value: '100' }] } }, [500, 0]),
    { id: 'split', name: 'Calls in window', type: 'n8n-nodes-base.code', typeVersion: 2, position: [750, 0],
      parameters: { mode: 'runOnceForEachItem', language: 'javaScript', jsCode: code2a.replace('$json.conversations', '$json.conversations') } },
    http('Get call', 'GET', '=https://api.elevenlabs.io/v1/convai/conversations/{{ $json.conversation_id }}', {}, [1000, 0]),
    { id: 'rows', name: 'One row per rep', type: 'n8n-nodes-base.code', typeVersion: 2, position: [1250, 0],
      parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: code2b } },
    { id: 'xlsx', name: 'Make Excel', type: 'n8n-nodes-base.convertToFile', typeVersion: 1.1, position: [1500, 0],
      parameters: { operation: 'xlsx', binaryPropertyName: 'data', options: { fileName: '={{ "VP_prep_" + $now.toFormat("yyyy-MM-dd") + ".xlsx" }}', sheetName: 'Before the meeting' } } },
    { id: 'dl', name: 'Download', type: 'n8n-nodes-base.form', typeVersion: 2.5, position: [1750, 0], webhookId: 'vp-prep-done',
      parameters: { operation: 'completion', respondWith: 'returnBinary', inputDataFieldName: 'data', completionTitle: 'Your prep sheet',
        completionMessage: 'The download should start now. One row per rep, latest check-in first.', options: {} } },
  ],
  connections: {
    'VP prep sheet': { main: [[{ node: 'Get agent', type: 'main', index: 0 }]] },
    'Get agent': { main: [[{ node: 'List calls', type: 'main', index: 0 }]] },
    'List calls': { main: [[{ node: 'Calls in window', type: 'main', index: 0 }]] },
    'Calls in window': { main: [[{ node: 'Get call', type: 'main', index: 0 }]] },
    'Get call': { main: [[{ node: 'One row per rep', type: 'main', index: 0 }]] },
    'One row per rep': { main: [[{ node: 'Make Excel', type: 'main', index: 0 }]] },
    'Make Excel': { main: [[{ node: 'Download', type: 'main', index: 0 }]] },
  },
  settings: { executionOrder: 'v1' },
};
// "Calls in window" returns many items from one input, so it must run once for all items.
wf2.nodes.find((n) => n.name === 'Calls in window').parameters.mode = 'runOnceForAllItems';
wf2.nodes.find((n) => n.name === 'Calls in window').parameters.jsCode = code2a.replace('($json.conversations || [])', "($input.first().json.conversations || [])");
// Empty window: still produce the sheet
wf2.nodes.find((n) => n.name === 'Get call').alwaysOutputData = true;
wf2.nodes.find((n) => n.name === 'Calls in window').alwaysOutputData = true;

fs.writeFileSync(__dirname + '/wf1.json', JSON.stringify(wf1, null, 1));
fs.writeFileSync(__dirname + '/wf2.json', JSON.stringify(wf2, null, 1));
console.log('wf1 code chars', code1.length, 'wf2 ok');
