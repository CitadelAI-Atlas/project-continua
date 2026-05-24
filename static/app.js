// continua dashboard — vanilla JS, no framework.

const state = {
  vocab: [],
  metaVocab: [],
  chanceRate: 0.125,
  metaChanceRate: 1 / 6,
  selectedLearn: null,
  selectedMeta: null,
  session: null,        // content-only session
  layered: null,        // layered session
};

const player = document.getElementById('player');

// --- Mode switching ---
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => switchMode(btn.dataset.mode));
});

function switchMode(mode) {
  document.querySelectorAll('.mode-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.mode === mode);
  });
  document.querySelectorAll('.mode').forEach(s => {
    s.classList.toggle('active', s.id === mode);
  });
  if (mode === 'history') loadHistory();
}

// --- Bootstrap ---
async function init() {
  const [vocabRes, metaRes] = await Promise.all([
    fetch('/api/vocabulary'),
    fetch('/api/metadata'),
  ]);
  const vocabData = await vocabRes.json();
  const metaData = await metaRes.json();

  state.vocab = vocabData.symbols;
  state.chanceRate = vocabData.chance_rate;
  state.metaVocab = metaData.symbols;
  state.metaChanceRate = metaData.chance_rate;

  renderLearnGrid();
  renderGuessGrid();
  renderMetaGrid();
  renderLayeredGrids();
}

// --- Learn mode ---
function renderLearnGrid() {
  const grid = document.getElementById('learn-grid');
  grid.innerHTML = '';
  state.vocab.forEach(sym => {
    const btn = document.createElement('button');
    btn.className = 'symbol-btn';
    btn.textContent = sym.name;
    btn.addEventListener('click', () => selectLearn(sym, btn));
    grid.appendChild(btn);
  });
}

