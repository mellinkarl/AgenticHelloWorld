import './style.css';

// ===== API base (vite proxy on by default) =====
const USE_PROXY = (import.meta as any).env?.VITE_USE_PROXY !== 'false'; // default true
const DIRECT_API = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000';
const API_BASE = USE_PROXY ? '' : DIRECT_API;
(document.querySelector('#api-base') as HTMLElement).textContent = USE_PROXY ? '(same-origin via proxy)' : DIRECT_API;
(document.querySelector('#proxy-note') as HTMLElement).textContent = USE_PROXY ? ' — dev proxy is on (no CORS)' : ' — direct mode';

// ===== Helpers =====
const $ = (sel: string) => document.querySelector(sel)! as HTMLElement;
const $$ = (sel: string) => Array.from(document.querySelectorAll(sel)) as HTMLElement[];

function text(el: HTMLElement, v: any) { el.textContent = v == null ? '—' : String(v); }
function setBadge(el: HTMLElement, label: string, cls?: string) {
  el.className = `badge ${cls || ''}`.trim();
  el.textContent = label || '—';
}
function pick<T=any>(obj: any, path: string, fallback?: T): T | undefined {
  try { return path.split('.').reduce((o,k)=> (o==null?undefined:o[k]), obj) ?? fallback; }
  catch { return fallback; }
}

// ===== Pretty JSON viewer =====
function renderJSON(el: HTMLElement, data: any, isRoot = true) {
  el.innerHTML = '';
  el.appendChild(buildNode(data, isRoot));
}
function buildNode(value: any, isRoot = false): HTMLElement {
  if (value === null) { const s = document.createElement('span'); s.className='v-null'; s.textContent='null'; return s; }
  const t = typeof value;
  if (t === 'string') { const s=document.createElement('span'); s.className='v-str'; s.textContent=JSON.stringify(value); return s; }
  if (t === 'number') { const s=document.createElement('span'); s.className='v-num'; s.textContent=String(value); return s; }
  if (t === 'boolean') { const s=document.createElement('span'); s.className='v-bool'; s.textContent=String(value); return s; }
  if (Array.isArray(value)) {
    const root=document.createElement('div'); if (isRoot) root.className='root';
    const details=document.createElement('details'); details.open=isRoot;
    const summary=document.createElement('summary'); summary.textContent=`Array[${value.length}]`;
    details.appendChild(summary);
    value.forEach((item, idx)=>{
      const row=document.createElement('div'); row.className='kv';
      const k=document.createElement('span'); k.className='k'; k.textContent=`[${idx}] `;
      const v=buildNode(item);
      row.appendChild(k); row.appendChild(v);
      details.appendChild(row);
    });
    root.appendChild(details); return root;
  }
  const keys=Object.keys(value||{});
  const root=document.createElement('div'); if (isRoot) root.className='root';
  const details=document.createElement('details'); details.open=isRoot;
  const summary=document.createElement('summary'); summary.textContent=`Object{${keys.length}}`;
  details.appendChild(summary);
  keys.forEach((key)=>{
    const row=document.createElement('div'); row.className='kv';
    const k=document.createElement('span'); k.className='k'; k.textContent=`${key}: `;
    const v=buildNode(value[key]);
    row.appendChild(k); row.appendChild(v);
    details.appendChild(row);
  });
  root.appendChild(details); return root;
}

// ===== Persistent recent doc_gcs_uri (7-day TTL) =====
type RecentDoc = { uri: string; t: number; ct?: string; size?: number };
const LS_KEY = 'amie_recent_docs';
const TTL_MS = 7 * 24 * 3600 * 1000;  // 7 days
const MAX_RECENT = 10;

function loadRecent(): RecentDoc[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    const arr: RecentDoc[] = raw ? JSON.parse(raw) : [];
    const now = Date.now();
    const pruned = arr
      .filter(x => typeof x?.uri === 'string' && x.uri.startsWith('gs://'))
      .filter(x => now - (x.t || 0) <= TTL_MS);
    if (pruned.length !== arr.length) localStorage.setItem(LS_KEY, JSON.stringify(pruned));
    return pruned.sort((a,b)=> (b.t - a.t)).slice(0, MAX_RECENT);
  } catch { return []; }
}

function saveRecent(entry: RecentDoc) {
  const now = Date.now();
  const list = loadRecent();
  // de-duplicate by uri
  const filtered = list.filter(x => x.uri !== entry.uri);
  filtered.unshift({ ...entry, t: now });
  const finalList = filtered.slice(0, MAX_RECENT);
  localStorage.setItem(LS_KEY, JSON.stringify(finalList));
}

function restoreLatestToInput(input: HTMLInputElement) {
  const list = loadRecent();
  if (list.length && !input.value.trim()) {
    input.value = list[0].uri;
  }
}

