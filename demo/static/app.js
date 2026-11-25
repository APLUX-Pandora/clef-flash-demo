'use strict';
let connected = false, modelReady = false, initialized = false, recoveryBusy = false;
const $ = id => document.getElementById(id);
let presets = [], selected = null, uploadData = null, hasImage = false, questions = [], last = null, busy = false;
let uploadedURL = null, activeController = null, uploadGeneration = 0, readingImage = false;
function cancelUpload() {
  uploadGeneration += 1; readingImage = false;
  $('run').disabled = busy || !modelReady || recoveryBusy;
}
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const error = message => { $('error').textContent = message; $('error').hidden = !message; };
function dirty() {
  questions.forEach(q => { delete q._result; });
  document.querySelectorAll('.option-result').forEach(n => n.remove());
  document.querySelectorAll('.option.winner').forEach(n => n.classList.remove('winner'));
  if (last) { $('metrics-status').textContent = 'Last completed run · inputs changed'; $('result-state').textContent = 'Inputs changed · run again to update'; $('result-state').className = 'result-state stale'; }
  document.querySelectorAll('.preset').forEach(n => n.classList.remove('active'));
}
function syncCount() {
  $('question-count').textContent = questions.length > 1 ? `${questions.length} questions` : '';
  $('add-question').disabled = busy || questions.length >= 12;
}
function showImage(src, name) {
  hasImage = !!src;
  document.querySelector('.input-panel').classList.toggle('has-image', hasImage);
  $('image-controls').hidden = !src;
  $('preview').hidden = !src; $('no-image').hidden = !!src;
  $('enlarge').hidden = !src; $('remove-image').hidden = !src;
  if (src) { $('preview').src = src; $('full-image').src = src; }
  else { $('preview').removeAttribute('src'); $('full-image').removeAttribute('src'); }
  $('image-name').textContent = name;
}
function selectPreset(p) {
  cancelUpload();
  selected = p; uploadData = null;
  if (uploadedURL) { URL.revokeObjectURL(uploadedURL); uploadedURL = null; }
  $('upload').value = '';
  questions = Object.entries(p.request.questions).map(([id, q]) => Object.assign({id}, structuredClone(q)));
  const state = p.request.state;
  $('state').value = typeof state === 'string' ? state : state && typeof state.task === 'string' && Object.keys(state).length === 1 ? state.task : JSON.stringify(state);
  showImage(p.file ? `/media/${encodeURIComponent(p.file)}` : null, p.source);
  dirty(); renderQuestions(); $('questions').scrollTop = 0; error('');
  document.querySelectorAll('.preset').forEach(n => n.classList.toggle('active', n.dataset.id === p.id));
}
function resetInputs() {
  cancelUpload();
  selected = null; uploadData = null;
  if (uploadedURL) { URL.revokeObjectURL(uploadedURL); uploadedURL = null; }
  $('upload').value = ''; $('state').value = '';
  questions = [{id: 'answer', type: 'noul', instructions: ''}];
  last = null; $('results').replaceChildren(); renderMetrics();
  $('summary-time').textContent = '';
  $('result-state').textContent = 'Your answer will appear here.'; $('result-state').className = 'result-state';
  showImage(null, ''); dirty(); renderQuestions(); error('');
}
function renderQuestions() {
  $('questions').replaceChildren();
  questions.forEach((q, index) => {
    const card = el('div', 'question');
    if (questions.length > 1) {
      const top = el('div', 'question-label'); top.append(el('span', '', `Question ${index + 1}`));
      const remove = el('button', 'text-button', 'Remove');
      remove.onclick = () => { questions.splice(index, 1); dirty(); renderQuestions(); };
      top.append(remove); card.append(top);
    }
    const prompt = el('textarea'); prompt.id = `prompt-${index}`; prompt.rows = 2; prompt.value = q.instructions || '';
    prompt.setAttribute('aria-label', `Question ${index + 1}`); prompt.placeholder = 'What would you like to decide?';
    prompt.oninput = () => { q.instructions = prompt.value; dirty(); };
    card.append(prompt);
    const options = el('details', 'question-options'); options.open = q._editing ?? (index === 0);
    const description = q.type === 'noul' ? 'Yes / no' : q.type === 'score' ? `Score · ${q.criteria.length} levels` : `Choose from ${Object.keys(q.criteria).length} answers`;
    options.append(el('summary', '', `${description} · Options`));
    options.ontoggle = () => { q._editing = options.open; };
    const format = el('div', 'format-row'); format.append(el('span', '', 'Answer format'));
    const type = el('select'); type.setAttribute('aria-label', `Question ${index + 1} type`);
    [['choice', 'Choice'], ['noul', 'Yes / no'], ['score', 'Score']].forEach(([value, name]) => { const opt = el('option', '', name); opt.value = value; type.append(opt); });
    type.value = q.type;
    type.onchange = () => { q.type = type.value; q._editing = true; q.criteria = q.type === 'score' ? ['Low', 'Medium', 'High'] : q.type === 'choice' ? {A: 'Option A', B: 'Option B'} : undefined; dirty(); renderQuestions(); };
    format.append(type); options.append(format);
    if (q.type !== 'noul') {
      const entries = q.type === 'score' ? q.criteria.map((value, i) => [String(i), value]) : Object.entries(q.criteria);
      options.classList.toggle('named-options', entries.some(([key]) => key.length > 2));
      entries.forEach(([key, value]) => {
        const row = el('div', 'option'); const field = el('textarea'); field.rows = 1; field.value = value; field.setAttribute('aria-label', `Question ${index + 1}, option ${key}`);
        field.oninput = () => { q.criteria[key] = field.value; field.style.height = 'auto'; field.style.height = Math.min(140, field.scrollHeight + 2) + 'px'; dirty(); };
        const rm = el('button', 'remove-option', '×'); rm.setAttribute('aria-label', `Remove option ${key}`); rm.disabled = entries.length <= 2;
        rm.onclick = () => { if (q.type === 'score') q.criteria.splice(Number(key), 1); else delete q.criteria[key]; dirty(); renderQuestions(); };
        row.append(el('span', 'option-key', key), field, rm);
        if (q._result) {
          const result = q._result;
          const probability = result.probabilities[String(key)];
          if (probability !== undefined) {
            const badge = el('span', 'option-result', `${(probability * 100).toFixed(2)}%`);
            badge.setAttribute('aria-label', `Option ${key} probability ${(probability * 100).toFixed(2)} percent`);
            row.append(badge);
            row.classList.toggle('winner', String(key) === result.best);
          }
        }
        options.append(row);
      });
      const add = el('button', 'text-button', '+ Add option'); add.disabled = entries.length >= 12;
      add.onclick = () => {
        if (q.type === 'score') q.criteria.push(`Level ${q.criteria.length}`);
        else { const key = 'ABCDEFGHIJKL'.split('').find(k => !(k in q.criteria)); q.criteria[key] = ''; }
        dirty(); renderQuestions();
      };
      options.append(add);
    } else {
      options.append(el('p', 'hint', 'Returns the probability of Yes. No answer choices are needed.'));
      if (q._result) {
        for (const [key, probability] of Object.entries(q._result.probabilities)) {
          const row = el('div', 'option-result binary-probability');
          row.append(el('span', '', key === 'true' ? 'Yes' : 'No'), el('strong', '', `${(probability * 100).toFixed(2)}%`));
          options.append(row);
        }
      }
    }
    card.append(options);
    $('questions').append(card);
  });
  syncCount();
  requestAnimationFrame(() => document.querySelectorAll('.option textarea').forEach(n => { n.style.height = 'auto'; n.style.height = Math.min(140, n.scrollHeight + 2) + 'px'; }));
}
function buildRequest() {
  let state = $('state').value;
  if (selected && typeof selected.request.state === 'object' && selected.request.state !== null && Object.keys(selected.request.state).length === 1 && state === selected.request.state.task) state = structuredClone(selected.request.state);
  const qs = {};
  for (const q of questions) {
    if (!q.instructions.trim()) throw new Error('Enter instructions for every question.');
    const entry = {type: q.type, instructions: q.instructions};
    if (q.type !== 'noul') {
      const vals = Object.values(q.criteria);
      if (vals.length < 2 || vals.some(v => !v.trim())) throw new Error('Fill in at least two nonempty options for every choice or score question.');
      entry.criteria = structuredClone(q.criteria);
    }
    qs[q.id] = entry;
  }
  return {model: 'decision-studio', state, questions: qs};
}
function renderMetrics(timing = null) {
  const tm = timing;
  const rows = [
    ['Inference', tm ? `${(tm.total_ms / 1000).toFixed(2)} s` : '—'],
    ['Input tokens', tm ? `${tm.tokens}` : '—'],
    ['Vision encoder', tm ? `${tm.vit_ms.toFixed(0)} ms` : '—'],
    ['Prefill', tm ? `${tm.prefill_ms.toFixed(0)} ms` : '—'],
    ['Decision head', tm ? `${tm.head_ms.toFixed(0)} ms` : '—'],
    ['Image / encoding', tm ? `${(tm.image_prep_ms + tm.encode_ms).toFixed(0)} ms` : '—']
  ];
  const grid = el('div', 'metrics-grid');
  for (const [name, value] of rows) {
    const cell = el('div', 'metric'); cell.append(el('span', '', name), el('strong', '', value)); grid.append(cell);
  }
  $('metrics').replaceChildren(grid);
  $('metrics-status').textContent = tm ? 'Last completed run · excludes model loading' : 'Run a decision to view performance';
}
function renderResults(data, request) {
  const response = data.response; $('results').replaceChildren();
  for (const [id, answer] of Object.entries(response.answers)) {
    const q = request.questions[id]; const logits = response.decision.logits[id];
    const max = Math.max(...logits.logits); const weights = logits.logits.map(x => Math.exp(x - max)); const sum = weights.reduce((a, b) => a + b, 0); const probs = weights.map(x => x / sum);
    const best = probs.indexOf(Math.max(...probs));
    const chosen = answer.type === 'choice' ? answer.choice : answer.type === 'noul' ? (answer.noul >= .5 ? 'Yes' : 'No') : `${answer.score.toFixed(2)} / ${q.criteria.length - 1}`;
    const card = el('article', 'decision');
    if (Object.keys(response.answers).length > 1) card.append(el('h3', '', q.instructions));
    card.append(el('div', 'answer', chosen));
    card.append(el('div', 'confidence', answer.type === 'noul' ? `P(true) ${(answer.noul * 100).toFixed(2)}%` : answer.type === 'score' ? 'Expected score across the ordered levels' : `Selected option · ${(answer.confidence * 100).toFixed(2)}%`));
    const current = questions.find(question => question.id === id);
    if (current) {
      current._result = {probabilities: Object.fromEntries(logits.options.map((key, i) => [String(key), probs[i]])),
                         best: String(logits.options[best])};
    }
    $('results').append(card);
  }
  renderQuestions();
  const tm = response.decision.timing;
  $('summary-time').textContent = `${(tm.total_ms / 1000).toFixed(2)} s`;
  renderMetrics(tm);
  $('result-state').textContent = 'Complete'; $('result-state').className = 'result-state success';
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('.input-panel input,.input-panel button,.input-panel textarea,.question-panel button,.question-panel textarea,.question-panel select').forEach(n => n.disabled = value);
  $('run').disabled = value; $('run').textContent = value ? 'Running…' : 'Run decision →';
  if (!value) renderQuestions();
  $('run').disabled = value || !modelReady || readingImage || recoveryBusy;
}
async function run() {
  if (!modelReady || recoveryBusy || busy) return;
  if (readingImage) { error('Wait for the image to finish loading.'); return; }
  error(''); let request;
  try { request = buildRequest(); } catch (e) { error(`Check the question configuration: ${e.message}`); return; }
  setBusy(true); const start = performance.now();
  $('result-state').textContent = 'Running on the device…'; $('result-state').className = 'result-state';
  const timer = setInterval(() => $('elapsed').textContent = `${((performance.now() - start) / 1000).toFixed(1)} s elapsed`, 100);
  activeController = new AbortController();
  const timeout = setTimeout(() => activeController.abort(), 180000);
  try {
    const body = {request};
    if (hasImage) { if (uploadData !== null) body.image_base64 = uploadData; else body.preset_id = selected.id; }
    else if (selected && !selected.file) body.preset_id = selected.id;
    const res = await fetch('/api/run', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal: activeController.signal});
    let data;
    try { data = await res.json(); }
    catch (_) {
      modelReady = false; $('retry-connection').hidden = false;
      $('connection').textContent = 'Connection needs checking'; $('connection').className = 'status';
      throw new Error(`HTTP ${res.status}: the service returned an invalid response. Check the connection.`);
    }
    if (!res.ok && res.status >= 500 && !data.reload_required) {
      modelReady = false; $('retry-connection').hidden = false;
      $('connection').textContent = 'Connection needs checking'; $('connection').className = 'status';
    }
    if (data.reload_required) { modelReady = false; $('reload-model').hidden = false; $('connection').textContent = 'Model needs reloading'; $('connection').className = 'status'; }
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    last = Object.assign({request}, data); renderResults(data, request);
  } catch (e) {
    if (e instanceof TypeError || e.name === 'AbortError') { connected = false; modelReady = false; $('retry-connection').hidden = false; $('connection').textContent = 'Connection needs checking'; $('connection').className = 'status'; }
    error(e.name === 'AbortError' ? 'The request timed out. The device may still be finishing it; wait before retrying.' : e.message);
    $('result-state').textContent = last ? 'Request failed · previous results are out of date' : 'No result · request failed'; $('result-state').className = 'result-state stale';
  } finally { clearInterval(timer); clearTimeout(timeout); activeController = null; $('elapsed').textContent = ''; setBusy(false); }
}
$('state').oninput = dirty;
$('upload-button').onclick = () => $('upload').click();
$('no-image').onclick = () => $('upload').click();
$('reset').onclick = resetInputs;
$('remove-image').onclick = () => { cancelUpload(); uploadData = null; $('upload').value = ''; if (uploadedURL) { URL.revokeObjectURL(uploadedURL); uploadedURL = null; } showImage(null, 'No image · text-only'); dirty(); };
$('add-question').onclick = () => { const id = `q_${Date.now()}_${questions.length}`; questions.push({id, type: 'noul', instructions: ''}); dirty(); renderQuestions(); $('questions').lastElementChild.querySelector('textarea').focus(); };
$('run').onclick = run;
$('upload').onchange = async () => {
  const file = $('upload').files[0]; if (!file) return;
  const generation = ++uploadGeneration;
  readingImage = false; $('run').disabled = busy || !modelReady || recoveryBusy;
  error('');
  if (!['image/jpeg', 'image/png'].includes(file.type) || file.size > 8 * 1024 * 1024) { error('Choose a JPEG or PNG image up to 8 MiB.'); $('upload').value = ''; return; }
  readingImage = true; $('run').disabled = true;
  try {
    const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]); reader.onerror = () => reject(new Error('Could not read this image.')); reader.readAsDataURL(file); });
    if (generation !== uploadGeneration) return;
    uploadData = data;
    if (uploadedURL) URL.revokeObjectURL(uploadedURL); uploadedURL = URL.createObjectURL(file);
    showImage(uploadedURL, file.name); dirty();
  } catch (e) { if (generation === uploadGeneration) error(e.message); }
  finally { if (generation === uploadGeneration) { readingImage = false; $('run').disabled = busy || !modelReady || recoveryBusy; } }
};
$('enlarge').onclick = () => $('image-dialog').showModal();
$('close-image').onclick = () => $('image-dialog').close();
function showStatus(info) {
  connected = true; modelReady = info.ready === true && !info.busy;
  $('connection').textContent = info.state === 'loading' ? 'Loading model…' : info.reload_required ? 'Model needs reloading' : info.busy ? 'Device busy' : 'Device ready';
  $('connection').className = modelReady ? 'status ready' : 'status';
  $('retry-connection').hidden = modelReady;
  $('reload-model').hidden = !info.reload_required;
  $('reload-model').disabled = recoveryBusy || info.busy || info.state === 'loading';
  $('run').disabled = busy || !modelReady || readingImage || recoveryBusy;
}
async function fetchJSON(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  } finally { clearTimeout(timer); }
}
async function init() {
  $('retry-connection').disabled = true;
  try {
    const [info, available] = await Promise.all([fetchJSON('/api/info'), fetchJSON('/api/presets')]);
    if (!initialized) {
      presets = available;
      const names = ['Skiing', 'Sandwich', 'Food web'];
      $('presets').replaceChildren();
      for (const [i, p] of presets.entries()) { const button = el('button', 'preset', names[i] || p.subtitle); button.dataset.id = p.id; button.title = `Load template: ${p.subtitle}`; button.onclick = () => selectPreset(p); $('presets').append(button); }
      resetInputs(); initialized = true;
    }
    showStatus(info); error('');
  } catch (e) {
    connected = false; modelReady = false;
    $('connection').textContent = 'Device unavailable'; $('connection').className = 'status';
    $('retry-connection').hidden = false; $('reload-model').hidden = true; $('run').disabled = true;
    error(e.message + ' Use Retry connection after the service is available.');
  } finally { $('retry-connection').disabled = recoveryBusy; }
}
$('retry-connection').onclick = init;
$('reload-model').onclick = async () => {
  if (busy || recoveryBusy || !connected) return;
  recoveryBusy = true; modelReady = false;
  $('reload-model').disabled = true; $('retry-connection').disabled = true; $('run').disabled = true;
  $('connection').textContent = 'Loading model…'; error('');
  try {
    await fetchJSON('/api/reload', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}, 180000);
    recoveryBusy = false; await init();
  } catch (e) {
    recoveryBusy = false;
    await init(); error(e.message + ' Check the connection and model status before trying again.');
  } finally { recoveryBusy = false; $('retry-connection').disabled = false; $('reload-model').disabled = false; }
};
init();