function selectLearn(sym, btn) {
  state.selectedLearn = sym;
  document.querySelectorAll('#learn-grid .symbol-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  document.getElementById('learn-name').textContent = sym.name;
  document.getElementById('learn-meaning').textContent = sym.meaning;
  document.getElementById('learn-rationale').textContent = sym.rationale;
  const playBtn = document.getElementById('learn-play');
  playBtn.disabled = false;
  playAudio(sym.name);
}

document.getElementById('learn-play').addEventListener('click', () => {
  if (state.selectedLearn) playAudio(state.selectedLearn.name);
});

// --- Audio playback ---
function playAudio(name) {
  player.src = `/audio/${name}.wav?t=${Date.now()}`;
  player.play().catch(err => console.error('audio play failed:', err));
}

// --- Test mode ---
document.getElementById('test-start').addEventListener('click', startSession);
document.getElementById('restart-btn').addEventListener('click', () => {
  document.getElementById('test-results').classList.add('hidden');
  document.getElementById('test-intro').classList.remove('hidden');
});
document.getElementById('goto-history').addEventListener('click', () => switchMode('history'));
document.getElementById('hear-btn').addEventListener('click', () => playCurrent());
document.getElementById('replay-btn').addEventListener('click', () => playCurrent(true));

function startSession() {
  const total = parseInt(document.getElementById('trial-count').value, 10);
  const notes = document.getElementById('session-notes').value.trim();

  state.session = {
    trials: [],
    idx: 0,
    total,
    notes,
    order: buildRandomOrder(total),
    current: null,
    startTimestamp: Date.now(),
  };

  document.getElementById('test-intro').classList.add('hidden');
  document.getElementById('test-results').classList.add('hidden');
  document.getElementById('test-active').classList.remove('hidden');

  document.getElementById('trial-total').textContent = total;
  updateScoreDisplay();
  nextTrial();
}

function buildRandomOrder(n) {
  const names = state.vocab.map(s => s.name);
  const order = [];
  for (let i = 0; i < n; i++) {
    const pool = names.filter(name => order.length === 0 || name !== order[order.length - 1]);
    order.push(pool[Math.floor(Math.random() * pool.length)]);
  }
  return order;
}

function nextTrial() {
  if (state.session.idx >= state.session.total) {
    finishSession();
    return;
  }
  const truth = state.session.order[state.session.idx];
  state.session.current = {
    truth,
    answered: false,
    playStart: null,
  };

  document.getElementById('trial-num').textContent = state.session.idx + 1;
  document.getElementById('trial-feedback').textContent = '';
  document.getElementById('trial-feedback').className = 'feedback';

  // Reset guess grid
  document.querySelectorAll('#guess-grid .symbol-btn').forEach(b => {
    b.classList.remove('correct', 'incorrect', 'selected');
    b.disabled = true; // disabled until they hit "Hear"
  });
  document.getElementById('hear-btn').disabled = false;
  document.getElementById('hear-btn').textContent = '▶ Hear symbol';
  document.getElementById('replay-btn').disabled = true;
}

function playCurrent(isReplay = false) {
  if (!state.session?.current) return;
  if (!isReplay) {
    state.session.current.playStart = Date.now();
    // Enable guess buttons after first listen
    document.querySelectorAll('#guess-grid .symbol-btn').forEach(b => { b.disabled = false; });
    document.getElementById('hear-btn').disabled = true;
    document.getElementById('hear-btn').textContent = '— played —';
    document.getElementById('replay-btn').disabled = false;
  }
  playAudio(state.session.current.truth);
}

function renderGuessGrid() {
  const grid = document.getElementById('guess-grid');
  grid.innerHTML = '';
  state.vocab.forEach(sym => {
    const btn = document.createElement('button');
    btn.className = 'symbol-btn';
    btn.textContent = sym.name;
    btn.dataset.name = sym.name;
    btn.disabled = true;
    btn.addEventListener('click', () => recordGuess(sym.name, btn));
    grid.appendChild(btn);
  });
}

function recordGuess(guess, btn) {
  if (!state.session?.current || state.session.current.answered) return;

  const truth = state.session.current.truth;
  const correct = guess === truth;
  const responseMs = state.session.current.playStart
    ? Date.now() - state.session.current.playStart
    : 0;

  state.session.current.answered = true;
  state.session.trials.push({
    index: state.session.idx + 1,
    truth,
    guess,
    correct,
    response_ms: responseMs,
  });

  // Disable all + paint feedback
  document.querySelectorAll('#guess-grid .symbol-btn').forEach(b => {
    b.disabled = true;
    if (b.dataset.name === truth) b.classList.add('correct');
    if (b.dataset.name === guess && !correct) b.classList.add('incorrect');
  });

  const fb = document.getElementById('trial-feedback');
  if (correct) {
    fb.textContent = `OK — ${truth}`;
    fb.className = 'feedback ok';
  } else {
    fb.textContent = `X — heard ${truth}, you said ${guess}`;
    fb.className = 'feedback bad';
  }
  updateScoreDisplay();

  // Advance after a short pause so the user can absorb the feedback
  setTimeout(() => {
    state.session.idx++;
    nextTrial();
  }, 900);
}

function updateScoreDisplay() {
  const n = state.session.trials.length;
  const correct = state.session.trials.filter(t => t.correct).length;
  document.getElementById('score-num').textContent = correct;
  document.getElementById('score-total').textContent = n;
  document.getElementById('score-pct').textContent = n ? `${Math.round((correct / n) * 100)}%` : '—';
}

async function finishSession() {
  document.getElementById('test-active').classList.add('hidden');
  document.getElementById('test-results').classList.remove('hidden');

  const res = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trials: state.session.trials, notes: state.session.notes }),
  });
  const data = await res.json();

  document.getElementById('results-summary').textContent = data.summary;
  renderBreakdown(state.session.trials);
  renderConfusions(state.session.trials);
}