// ===== Upload controls =====
const fileInput = $('#file-input') as HTMLInputElement;
const chooseBtn = $('#btn-choose') as HTMLButtonElement;
const fileName = $('#file-name') as HTMLSpanElement;
const withSignedUrl = $('#with-signed-url') as HTMLInputElement;

const uploadBtn = $('#btn-upload') as HTMLButtonElement;
const uploadOut = $('#upload-result') as HTMLDivElement;

chooseBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  const f = fileInput.files?.[0];
  fileName.textContent = f ? f.name : 'No file chosen';
});

async function uploadFile() {
  const file = fileInput.files?.[0];
  if (!file) { uploadOut.innerHTML = '<span class="muted">Please choose a file.</span>'; return; }
  const form = new FormData(); form.append('file', file);
  const url = new URL((API_BASE || '') + '/upload-file', window.location.origin);
  if (withSignedUrl.checked) url.searchParams.set('return_signed_url', 'true');
  uploadOut.innerHTML = '<span class="muted">Uploading...</span>';
  const res = await fetch(url.toString(), { method: 'POST', body: form });
  const data = await res.json();
  renderJSON(uploadOut, data, true);

  const docGcs = (data as any)?.doc_gcs_uri as string | undefined;
  if (docGcs && docGcs.startsWith('gs://')) {
    gcsInput.value = docGcs;
    // persist with metadata if available
    saveRecent({
      uri: docGcs,
      t: Date.now(),
      ct: (data as any)?.content_type,
      size: Number((data as any)?.size) || undefined,
    });
  }
}
uploadBtn.addEventListener('click', uploadFile);

// ===== Invoke controls =====
const gcsInput = $('#gcs-uri') as HTMLInputElement;
const invokeBtn = $('#btn-invoke') as HTMLButtonElement;
const invokeOut = $('#invoke-result') as HTMLDivElement;

// restore latest doc_gcs_uri on load
restoreLatestToInput(gcsInput);

// whenever user edits the field, also persist it (so“粘贴一个旧的 GCS”也会被记忆)
gcsInput.addEventListener('change', () => {
  const uri = gcsInput.value.trim();
  if (uri && uri.startsWith('gs://')) saveRecent({ uri, t: Date.now() });
});
gcsInput.addEventListener('blur', () => {
  const uri = gcsInput.value.trim();
  if (uri && uri.startsWith('gs://')) saveRecent({ uri, t: Date.now() });
});

async function invoke() {
  const gcs = gcsInput.value.trim();
  if (!gcs) { invokeOut.innerHTML = '<span class="muted">Missing doc_gcs_uri</span>'; return; }
  invokeOut.innerHTML = '<span class="muted">Invoking...</span>';
  const res = await fetch((API_BASE || '') + '/invoke', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ gcs_url: gcs })
  });
  const data = await res.json();
  renderJSON(invokeOut, data, true);
  if ((data as any).request_id) requestIdInput.value = (data as any).request_id;
}
invokeBtn.addEventListener('click', invoke);

// ===== Poll /debug_state dashboard =====
const requestIdInput = $('#request-id') as HTMLInputElement;
const pollStartBtn = $('#btn-start-poll') as HTMLButtonElement;
const pollStopBtn = $('#btn-stop-poll') as HTMLButtonElement;
const pollIntervalInput = $('#poll-interval') as HTMLInputElement;
const stateOut = $('#state-result') as HTMLDivElement;

let pollTimer: number | null = null;

