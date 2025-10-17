import './style.css';

// ===== API base (vite proxy on by default) =====
const USE_PROXY = (import.meta as any).env?.VITE_USE_PROXY !== 'false'; // default true
const DIRECT_API = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000';
const API_BASE = USE_PROXY ? '' : DIRECT_API;
(document.querySelector('#api-base') as HTMLElement).textContent = USE_PROXY ? '(same-origin via proxy)' : DIRECT_API;
(document.querySelector('#proxy-note') as HTMLElement).textContent = USE_PROXY ? ' — dev proxy is on (no CORS)' : ' — direct mode';

// ===== Helpers =====
const $ = (sel: string) => document.querySelector(sel)! as HTMLElement;
function text(el: HTMLElement, v: any) { el.textContent = v == null ? '—' : String(v); }
function setBadge(el: HTMLElement, label: string, cls?: string) {
  el.className = `badge ${cls || ''}`.trim();
  el.textContent = label || '—';
}
function pick<T=any>(obj: any, path: string, fallback?: T): T | undefined {
  try { return path.split('.').reduce((o,k)=> (o==null?undefined:o[k]), obj) ?? fallback; }
  catch { return fallback; }
}
function renderPreJSON(el: HTMLElement, data: any) {
  (el as HTMLPreElement).textContent = JSON.stringify(data, null, 2);
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
  const filtered = list.filter(x => x.uri !== entry.uri);
  filtered.unshift({ ...entry, t: now });
  localStorage.setItem(LS_KEY, JSON.stringify(filtered.slice(0, MAX_RECENT)));
}
function restoreLatestToInput(input: HTMLInputElement) {
  const list = loadRecent();
  if (list.length && !input.value.trim()) input.value = list[0].uri;
}

// ===== Upload controls =====
const fileInput = $('#file-input') as HTMLInputElement;
const chooseBtn = $('#btn-choose') as HTMLButtonElement;
const fileName = $('#file-name') as HTMLSpanElement;
const withSignedUrl = $('#with-signed-url') as HTMLInputElement;

const uploadBtn = $('#btn-upload') as HTMLButtonElement;
const uploadOut = $('#upload-result') as HTMLPreElement;

chooseBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  const f = fileInput.files?.[0];
  fileName.textContent = f ? f.name : 'No file chosen';
});

async function uploadFile() {
  const file = fileInput.files?.[0];
  if (!file) { uploadOut.textContent = 'Please choose a file.'; return; }
  const form = new FormData(); form.append('file', file);
  const url = new URL((API_BASE || '') + '/upload-file', window.location.origin);
  if (withSignedUrl.checked) url.searchParams.set('return_signed_url', 'true');
  uploadOut.textContent = 'Uploading...';
  const res = await fetch(url.toString(), { method: 'POST', body: form });
  const data = await res.json();
  renderPreJSON(uploadOut, data);

  const docGcs = (data as any)?.doc_gcs_uri as string | undefined;
  if (docGcs && docGcs.startsWith('gs://')) {
    gcsInput.value = docGcs;
    saveRecent({ uri: docGcs, t: Date.now(), ct: (data as any)?.content_type, size: Number((data as any)?.size) || undefined });
  }
}
uploadBtn.addEventListener('click', uploadFile);

// ===== Invoke controls =====
const gcsInput = $('#gcs-uri') as HTMLInputElement;
const invokeBtn = $('#btn-invoke') as HTMLButtonElement;
const invokeOut = $('#invoke-result') as HTMLPreElement;

restoreLatestToInput(gcsInput);
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
  if (!gcs) { invokeOut.textContent = 'Missing doc_gcs_uri'; return; }
  invokeOut.textContent = 'Invoking...';
  const res = await fetch((API_BASE || '') + '/invoke', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ gcs_url: gcs })
  });
  const data = await res.json();
  renderPreJSON(invokeOut, data);
  if ((data as any).request_id) requestIdInput.value = (data as any).request_id;
}
invokeBtn.addEventListener('click', invoke);

// ===== Poll /debug_state with minimal fields + per-agent details =====
const requestIdInput = $('#request-id') as HTMLInputElement;
const pollStartBtn = $('#btn-start-poll') as HTMLButtonElement;
const pollStopBtn = $('#btn-stop-poll') as HTMLButtonElement;
const pollIntervalInput = $('#poll-interval') as HTMLInputElement;
const stateOut = $('#state-result') as HTMLPreElement;

// overview minimal spans
const ovState = $('#ov-state');
const ovStateStr = $('#ov-state-str');

// agent minimal spans
const iaState = $('#ia-state');
const iaStateStr = $('#ia-state-str');
const idcaState = $('#idca-state');
const idcaStateStr = $('#idca-state-str');
const naaState = $('#naa-state');
const naaStateStr = $('#naa-state-str');
const aaState = $('#aa-state');
const aaStateStr = $('#aa-state-str');

// badges
const badgeRun = $('#badge-run');
const badgeIA = $('#badge-ia');
const badgeIDCA = $('#badge-idca');
const badgeNAA = $('#badge-naa');
const badgeAA = $('#badge-aa');