function renderBreakdown(trials) {
  const by = {};
  trials.forEach(t => {
    if (!by[t.truth]) by[t.truth] = { n: 0, c: 0 };
    by[t.truth].n++;
    if (t.correct) by[t.truth].c++;
  });
  const table = document.getElementById('results-breakdown');
  table.innerHTML = '<tr><th>Symbol</th><th>Correct</th><th>Total</th><th>Rate</th></tr>';
  state.vocab.forEach(sym => {
    const stat = by[sym.name];
    if (!stat) return;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${sym.name}</td><td>${stat.c}</td><td>${stat.n}</td><td>${Math.round((stat.c / stat.n) * 100)}%</td>`;
    table.appendChild(tr);
  });
}

function renderConfusions(trials) {
  const conf = {};
  trials.forEach(t => {
    if (!t.correct && t.guess) {
      if (!conf[t.truth]) conf[t.truth] = {};
      conf[t.truth][t.guess] = (conf[t.truth][t.guess] || 0) + 1;
    }
  });
  const el = document.getElementById('results-confusions');
  const keys = Object.keys(conf).sort();
  if (!keys.length) {
    el.textContent = 'No confusions — clean session.';
    return;
  }
  el.innerHTML = keys.map(truth => {
    const guesses = Object.entries(conf[truth])
      .sort((a, b) => b[1] - a[1])
      .map(([g, n]) => `${g} (${n}x)`)
      .join(', ');
    return `<div>${truth} → ${guesses}</div>`;
  }).join('');
}

// --- History mode ---
async function loadHistory() {
  const res = await fetch('/api/sessions');
  const data = await res.json();
  const sessions = data.sessions || [];
  const table = document.getElementById('history-table');
  const empty = document.getElementById('history-empty');

  if (!sessions.length) {
    table.innerHTML = '';
    empty.classList.remove('hidden');
    drawChart([]);
    return;
  }
  empty.classList.add('hidden');

  table.innerHTML = '<tr><th>When</th><th>Trials</th><th>Correct</th><th>Accuracy</th><th>p-value</th><th>Bits</th><th>Notes</th></tr>';
  sessions.slice().reverse().forEach(s => {
    const st = s.stats;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${formatTimestamp(s.timestamp)}</td>
      <td>${st.n_trials}</td>
      <td>${st.n_correct}</td>
      <td>${(st.accuracy * 100).toFixed(0)}%</td>
      <td>${formatP(st.p_value)}</td>
      <td>${st.above_chance_bits.toFixed(2)}</td>
      <td>${s.notes || ''}</td>
    `;
    table.appendChild(tr);
  });

  drawChart(sessions.map(s => ({
    accuracy: s.stats.accuracy,
    label: formatTimestamp(s.timestamp),
  })));
}

function formatTimestamp(ts) {
  // expects YYYYMMDD_HHMMSS
  if (!ts || ts.length < 13) return ts || '';
  const date = `${ts.slice(0,4)}-${ts.slice(4,6)}-${ts.slice(6,8)}`;
  const time = `${ts.slice(9,11)}:${ts.slice(11,13)}`;
  return `${date} ${time}`;
}

function formatP(p) {
  if (p < 0.001) return '<0.001';
  if (p < 0.01) return p.toFixed(3);
  return p.toFixed(2);
}