async function fetchDebugStateOnce(id: string) {
  const res = await fetch((API_BASE || '') + '/debug_state/' + encodeURIComponent(id));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function renderDashboard(s: any) {
  // Raw JSON
  renderJSON(stateOut, s, true);

  // Overview
  const run = String(s?.status || '').toUpperCase() || '—';
  const badgeRun = $('#badge-run'); setBadge(badgeRun, run, `badge-${run}`);
  text($('#ov-req'), s?.request_id);
  text($('#ov-doc'), s?.doc_gcs_uri);
  text($('#ov-created'), s?.created_at);
  text($('#ov-updated'), s?.updated_at);
  text($('#ov-state-str'), s?.state_str ?? '—');

  // runtime statuses
  const stIA = String(pick(s,'runtime.ia.status','—')).toUpperCase();
  const stID = String(pick(s,'runtime.idca.status','—')).toUpperCase();
  const stNA = String(pick(s,'runtime.naa.status','—')).toUpperCase();
  const stAA = String(pick(s,'runtime.aa.status','—')).toUpperCase();

  setBadge($('#badge-ia'), stIA, stIA==='FINISHED' ? 'badge-FINISHED' : stIA==='RUNNING' ? 'badge-RUNNING' : stIA==='FAILED' ? 'badge-FAILED' : 'badge-PENDING');
  setBadge($('#badge-idca'), stID, stID==='FINISHED' ? 'badge-FINISHED' : stID==='RUNNING' ? 'badge-RUNNING' : stID==='FAILED' ? 'badge-FAILED' : 'badge-PENDING');
  setBadge($('#badge-naa'), stNA, stNA==='FINISHED' ? 'badge-FINISHED' : stNA==='RUNNING' ? 'badge-RUNNING' : stNA==='FAILED' ? 'badge-FAILED' : 'badge-PENDING');
  setBadge($('#badge-aa'), stAA, stAA==='FINISHED' ? 'badge-FINISHED' : stAA==='RUNNING' ? 'badge-RUNNING' : stAA==='FAILED' ? 'badge-FAILED' : 'badge-PENDING');

  // IA artifacts
  const ia = pick<any>(s,'artifacts.ia',{}) || pick<any>(s,'report.ia',{}) || {};
  text($('#ia-is-pdf'), ia?.is_pdf);
  text($('#ia-size'), ia?.size);
  text($('#ia-ct'), ia?.content_type);
  text($('#ia-local'), ia?.doc_local_uri);

  // IDCA
  const idca = pick<any>(s,'artifacts.idca',{}) || pick<any>(s,'report.idca',{}) || {};
  const invStatus = (idca?.status || '—').toString().toLowerCase();
  text($('#idca-status'), idca?.status ?? '—');
  const idcaStatusEl = $('#idca-status');
  idcaStatusEl.classList.remove('idca-present','idca-implied','idca-absent');
  if (invStatus === 'present') idcaStatusEl.classList.add('idca-present');
  if (invStatus === 'implied' || invStatus === 'absent') idcaStatusEl.classList.add(`idca-${invStatus}`);
  text($('#idca-title'), idca?.title ?? '—');
  text($('#idca-authors'), (idca?.authors || []).join(', ') || '—');
  ($('#idca-summary') as HTMLElement).textContent = idca?.summary || '—';

  // Routing hint based on IDCA status
  let routeText = '—';
  if (invStatus === 'present') routeText = 'IA → IDCA(status=present) → NAA → AA';
  else if (invStatus === 'implied' || invStatus === 'absent') routeText = `IA → IDCA(status=${invStatus}) → AA (skip NAA)`;
  else routeText = 'IA → IDCA → (waiting)';
  $('#route-hint').innerHTML = `Routing: <span class="arrow">${routeText}</span>`;

  // NAA
  const naa = pick<any>(s,'artifacts.naa',{}) || pick<any>(s,'report.naa',{}) || {};
  const scores = naa?.scores || {};
  const fmtScore = (v:any)=> (v==null?'—':String(v));
  text($('#naa-scores'), `novelty=${fmtScore(scores.novelty)}, significance=${fmtScore(scores.significance)}, rigor=${fmtScore(scores.rigor)}, clarity=${fmtScore(scores.clarity)}`);
  text($('#naa-hl'), (naa?.highlights||[]).slice(0,3).join(' • ') || '—');
  text($('#naa-risks'), (naa?.risks||[]).slice(0,3).join(' • ') || '—');

  // AA
  const verdict = pick<string>(s,'artifacts.report.verdict') || pick<string>(s,'report.verdict') || '—';
  text($('#aa-verdict'), verdict);
  const aa = pick<any>(s,'internals.aa',{}) || {};
  text($('#aa-mode'), aa?.mode ?? '—');
  text($('#aa-merge'), aa?.merge_policy ?? '—');
}

async function startPolling() {
  const id = requestIdInput.value.trim();
  if (!id) { stateOut.innerHTML = '<span class="muted">Missing request_id</span>'; return; }
  const interval = Math.max(500, Number(pollIntervalInput.value) || 1500);
  const tick = async () => {
    try {
      const data = await fetchDebugStateOnce(id);
      renderDashboard(data);
      const status = String(data?.status || '').toUpperCase();
      if (status === 'FINISHED' || status === 'FAILED') stopPolling();
    } catch (e: any) {
      stateOut.innerHTML = `<span class="muted">Error: ${e?.message||e}</span>`;
      stopPolling();
    }
  };
  await tick();
  pollTimer = window.setInterval(tick, interval);
}
function stopPolling() { if (pollTimer !== null) { clearInterval(pollTimer); pollTimer = null; } }
$('#btn-start-poll').addEventListener('click', startPolling);
$('#btn-stop-poll').addEventListener('click', stopPolling);

// ===== CPC debug =====
const cpcBtn = $('#btn-cpc') as HTMLButtonElement;
const cpcOut = $('#cpc-result') as HTMLDivElement;
async function getCpc() {
  cpcOut.innerHTML = '<span class="muted">Fetching /debug/cpc ...</span>';
  const res = await fetch((API_BASE || '') + '/debug/cpc');
  const data = await res.json();
  renderJSON(cpcOut, data, true);
}
cpcBtn.addEventListener('click', getCpc);