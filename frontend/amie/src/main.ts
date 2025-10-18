import './style.css';

// ===== API base =====
const USE_PROXY = (import.meta as any).env?.VITE_USE_PROXY !== 'false';
const DIRECT_API = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000';
const API_BASE = USE_PROXY ? '' : DIRECT_API;
(document.querySelector('#api-base') as HTMLElement).textContent = USE_PROXY ? '(same-origin via proxy)' : DIRECT_API;
(document.querySelector('#proxy-note') as HTMLElement).textContent = USE_PROXY ? ' — dev proxy is on (no CORS)' : ' — direct mode';

// ===== helpers =====
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
  (el as HTMLPreElement).textContent = JSON.stringify(data ?? {}, null, 2);
}

// ===== persist recent gcs uri =====
type RecentDoc = { uri: string; t: number; ct?: string; size?: number };
const LS_KEY = 'amie_recent_docs';
const TTL_MS = 7 * 24 * 3600 * 1000;
const MAX_RECENT = 10;

function loadRecent(): RecentDoc[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    const arr: RecentDoc[] = raw ? JSON.parse(raw) : [];
    const now = Date.now();
    const pruned = arr.filter(x => typeof x?.uri === 'string' && x.uri.startsWith('gs://'))
                      .filter(x => now - (x.t || 0) <= TTL_MS);
    if (pruned.length !== arr.length) localStorage.setItem(LS_KEY, JSON.stringify(pruned));
    return pruned.sort((a,b)=> (b.t - a.t)).slice(0, MAX_RECENT);
  } catch { return []; }
}
function saveRecent(entry: RecentDoc) {
  const now = Date.now();
  const list = loadRecent().filter(x => x.uri !== entry.uri);
  list.unshift({ ...entry, t: now });
  localStorage.setItem(LS_KEY, JSON.stringify(list.slice(0, MAX_RECENT)));
}
function restoreLatestToInput(input: HTMLInputElement) {
  const list = loadRecent();
  if (list.length && !input.value.trim()) input.value = list[0].uri;
}

// ===== upload =====
const fileInput = $('#file-input') as HTMLInputElement;
const chooseBtn = $('#btn-choose') as HTMLButtonElement;
const fileName = $('#file-name') as HTMLSpanElement;
const withSignedUrl = $('#with-signed-url') as HTMLInputElement;
const uploadBtn = $('#btn-upload') as HTMLButtonElement;
const uploadOut = $('#upload-result') as HTMLPreElement;
chooseBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => { fileName.textContent = fileInput.files?.[0]?.name ?? 'No file chosen'; });

uploadBtn.addEventListener('click', async () => {
  const f = fileInput.files?.[0]; if (!f) { uploadOut.textContent = 'Please choose a file.'; return; }
  const form = new FormData(); form.append('file', f);
  const url = new URL((API_BASE || '') + '/upload-file', window.location.origin);
  if (withSignedUrl.checked) url.searchParams.set('return_signed_url','true');
  uploadOut.textContent = 'Uploading...';
  const r = await fetch(url.toString(), { method:'POST', body: form });
  const data = await r.json();
  renderPreJSON(uploadOut, data);
  const gcs = (data as any)?.doc_gcs_uri; if (gcs?.startsWith('gs://')) { gcsInput.value = gcs; saveRecent({ uri: gcs, t: Date.now(), ct: (data as any)?.content_type, size: (data as any)?.size }); }
});

// ===== invoke =====
const gcsInput = $('#gcs-uri') as HTMLInputElement;
const invokeBtn = $('#btn-invoke') as HTMLButtonElement;
const invokeOut = $('#invoke-result') as HTMLPreElement;
restoreLatestToInput(gcsInput);
gcsInput.addEventListener('change', ()=> { const v=gcsInput.value.trim(); if (v.startsWith('gs://')) saveRecent({uri:v,t:Date.now()}); });
gcsInput.addEventListener('blur', ()=> { const v=gcsInput.value.trim(); if (v.startsWith('gs://')) saveRecent({uri:v,t:Date.now()}); });
invokeBtn.addEventListener('click', async () => {
  const g = gcsInput.value.trim(); if (!g) { invokeOut.textContent = 'Missing doc_gcs_uri'; return; }
  invokeOut.textContent = 'Invoking...';
  const r = await fetch((API_BASE||'') + '/invoke', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ gcs_url: g }) });
  const data = await r.json(); renderPreJSON(invokeOut, data);
  if ((data as any)?.request_id) (document.querySelector('#request-id') as HTMLInputElement).value = (data as any).request_id;
});