function drawChart(points) {
  const canvas = document.getElementById('history-chart');
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Background grid
  ctx.strokeStyle = '#2a313c';
  ctx.lineWidth = 1;
  const padding = { top: 20, right: 20, bottom: 40, left: 50 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;

  // Y axis (accuracy 0-100%)
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (plotH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(padding.left + plotW, y);
    ctx.stroke();
    ctx.fillStyle = '#8b949e';
    ctx.font = '11px ui-monospace, monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`${100 - i * 25}%`, padding.left - 8, y + 4);
  }

  // Chance line (12.5% for 8 symbols)
  const chanceY = padding.top + plotH * (1 - state.chanceRate);
  ctx.strokeStyle = '#d29922';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(padding.left, chanceY);
  ctx.lineTo(padding.left + plotW, chanceY);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#d29922';
  ctx.textAlign = 'left';
  ctx.fillText(`chance (${(state.chanceRate * 100).toFixed(1)}%)`, padding.left + 6, chanceY - 6);

  if (!points.length) {
    ctx.fillStyle = '#8b949e';
    ctx.textAlign = 'center';
    ctx.fillText('No sessions yet', w / 2, h / 2);
    return;
  }

  // Line + points
  const stepX = points.length === 1 ? 0 : plotW / (points.length - 1);
  ctx.strokeStyle = '#58a6ff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = padding.left + i * stepX;
    const y = padding.top + plotH * (1 - p.accuracy);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Dots
  points.forEach((p, i) => {
    const x = padding.left + (points.length === 1 ? plotW / 2 : i * stepX);
    const y = padding.top + plotH * (1 - p.accuracy);
    ctx.fillStyle = '#58a6ff';
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });

  // X-axis label
  ctx.fillStyle = '#8b949e';
  ctx.textAlign = 'center';
  ctx.font = '11px ui-monospace, monospace';
  ctx.fillText('sessions over time →', w / 2, h - 10);
}

// --- Layered mode ---
function renderMetaGrid() {
  const grid = document.getElementById('meta-grid');
  grid.innerHTML = '';
  state.metaVocab.forEach(sym => {
    const btn = document.createElement('button');
    btn.className = 'symbol-btn';
    btn.textContent = sym.name;
    btn.addEventListener('click', () => selectMeta(sym, btn));
    grid.appendChild(btn);
  });
}

function selectMeta(sym, btn) {
  state.selectedMeta = sym;
  document.querySelectorAll('#meta-grid .symbol-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  document.getElementById('meta-name').textContent = sym.name;
  document.getElementById('meta-meaning').textContent = sym.meaning;
  document.getElementById('meta-rationale').textContent = sym.rationale;
  document.getElementById('meta-play').disabled = false;
  playMeta(sym.name);
}

function playMeta(name) {
  player.src = `/audio/meta/${name}.wav?t=${Date.now()}`;
  player.play().catch(err => console.error('meta play failed:', err));
}

function playCombined(content, meta) {
  player.src = `/audio/combined/${content}/${meta}.wav?t=${Date.now()}`;
  player.play().catch(err => console.error('combined play failed:', err));
}

document.getElementById('meta-play').addEventListener('click', () => {
  if (state.selectedMeta) playMeta(state.selectedMeta.name);
});

function renderLayeredGrids() {
  // Content grid
  const cGrid = document.getElementById('layered-content-grid');
  cGrid.innerHTML = '';
  state.vocab.forEach(sym => {
    const btn = document.createElement('button');
    btn.className = 'symbol-btn';
    btn.textContent = sym.name;
    btn.dataset.name = sym.name;
    btn.disabled = true;
    btn.addEventListener('click', () => selectLayeredGuess('content', sym.name, btn));
    cGrid.appendChild(btn);
  });

  // Metadata grid
  const mGrid = document.getElementById('layered-meta-grid');
  mGrid.innerHTML = '';
  state.metaVocab.forEach(sym => {
    const btn = document.createElement('button');
    btn.className = 'symbol-btn';
    btn.textContent = sym.name;
    btn.dataset.name = sym.name;
    btn.disabled = true;
    btn.addEventListener('click', () => selectLayeredGuess('meta', sym.name, btn));
    mGrid.appendChild(btn);
  });
}

function selectLayeredGuess(layer, name, btn) {
  if (!state.layered?.current || state.layered.current.answered) return;
  const gridId = layer === 'content' ? 'layered-content-grid' : 'layered-meta-grid';
  document.querySelectorAll(`#${gridId} .symbol-btn`).forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  if (layer === 'content') state.layered.current.contentGuess = name;
  else state.layered.current.metaGuess = name;

  // Enable submit when both layers have a guess
  document.getElementById('layered-submit').disabled =
    !(state.layered.current.contentGuess && state.layered.current.metaGuess);
}

document.getElementById('layered-start').addEventListener('click', startLayeredSession);
document.getElementById('layered-restart').addEventListener('click', () => {
  document.getElementById('layered-results').classList.add('hidden');
  document.getElementById('layered-intro').classList.remove('hidden');
});
document.getElementById('layered-history').addEventListener('click', () => switchMode('history'));
document.getElementById('layered-hear').addEventListener('click', () => playLayeredCurrent());
document.getElementById('layered-replay').addEventListener('click', () => playLayeredCurrent(true));
document.getElementById('layered-submit').addEventListener('click', commitLayeredTrial);

function startLayeredSession() {
  const total = parseInt(document.getElementById('layered-trial-count').value, 10);
  const notes = document.getElementById('layered-notes').value.trim();

  state.layered = {
    trials: [],
    idx: 0,
    total,
    notes,
    order: buildLayeredOrder(total),
    current: null,
  };

  document.getElementById('layered-intro').classList.add('hidden');
  document.getElementById('layered-results').classList.add('hidden');
  document.getElementById('layered-active').classList.remove('hidden');
  document.getElementById('layered-total').textContent = total;
  updateLayeredScores();
  nextLayeredTrial();
}

function buildLayeredOrder(n) {
  const contentNames = state.vocab.map(s => s.name);
  const metaNames = state.metaVocab.map(s => s.name);
  const order = [];
  for (let i = 0; i < n; i++) {
    const cPool = contentNames.filter(name =>
      order.length === 0 || name !== order[order.length - 1].content);
    const mPool = metaNames.filter(name =>
      order.length === 0 || name !== order[order.length - 1].meta);
    order.push({
      content: cPool[Math.floor(Math.random() * cPool.length)],
      meta: mPool[Math.floor(Math.random() * mPool.length)],
    });
  }
  return order;
}

function nextLayeredTrial() {
  if (state.layered.idx >= state.layered.total) {
    finishLayeredSession();
    return;
  }
  const { content, meta } = state.layered.order[state.layered.idx];
  state.layered.current = {
    truth: content,
    truth_meta: meta,
    contentGuess: null,
    metaGuess: null,
    answered: false,
    playStart: null,
  };

  document.getElementById('layered-num').textContent = state.layered.idx + 1;
  document.getElementById('layered-feedback').textContent = '';
  document.getElementById('layered-feedback').className = 'feedback';
  document.getElementById('layered-submit').disabled = true;

  // Reset both grids
  document.querySelectorAll('#layered-content-grid .symbol-btn, #layered-meta-grid .symbol-btn').forEach(b => {
    b.classList.remove('correct', 'incorrect', 'selected');
    b.disabled = true;
  });

  document.getElementById('layered-hear').disabled = false;
  document.getElementById('layered-hear').textContent = '▶ Hear (stereo)';
  document.getElementById('layered-replay').disabled = true;
}

function playLayeredCurrent(isReplay = false) {
  if (!state.layered?.current) return;
  const { truth, truth_meta } = state.layered.current;
  if (!isReplay) {
    state.layered.current.playStart = Date.now();
    document.querySelectorAll('#layered-content-grid .symbol-btn, #layered-meta-grid .symbol-btn').forEach(b => {
      b.disabled = false;
    });
    document.getElementById('layered-hear').disabled = true;
    document.getElementById('layered-hear').textContent = '— played —';
    document.getElementById('layered-replay').disabled = false;
  }
  playCombined(truth, truth_meta);
}

function commitLayeredTrial() {
  const cur = state.layered.current;
  if (!cur || cur.answered) return;
  if (!cur.contentGuess || !cur.metaGuess) return;

  const contentCorrect = cur.contentGuess === cur.truth;
  const metaCorrect = cur.metaGuess === cur.truth_meta;
  cur.answered = true;

  state.layered.trials.push({
    index: state.layered.idx + 1,
    truth: cur.truth,
    guess: cur.contentGuess,
    correct: contentCorrect,
    truth_meta: cur.truth_meta,
    guess_meta: cur.metaGuess,
    meta_correct: metaCorrect,
    response_ms: cur.playStart ? Date.now() - cur.playStart : 0,
  });

  // Paint feedback on both grids
  document.querySelectorAll('#layered-content-grid .symbol-btn').forEach(b => {
    b.disabled = true;
    if (b.dataset.name === cur.truth) b.classList.add('correct');
    if (b.dataset.name === cur.contentGuess && !contentCorrect) b.classList.add('incorrect');
  });
  document.querySelectorAll('#layered-meta-grid .symbol-btn').forEach(b => {
    b.disabled = true;
    if (b.dataset.name === cur.truth_meta) b.classList.add('correct');
    if (b.dataset.name === cur.metaGuess && !metaCorrect) b.classList.add('incorrect');
  });

  const fb = document.getElementById('layered-feedback');
  if (contentCorrect && metaCorrect) {
    fb.textContent = `OK both — ${cur.truth} / ${cur.truth_meta}`;
    fb.className = 'feedback ok';
  } else if (contentCorrect) {
    fb.textContent = `content OK (${cur.truth}) — metadata was ${cur.truth_meta}, you said ${cur.metaGuess}`;
    fb.className = 'feedback bad';
  } else if (metaCorrect) {
    fb.textContent = `metadata OK (${cur.truth_meta}) — content was ${cur.truth}, you said ${cur.contentGuess}`;
    fb.className = 'feedback bad';
  } else {
    fb.textContent = `X both — was ${cur.truth} / ${cur.truth_meta}`;
    fb.className = 'feedback bad';
  }

  document.getElementById('layered-submit').disabled = true;
  updateLayeredScores();
  setTimeout(() => {
    state.layered.idx++;
    nextLayeredTrial();
  }, 1400);
}

function updateLayeredScores() {
  const trials = state.layered.trials;
  const n = trials.length;
  const c = trials.filter(t => t.correct).length;
  const m = trials.filter(t => t.meta_correct).length;
  const both = trials.filter(t => t.correct && t.meta_correct).length;
  document.getElementById('layered-content-score').textContent = `${c}/${n}`;
  document.getElementById('layered-meta-score').textContent = `${m}/${n}`;
  document.getElementById('layered-both-score').textContent = `${both}/${n}`;
}

async function finishLayeredSession() {
  document.getElementById('layered-active').classList.add('hidden');
  document.getElementById('layered-results').classList.remove('hidden');

  const res = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: 'layered',
      trials: state.layered.trials,
      notes: state.layered.notes,
    }),
  });
  const data = await res.json();
  document.getElementById('layered-summary').textContent = data.summary;
}