// detail toggles + panels
const toggleOverview = $('#toggle-overview') as HTMLButtonElement;
const toggleIA = $('#toggle-ia') as HTMLButtonElement;
const toggleIDCA = $('#toggle-idca') as HTMLButtonElement;
const toggleNAA = $('#toggle-naa') as HTMLButtonElement;
const toggleAA = $('#toggle-aa') as HTMLButtonElement;
const detailOverview = $('#detail-overview') as HTMLPreElement;
const detailIA = $('#detail-ia') as HTMLPreElement;
const detailIDCA = $('#detail-idca') as HTMLPreElement;
const detailNAA = $('#detail-naa') as HTMLPreElement;
const detailAA = $('#detail-aa') as HTMLPreElement;

let showOverview = false, showIA = false, showIDCA = false, showNAA = false, showAA = false;
function bindToggle(btn: HTMLButtonElement, get: ()=>boolean, set:(v:boolean)=>void, panel: HTMLElement) {
  btn.addEventListener('click', ()=>{
    const nv = !get(); set(nv);
    panel.classList.toggle('hide', !nv);
    btn.textContent = nv ? 'Hide' : 'Details';
  });
}
bindToggle(toggleOverview, ()=>showOverview, (v)=>showOverview=v, detailOverview);
bindToggle(toggleIA, ()=>showIA, (v)=>showIA=v, detailIA);
bindToggle(toggleIDCA, ()=>showIDCA, (v)=>showIDCA=v, detailIDCA);
bindToggle(toggleNAA, ()=>showNAA, (v)=>showNAA=v, detailNAA);
bindToggle(toggleAA, ()=>showAA, (v)=>showAA=v, detailAA);

let pollTimer: number | null = null;

async function fetchDebugStateOnce(id: string) {
  const res = await fetch((API_BASE || '') + '/debug_state/' + encodeURIComponent(id));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function renderDashboard(s: any) {
  // Raw JSON
  renderPreJSON(stateOut, s);

  // Overview minimal
  const run = String(s?.status || '').toUpperCase() || '—';
  setBadge(badgeRun, run, `badge-${run}`);
  text(ovState, run);
  text(ovStateStr, s?.state_str ?? '—');

  // IA minimal
  const stIA = String(pick(s, 'runtime.ia.status', '—')).toUpperCase();
  setBadge(badgeIA, stIA, `badge-${stIA}`);
  text(iaState, stIA);
  text(iaStateStr, pick(s, 'internals.ia.state_str', '—'));

  // IDCA minimal
  const stID = String(pick(s, 'runtime.idca.status', '—')).toUpperCase();
  setBadge(badgeIDCA, stID, `badge-${stID}`);
  text(idcaState, stID);
  text(idcaStateStr, pick(s, 'internals.idca.state_str', '—'));

  // NAA minimal
  const stNA = String(pick(s, 'runtime.naa.status', '—')).toUpperCase();
  setBadge(badgeNAA, stNA, `badge-${stNA}`);
  text(naaState, stNA);
  text(naaStateStr, pick(s, 'internals.naa.state_str', '—'));

  // AA minimal
  const stAA = String(pick(s, 'runtime.aa.status', '—')).toUpperCase();
  setBadge(badgeAA, stAA, `badge-${stAA}`);
  text(aaState, stAA);
  text(aaStateStr, pick(s, 'internals.aa.state_str', '—'));

  // Details content (only when opened):
  if (showOverview) {
    renderPreJSON(detailOverview, {
      artifacts: s?.artifacts ?? {},
      internals: s?.internals ?? {}
    });
  }
  if (showIA) {
    renderPreJSON(detailIA, {
      artifacts: { ia: pick(s,'artifacts.ia',{}) },
      internals: pick(s,'internals.ia',{})
    });
  }
  if (showIDCA) {
    renderPreJSON(detailIDCA, {
      artifacts: { idca: pick(s,'artifacts.idca',{}), report: pick(s,'report.idca',{}) },
      internals: pick(s,'internals.idca',{})
    });
  }
  if (showNAA) {
    renderPreJSON(detailNAA, {
      artifacts: { naa: pick(s,'artifacts.naa',{}), report: pick(s,'report.naa',{}) },
      internals: pick(s,'internals.naa',{})
    });
  }
  if (showAA) {
    renderPreJSON(detailAA, {
      artifacts: { report: pick(s,'artifacts.report',{}) ?? {} },
      internals: pick(s,'internals.aa',{})
    });
  }
}

async function startPolling() {
  const id = (document.querySelector('#request-id') as HTMLInputElement).value.trim();
  if (!id) { stateOut.textContent = 'Missing request_id'; return; }
  const interval = Math.max(500, Number((document.querySelector('#poll-interval') as HTMLInputElement).value) || 1500);
  const tick = async () => {
    try {
      const data = await fetchDebugStateOnce(id);
      renderDashboard(data);
      const status = String(data?.status || '').toUpperCase();
      if (status === 'FINISHED' || status === 'FAILED') stopPolling();
    } catch (e: any) {
      stateOut.textContent = `Error: ${e?.message||e}`;
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
const cpcOut = $('#cpc-result') as HTMLPreElement;
async function getCpc() {
  cpcOut.textContent = 'Fetching /debug/cpc ...';
  const res = await fetch((API_BASE || '') + '/debug/cpc');
  const data = await res.json();
  renderPreJSON(cpcOut, data);
}
cpcBtn.addEventListener('click', getCpc);