// ===== poll + dashboard & focus mode =====
const requestIdInput = $('#request-id') as HTMLInputElement;
const pollStartBtn = $('#btn-start-poll') as HTMLButtonElement;
const pollStopBtn = $('#btn-stop-poll') as HTMLButtonElement;
const pollIntervalInput = $('#poll-interval') as HTMLInputElement;
const stateOut = $('#state-result') as HTMLPreElement;
const grid = $('#grid');

let pollTimer: number | null = null;
let focusAgent: string | null = null;

function enterFocus(agent: string) {
  focusAgent = agent;
  grid.classList.add('focus-mode');
  document.querySelectorAll('.card').forEach(c => c.classList.toggle('focus', (c as HTMLElement).dataset.agent === agent));
  // 显示对应 details-row，隐藏其他
  document.querySelectorAll('.details-row').forEach(x => x.classList.add('hide'));
  const panel = document.querySelector(`#details-${agent}`) as HTMLElement;
  if (panel) panel.classList.remove('hide');
}
function exitFocus() {
  focusAgent = null;
  grid.classList.remove('focus-mode');
  document.querySelectorAll('.card').forEach(c => c.classList.remove('focus'));
  document.querySelectorAll('.details-row').forEach(x => x.classList.add('hide'));
}

$('#focus-overview').addEventListener('click', ()=> enterFocus('overview'));
$('#focus-ia').addEventListener('click', ()=> enterFocus('ia'));
$('#focus-idca').addEventListener('click', ()=> enterFocus('idca'));
$('#focus-naa').addEventListener('click', ()=> enterFocus('naa'));
$('#focus-aa').addEventListener('click', ()=> enterFocus('aa'));
document.querySelectorAll('.exit-focus').forEach(btn => btn.addEventListener('click', exitFocus));
$('#exit-focus')?.addEventListener('click', exitFocus); // overview 的退出按钮