// ---------------------------------------------------------------------------
// RECEIVE MODE (v2) — math-native receptive listening with TTS + voice capture
// Implements design-review decisions RD1-RD4.
// ---------------------------------------------------------------------------

const receive = {
  subject: 'self',
  tier: 'chord',
  n_trials: 6,
  trials: [],        // accumulated
  pool: [],          // bank entries for this tier
  current: null,     // current trial entry
  trialIdx: 0,
  recognition: null,
  awaitingCommand: null,  // 'begin' | 'replay' | 'done' | 'transcript'
  transcriptBuffer: '',
  ttsSupported: 'speechSynthesis' in window,
  recogSupported: false,
};

(function initReceiveCapability() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  receive.recogSupported = !!SR;
  const banner = document.getElementById('receive-capability');
  const issues = [];
  if (!receive.ttsSupported) issues.push('Browser TTS unavailable — prompts will be visual only.');
  if (!receive.recogSupported) issues.push('Web Speech API not available — typed input fallback will be used.');
  if (issues.length) {
    banner.textContent = issues.join(' ');
    banner.classList.add('warning');
  } else {
    banner.textContent = 'TTS + voice capture available. Headphones on, eyes closed when ready.';
  }
})();

function tts(text, opts = {}) {
  return new Promise((resolve) => {
    if (!receive.ttsSupported) { setTimeout(resolve, 200); return; }
    const u = new SpeechSynthesisUtterance(text);
    u.rate = opts.rate || 0.9;
    u.pitch = opts.pitch || 1.0;
    u.volume = opts.volume ?? 1.0;
    u.onend = resolve;
    u.onerror = resolve;
    window.speechSynthesis.speak(u);
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function makeRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR();
  r.lang = 'en-US';
  r.continuous = false;
  r.interimResults = true;
  r.maxAlternatives = 1;
  return r;
}

function listenFor(expected, timeoutMs = 8000) {
  // Listen for one of `expected` (array of words). Returns the matched word
  // or null on timeout. Strict 3-word vocab gating per RD3.
  return new Promise((resolve) => {
    if (!receive.recogSupported) { resolve(null); return; }
    const r = makeRecognition();
    let resolved = false;
    const finish = (val) => { if (!resolved) { resolved = true; try { r.stop(); } catch(_){}; resolve(val); } };
    r.onresult = (ev) => {
      let text = '';
      for (let i = 0; i < ev.results.length; i++) {
        text += ev.results[i][0].transcript;
      }
      text = text.toLowerCase();
      for (const w of expected) {
        if (text.includes(w)) { finish(w); return; }
      }
    };
    r.onerror = () => finish(null);
    r.onend = () => { if (!resolved) finish(null); };
    setTimeout(() => finish(null), timeoutMs);
    try { r.start(); document.getElementById('receive-listening').classList.remove('hidden'); }
    catch(_) { finish(null); }
  });
}

function captureFreeTranscript(maxMs = 12000) {
  // Open-ended capture for the user's interpretation. Returns the final
  // transcript string (empty on no speech / timeout).
  return new Promise((resolve) => {
    if (!receive.recogSupported) { resolve(''); return; }
    const r = makeRecognition();
    r.continuous = true;
    let buf = '';
    let resolved = false;
    const finish = () => { if (!resolved) { resolved = true; try { r.stop(); } catch(_){}; resolve(buf.trim()); } };
    r.onresult = (ev) => {
      buf = '';
      for (let i = 0; i < ev.results.length; i++) {
        buf += ev.results[i][0].transcript + ' ';
      }
      document.getElementById('receive-transcript').textContent = buf.trim();
      // If user says "done", finalize
      if (/\bdone\b/.test(buf.toLowerCase())) finish();
    };
    r.onerror = () => finish();
    r.onend = () => { if (!resolved) finish(); };
    setTimeout(finish, maxMs);
    try { r.start(); document.getElementById('receive-listening').classList.remove('hidden'); }
    catch(_) { finish(); }
  });
}

async function calibrate() {
  // RD2 — pre-session calibration ritual (~45 seconds)
  document.getElementById('receive-intro').classList.add('hidden');
  document.getElementById('receive-calibration').classList.remove('hidden');
  const step = document.getElementById('calibration-step');
  const fill = document.querySelector('#calibration-progress .progress-fill');
  const progress = (pct) => { fill.style.width = pct + '%'; };

  step.textContent = 'Welcome. Put on your headphones. Close your eyes.';
  progress(5);
  await tts('Welcome. Put on your headphones. Close your eyes.');
  await sleep(800);

  // L-channel test
  step.textContent = 'Left ear test…';
  progress(20);
  await playChannelTone('left', 0.5);
  await sleep(400);

  // R-channel test
  step.textContent = 'Right ear test…';
  progress(35);
  await playChannelTone('right', 0.5);
  await sleep(400);

  // Center test
  step.textContent = 'Center test…';
  progress(50);
  await playChannelTone('center', 0.5);
  await sleep(400);

  // Mic check
  if (receive.recogSupported) {
    step.textContent = 'Say anything when ready.';
    progress(65);
    await tts('Say anything when ready.');
    const got = await listenFor(['ok','ready','here','hello','yes','begin','i','self'], 6000);
    if (!got) step.textContent = '(no voice heard — falling back to typed input later if needed)';
    document.getElementById('receive-listening').classList.add('hidden');
  } else {
    step.textContent = 'Voice unavailable — typed input only.';
    progress(65);
  }
  await sleep(400);

  // Settling pause with breathing
  step.textContent = 'Close your eyes. Breathe out slowly, three times.';
  progress(80);
  await tts('Close your eyes. Breathe out slowly, three times.');
  await sleep(3500);

  // Ready chime
  step.textContent = 'Ready.';
  progress(100);
  await tts('Ready.');
  await sleep(500);

  // Move to trial loop
  document.getElementById('receive-calibration').classList.add('hidden');
  document.getElementById('receive-trial').classList.remove('hidden');
  startTrial();
}

function playChannelTone(side, durationS) {
  // Synthesize a calibration tone on the specified channel.
  return new Promise((resolve) => {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const merger = ctx.createChannelMerger(2);
    osc.frequency.value = 440;
    gain.gain.value = 0.25;
    osc.connect(gain);
    if (side === 'left') gain.connect(merger, 0, 0);
    else if (side === 'right') gain.connect(merger, 0, 1);
    else { gain.connect(merger, 0, 0); gain.connect(merger, 0, 1); }
    merger.connect(ctx.destination);
    osc.start();
    setTimeout(() => { osc.stop(); ctx.close(); resolve(); }, durationS * 1000);
  });
}

async function loadReceivePool() {
  const res = await fetch(`/api/v2/messages?tier=${receive.tier}`);
  const data = await res.json();
  // shuffle and take n
  const pool = [...data.messages];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  receive.pool = pool.slice(0, receive.n_trials);
}

async function startTrial() {
  if (receive.trialIdx >= receive.pool.length) return finishSession();
  receive.current = receive.pool[receive.trialIdx];
  document.getElementById('receive-trial-num').textContent = receive.trialIdx + 1;
  document.getElementById('receive-trial-total').textContent = receive.pool.length;
  document.getElementById('receive-state').textContent = 'Say "begin" when ready.';
  document.getElementById('receive-transcript').textContent = '';
  document.getElementById('receive-feedback').textContent = '';
  document.getElementById('receive-typed-input').classList.add('hidden');
  document.getElementById('receive-replay-btn').disabled = true;
  document.getElementById('receive-done-btn').disabled = true;

  if (receive.recogSupported) {
    await tts('Say begin when ready.');
    const got = await listenFor(['begin','start'], 15000);
    document.getElementById('receive-listening').classList.add('hidden');
    if (!got) {
      // RD4 — failure fallback: offer typed-button start
      document.getElementById('receive-state').textContent = 'No "begin" heard. Press Replay to start, or use typed input.';
      document.getElementById('receive-replay-btn').disabled = false;
      return;
    }
  }
  await playMessage();
  await captureAndScore();
}

async function playMessage() {
  document.getElementById('receive-state').textContent = 'Listening to message…';
  return new Promise((resolve) => {
    const audio = new Audio(`/audio/v2/${receive.current.id}.wav`);
    audio.onended = resolve;
    audio.onerror = resolve;
    audio.play();
  });
}

async function captureAndScore() {
  document.getElementById('receive-state').textContent = 'Speak your interpretation. Say "done" when finished, or "replay" to hear again.';
  document.getElementById('receive-replay-btn').disabled = false;
  document.getElementById('receive-done-btn').disabled = false;

  if (receive.recogSupported) {
    const transcript = await captureFreeTranscript(15000);
    document.getElementById('receive-listening').classList.add('hidden');
    if (transcript) {
      await scoreTrial(transcript);
    } else {
      document.getElementById('receive-state').textContent = 'No transcript captured. Try Replay or use typed input.';
    }
  } else {
    // typed-input fallback
    document.getElementById('receive-typed-input').classList.remove('hidden');
    document.getElementById('receive-state').textContent = 'Type what you heard. Press Submit.';
  }
}

async function scoreTrial(transcript) {
  const res = await fetch('/api/v2/score', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({transcript, message_id: receive.current.id}),
  });
  const result = await res.json();
  const trial = {
    message_id: receive.current.id,
    tier: receive.current.tier,
    english_gloss: receive.current.english_gloss,
    transcript: transcript,
    score: result.score,
    label: result.label,
    breakdown: result.breakdown,
  };
  receive.trials.push(trial);
  updateScoreDisplay();
  document.getElementById('receive-feedback').innerHTML = renderTrialFeedback(trial);
  await tts(result.label === 'correct' ? 'Correct.' : (result.label === 'partial' ? 'Partial.' : 'Different.'));
  await sleep(1500);
  receive.trialIdx++;
  startTrial();
}

function renderTrialFeedback(trial) {
  const recovered = (trial.breakdown.recovered_primitives || []).join(', ');
  const missed = (trial.breakdown.missed_primitives || []).join(', ');
  return `
    <div class="trial-feedback-card">
      <div><strong>${trial.label.toUpperCase()}</strong> · score ${trial.score.toFixed(2)}</div>
      <div class="gloss">truth: "${trial.english_gloss}"</div>
      <div class="gloss">you said: "${trial.transcript}"</div>
      ${recovered ? `<div class="primitives">recovered: ${recovered}</div>` : ''}
      ${missed ? `<div class="primitives missed">missed: ${missed}</div>` : ''}
    </div>
  `;
}

function updateScoreDisplay() {
  const counts = {correct: 0, partial: 0, incorrect: 0};
  for (const t of receive.trials) counts[t.label] = (counts[t.label] || 0) + 1;
  document.getElementById('receive-score-correct').textContent = counts.correct;
  document.getElementById('receive-score-partial').textContent = counts.partial;
  document.getElementById('receive-score-incorrect').textContent = counts.incorrect;
}

document.getElementById('receive-start').addEventListener('click', async () => {
  receive.subject = document.getElementById('receive-subject').value.trim() || 'anonymous';
  receive.tier = document.getElementById('receive-tier').value;
  receive.n_trials = parseInt(document.getElementById('receive-trials').value, 10);
  receive.trials = [];
  receive.trialIdx = 0;
  await loadReceivePool();
  await calibrate();
});

document.getElementById('receive-replay-btn').addEventListener('click', async () => {
  await playMessage();
  await captureAndScore();
});

document.getElementById('receive-done-btn').addEventListener('click', async () => {
  const typed = document.getElementById('receive-transcript').textContent.trim();
  if (typed) await scoreTrial(typed);
});

document.getElementById('receive-typed-btn').addEventListener('click', () => {
  document.getElementById('receive-typed-input').classList.remove('hidden');
});

document.getElementById('receive-typed-submit').addEventListener('click', async () => {
  const text = document.getElementById('receive-typed-text').value.trim();
  if (!text) return;
  document.getElementById('receive-typed-text').value = '';
  await scoreTrial(text);
});

async function finishSession() {
  document.getElementById('receive-trial').classList.add('hidden');
  document.getElementById('receive-results').classList.remove('hidden');

  const res = await fetch('/api/v2/sessions', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      subject_id: receive.subject,
      tier: receive.tier,
      trials: receive.trials,
    }),
  });
  const data = await res.json();
  const s = data.stats;
  document.getElementById('receive-summary').innerHTML = `
    <div>Subject: <strong>${receive.subject}</strong> · Tier: <strong>${receive.tier}</strong></div>
    <div>Trials: ${s.n_trials} · Correct: ${s.n_correct} · Partial: ${s.n_partial} · Incorrect: ${s.n_incorrect}</div>
    <div>Mean score: ${s.mean_score.toFixed(3)} · Partial-or-better rate: ${(s.partial_or_better_rate * 100).toFixed(1)}%</div>
    <div>Saved to: ${data.saved}</div>
  `;

  const table = document.getElementById('receive-trial-table');
  let html = '<tr><th>#</th><th>truth</th><th>transcript</th><th>label</th><th>score</th></tr>';
  receive.trials.forEach((t, i) => {
    html += `<tr><td>${i+1}</td><td>${t.english_gloss}</td><td>${t.transcript}</td><td class="label-${t.label}">${t.label}</td><td>${t.score.toFixed(2)}</td></tr>`;
  });
  table.innerHTML = html;
}

document.getElementById('receive-restart').addEventListener('click', () => {
  document.getElementById('receive-results').classList.add('hidden');
  document.getElementById('receive-intro').classList.remove('hidden');
  receive.trials = [];
  receive.trialIdx = 0;
});

init();