async function fetchDebugStateOnce(id: string) {
  const res = await fetch((API_BASE || '') + '/debug_state/' + encodeURIComponent(id));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const badgeRun = $('#badge-run');
const badgeIA = $('#badge-ia');
const badgeIDCA = $('#badge-idca');
const badgeNAA = $('#badge-naa');
const badgeAA = $('#badge-aa');

// minimal spans
const ovState = $('#ov-state'); const ovStateStr = $('#ov-state-str');
const iaState = $('#ia-state'); const iaStateStr = $('#ia-state-str');
const idcaState = $('#idca-state'); const idcaStateStr = $('#idca-state-str');
const naaState = $('#naa-state'); const naaStateStr = $('#naa-state-str');
const aaState = $('#aa-state'); const aaStateStr = $('#aa-state-str');

// detail pres
const ovArt = $('#overview-artifacts'); const ovInt = $('#overview-internals');
const iaArt = $('#ia-artifacts'); const iaInt = $('#ia-internals');
const idArt = $('#idca-artifacts'); const idInt = $('#idca-internals');
const naArt = $('#naa-artifacts'); const naInt = $('#naa-internals');
const aaArt = $('#aa-artifacts'); const aaInt = $('#aa-internals');

// final report
const finalCard = $('#final-card'); const badgeFinal = $('#badge-final');
const frVerdict = $('#fr-verdict'); const frIdcaStatus = $('#fr-idca-status');
const frIdcaSummary = $('#fr-idca-summary'); const frNaaScores = $('#fr-naa-scores'); const frDoc = $('#fr-doc');
const toggleFinal = $('#toggle-final') as HTMLButtonElement; const detailFinal = $('#detail-final') as HTMLPreElement;
let showFinal = false;
toggleFinal.addEventListener('click', ()=>{ showFinal=!showFinal; detailFinal.classList.toggle('hide', !showFinal); toggleFinal.textContent=showFinal?'Hide':'Details'; });

function renderDashboard(s: any) {
  // raw
  renderPreJSON(stateOut, s);

  // overview
  const run = String(s?.status || '—').toUpperCase();
  setBadge(badgeRun, run, `badge-${run}`); text(ovState, run); text(ovStateStr, s?.state_str ?? '—');

  // agents states + status_str
  const stIA = String(pick(s,'runtime.ia.status','—')).toUpperCase();
  setBadge(badgeIA, stIA, `badge-${stIA}`); text(iaState, stIA); text(iaStateStr, pick(s,'internals.ia.status_str','—'));

  const stID = String(pick(s,'runtime.idca.status','—')).toUpperCase();
  setBadge(badgeIDCA, stID, `badge-${stID}`); text(idcaState, stID); text(idcaStateStr, pick(s,'internals.idca.status_str','—'));

  const stNA = String(pick(s,'runtime.naa.status','—')).toUpperCase();
  setBadge(badgeNAA, stNA, `badge-${stNA}`); text(naaState, stNA); text(naaStateStr, pick(s,'internals.naa.status_str','—'));

  const stAA = String(pick(s,'runtime.aa.status','—')).toUpperCase();
  setBadge(badgeAA, stAA, `badge-${stAA}`); text(aaState, stAA); text(aaStateStr, pick(s,'internals.aa.status_str','—'));

  // focus panels render（只渲染当前聚焦的详情，避免卡顿）
  if (focusAgent === 'overview') {
    renderPreJSON(ovArt, s?.artifacts ?? {});
    renderPreJSON(ovInt, s?.internals ?? {});
  } else if (focusAgent === 'ia') {
    renderPreJSON(iaArt, { ia: pick(s,'artifacts.ia',{}) });
    renderPreJSON(iaInt, pick(s,'internals.ia',{}));
  } else if (focusAgent === 'idca') {
    renderPreJSON(idArt, { idca: pick(s,'artifacts.idca',{}), report: pick(s,'report.idca',{}) });
    renderPreJSON(idInt, pick(s,'internals.idca',{}));
  } else if (focusAgent === 'naa') {
    renderPreJSON(naArt, { naa: pick(s,'artifacts.naa',{}), report: pick(s,'report.naa',{}) });
    renderPreJSON(naInt, pick(s,'internals.naa',{}));
  } else if (focusAgent === 'aa') {
    renderPreJSON(aaArt, { report: pick(s,'artifacts.report',{}) });
    renderPreJSON(aaInt, pick(s,'internals.aa',{}));
  }

  // final report
  if (run === 'FINISHED') {
    finalCard.classList.remove('hide'); setBadge(badgeFinal, 'FINISHED','badge-FINISHED');
    const verdict = pick<string>(s,'artifacts.report.verdict') || pick<string>(s,'report.verdict') || '—'; text(frVerdict, verdict);
    const idca = pick<any>(s,'artifacts.idca',{}) || pick<any>(s,'report.idca',{}) || {};
    text(frIdcaStatus, idca?.status ?? '—'); text(frIdcaSummary, idca?.summary ?? '—');
    const naa = pick<any>(s,'artifacts.naa',{}) || pick<any>(s,'report.naa',{}) || {}; const sc = naa?.scores || {};
    const fmt=(v:any)=> v==null?'—':String(v);
    text(frNaaScores, `novelty=${fmt(sc.novelty)}, significance=${fmt(sc.significance)}, rigor=${fmt(sc.rigor)}, clarity=${fmt(sc.clarity)}`);
    text(frDoc, s?.doc_gcs_uri || '—');
    if (showFinal) renderPreJSON(detailFinal, { artifacts: { report: pick(s,'artifacts.report',{}) }, internals: { aa: pick(s,'internals.aa',{}) } });
  } else {
    finalCard.classList.add('hide'); showFinal=false; detailFinal.classList.add('hide'); toggleFinal.textContent='Details';
  }
}

async function startPolling() {
  const id = requestIdInput.value.trim(); if (!id) { stateOut.textContent = 'Missing request_id'; return; }
  const interval = Math.max(500, Number(pollIntervalInput.value) || 1500);
  const tick = async () => {
    try {
      const data = await fetchDebugStateOnce(id);
      renderDashboard(data);
      const status = String(data?.status || '').toUpperCase();
      if (status === 'FINISHED' || status === 'FAILED') stopPolling();
    } catch (e: any) { stateOut.textContent = `Error: ${e?.message||e}`; stopPolling(); }
  };
  await tick(); pollTimer = window.setInterval(tick, interval);
}
function stopPolling() { if (pollTimer !== null) { clearInterval(pollTimer); pollTimer = null; } }
pollStartBtn.addEventListener('click', startPolling);
pollStopBtn.addEventListener('click', stopPolling);

// CPC
const cpcBtn = $('#btn-cpc') as HTMLButtonElement;
const cpcOut = $('#cpc-result') as HTMLPreElement;
cpcBtn.addEventListener('click', async ()=> {
  cpcOut.textContent = 'Fetching /debug/cpc ...';
  const r = await fetch((API_BASE||'') + '/debug/cpc'); const data = await r.json(); renderPreJSON(cpcOut, data);
});
