/* EDRA / Pitch Floor — frontend controller (Phase 2)
 *
 * No build step, no framework. Polls GET /state every 1000ms (TASK.md §10.6),
 * streams active revisions via EventSource, drives the VN textbox + interest
 * gauge + rulebook + reflection console from the snapshot.
 *
 * Update philosophy: re-render only what changed. The textbox typewriter
 * and the gauge transitions are stateful, so we track their last-rendered
 * value and skip work when the snapshot hasn't moved.
 */

'use strict';

const POLL_MS = 1000;
const TYPEWRITER_CPS = 30;
const SPAWNABLE_ROTATION = ['arch_journalist_curious', 'arch_vc_investor'];

const state = {
  expertOn: true,
  lastUtterance: null,
  lastInterest: null,
  typewriterTimer: null,
  activeRevisionId: null,
  eventSource: null,
  currentSessionId: null,
  spawnIdx: 0,
  liveMode: false,
  syntheticArchetypes: [],
  pendingLiveUrl: null,
};

// ── Helpers ──────────────────────────────────────────────────────────

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function setText(sel, text) {
  const el = $(sel);
  if (el && el.textContent !== String(text)) {
    el.textContent = String(text);
  }
}

function setHidden(sel, hidden) {
  const el = $(sel);
  if (!el) return;
  el.style.display = hidden ? 'none' : '';
}

async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json();
}

async function postJSON(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body == null ? '{}' : JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => '');
    throw new Error(`POST ${path} → ${r.status} ${detail}`);
  }
  return r.json();
}

function formatGaugeValue(n) {
  if (n > 0) return `+${n}`;
  return String(n);
}

function getEmotion(interest) {
  if (interest >= 4) return 'confident';
  if (interest >= 1) return 'pleased';
  if (interest === 0) return 'neutral';
  if (interest >= -2) return 'thoughtful';
  if (interest >= -4) return 'concerned';
  return 'disappointed';
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

// ── Polling + state apply ────────────────────────────────────────────

async function poll() {
  let snap;
  try {
    snap = await getJSON('/state');
  } catch (e) {
    console.warn('poll failed', e);
    return;
  }
  applyState(snap);
}

function applyState(s) {
  applyTopStats(s);
  applyTextbox(s);
  applyGauge(s);
  applyRulebook(s.rules || []);
  applyReflection(s.active_revision);
  applyVisitor(s.current_session, s.recent_episodes);
  applyChoices(s.current_session);
}

function applyTopStats(s) {
  const day = (s.clock && s.clock.day) || 1;
  setText('#stat-day', `Day ${pad2(day)}`);
  setText('#stat-episodes', (s.recent_episodes || []).length);
  const activeRules = (s.rules || []).filter(r => r.status === 'active').length;
  setText('#stat-rules', activeRules);
  setText('#stat-revising', s.active_revision ? 1 : 0);
  setText('#stat-specialists', (s.agents || []).length);
}

// pick the most-recent DialogueStep we should display
function pickStep(s) {
  if (s.current_session && s.current_session.dialogue && s.current_session.dialogue.length) {
    return s.current_session.dialogue[s.current_session.dialogue.length - 1];
  }
  if (s.recent_episodes && s.recent_episodes.length) {
    const latest = s.recent_episodes[0];
    if (latest.dialogue && latest.dialogue.length) {
      return latest.dialogue[latest.dialogue.length - 1];
    }
  }
  return null;
}

function applyTextbox(s) {
  const step = pickStep(s);
  const utter = $('#utterance');

  if (!step) {
    setText('#thought-text', '— waiting for the first visitor —');
    setText('#utterance-text', '');
    setHidden('#thought-tag', true);
    utter.classList.add('-waiting');
    return;
  }

  utter.classList.remove('-waiting');
  setText('#thought-text', step.agent_thought || '');
  if (step.rule_applied) {
    setText('#thought-tag', step.rule_applied);
    setHidden('#thought-tag', false);
  } else {
    setHidden('#thought-tag', true);
  }

  if (step.agent_reply !== state.lastUtterance) {
    state.lastUtterance = step.agent_reply;
    typewrite('#utterance-text', step.agent_reply || '');
  }
}

function typewrite(sel, text) {
  const el = $(sel);
  const marker = $('#continue-marker');
  if (!el) return;
  if (state.typewriterTimer) {
    clearInterval(state.typewriterTimer);
    state.typewriterTimer = null;
  }
  if (marker) marker.classList.add('-typing');
  el.textContent = '';
  let i = 0;
  const step = 1000 / TYPEWRITER_CPS;
  state.typewriterTimer = setInterval(() => {
    if (i >= text.length) {
      clearInterval(state.typewriterTimer);
      state.typewriterTimer = null;
      if (marker) marker.classList.remove('-typing');
      return;
    }
    el.textContent += text.charAt(i++);
  }, step);
}

function applyGauge(s) {
  let interest = s.interest_gauge;
  if (interest == null) {
    // Fall back to the last persisted episode's final interest, so the gauge
    // reflects the most recent outcome between sessions instead of going to 0.
    if (s.recent_episodes && s.recent_episodes.length) {
      interest = s.recent_episodes[0].final_interest;
    } else {
      interest = 0;
    }
  }
  if (interest === state.lastInterest) return;
  state.lastInterest = interest;

  setText('#gauge-value', formatGaugeValue(interest));
  $('#gauge-value').style.color = interest >= 4 || interest <= -4
    ? 'var(--defy-red)'
    : (interest > 0 ? 'var(--warm-white)' : 'var(--cream-dim)');

  const cells = $$('.gauge-cell');
  cells.forEach((cell) => {
    const val = parseInt(cell.dataset.cell, 10);
    cell.classList.remove('-on', '-warm', '-hot');
    if (val === 0) return;

    const lit = (interest > 0 && val > 0 && val <= interest)
             || (interest < 0 && val < 0 && val >= interest);
    if (!lit) return;

    cell.classList.add('-on');
    if (Math.abs(val) >= 4) cell.classList.add('-warm');
    if (Math.abs(val) === 5) cell.classList.add('-hot');
  });

  setText('#agent-emotion', `current — ${getEmotion(interest)}`);
}

// ── Rulebook ─────────────────────────────────────────────────────────

function applyRulebook(rules) {
  const meta = $('#rulebook-meta');
  const list = $('#rules-list');
  if (!list) return;

  const active = rules.filter(r => r.status === 'active').length;
  const deprecated = rules.filter(r => r.status === 'deprecated').length;
  const revising = rules.filter(r => r.status === 'under_revision').length;

  if (rules.length === 0) {
    if (meta) meta.textContent = '— no rules induced yet —';
    list.innerHTML = '<div class="rules-empty">— no rules induced yet —</div>';
    return;
  }

  if (meta) {
    meta.textContent = `${active} active · ${deprecated} deprecated · ${revising} revising`;
  }

  // Sort: under_revision first (most urgent), then active by induced_at desc, then deprecated
  const ordered = [...rules].sort((a, b) => {
    const order = { under_revision: 0, active: 1, deprecated: 2 };
    const oa = order[a.status] ?? 3;
    const ob = order[b.status] ?? 3;
    if (oa !== ob) return oa - ob;
    return new Date(b.induced_at) - new Date(a.induced_at);
  });

  list.innerHTML = ordered.map(renderRule).join('');
}

function renderRule(rule) {
  const num = (rule.id || '').replace(/^R\./, '');
  const slots = {};
  for (const s of rule.slots || []) {
    slots[s.name] = s;
  }
  const cls = ['rule'];
  const ageMs = Date.now() - new Date(rule.induced_at).getTime();
  if (rule.status === 'active' && ageMs < 60_000) cls.push('-fresh');
  if (rule.status === 'under_revision') cls.push('-revising');
  if (rule.status === 'deprecated') cls.push('-deprecated');

  if (rule.status === 'deprecated') {
    return `
      <div class="${cls.join(' ')}">
        <div class="rule-num">${num}</div>
        <div class="rule-body">
          <span class="if">If</span><span class="clu">${escapeHTML(rule.cluster_id)} <em>(replaced by ${escapeHTML(rule.deprecated_by || '—')})</em></span>
        </div>
        <div class="rule-cs"><div class="cs-num" style="opacity:0.4;">—</div></div>
      </div>
    `;
  }

  const dynBits = (rule.slots || []).filter(s => s.kind === 'dynamic');
  const dynLine = dynBits.length
    ? `<span class="dyn">+ ${escapeHTML(dynBits.map(s => s.name).join(' & '))} via LLM</span>`
    : '';

  const csBars = renderCSHistory(rule.cs_history || []);
  const csNum = computeCSDisplay(rule.cs_history || []);

  const slotChip = (name) => {
    const s = slots[name];
    if (!s) return '<span class="slot">—</span>';
    if (s.kind === 'dynamic') return `<span class="slot">dynamic</span>`;
    return `<span class="slot">${escapeHTML(s.value || '—')}</span>`;
  };

  return `
    <div class="${cls.join(' ')}">
      <div class="rule-num">${num}</div>
      <div class="rule-body">
        <span class="if">If</span><span class="clu">${escapeHTML(rule.cluster_id)}</span><br>
        <span class="then">Then</span>framing ${slotChip('framing')} · tone ${slotChip('tone')} · opener ${slotChip('opener_type')} · words ${slotChip('word_target')} · ask ${slotChip('ask_size')}
        ${dynLine}
      </div>
      <div class="rule-cs">
        <div class="cs-hist">${csBars}</div>
        <div class="cs-num">${csNum.num}<small>${csNum.unit}</small></div>
      </div>
    </div>
  `;
}

function renderCSHistory(history) {
  // Pad/truncate to 10 bars; -active when value >= 0.6 (above induction threshold)
  const last = history.slice(-10);
  while (last.length < 10) last.unshift([null, null]);
  return last.map(([_, v]) => {
    const cls = (v != null && v >= 0.6) ? 'cs-bar -active' : 'cs-bar';
    return `<div class="${cls}"></div>`;
  }).join('');
}

function computeCSDisplay(history) {
  if (!history.length) return { num: '—', unit: '' };
  const last = history[history.length - 1][1];
  if (last == null) return { num: '—', unit: '' };
  return { num: Math.round(last * 100), unit: '%' };
}

// ── Reflection console ───────────────────────────────────────────────

function applyReflection(rev) {
  const block = $('#reflection-block');
  const proposal = $('#refl-proposal');
  if (!rev) {
    if (block) block.classList.add('-hidden');
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
      state.activeRevisionId = null;
    }
    return;
  }

  if (block) block.classList.remove('-hidden');
  setText('#refl-title-text', `${rev.rule_id} · Revising`);

  if (rev.id !== state.activeRevisionId) {
    state.activeRevisionId = rev.id;
    setText('#refl-text', '');
    if (proposal) proposal.style.display = 'none';
    if (state.eventSource) state.eventSource.close();
    openReflectionStream(rev.id);
  } else if (rev.llm_reasoning && !state.eventSource) {
    // Persisted reasoning from a previous session — surface it as static text.
    setText('#refl-text', rev.llm_reasoning);
  }
}

function openReflectionStream(revisionId) {
  const text = $('#refl-text');
  const proposal = $('#refl-proposal');
  if (text) text.classList.add('-streaming');

  const es = new EventSource(`/reflections/stream/${revisionId}`);
  state.eventSource = es;

  es.addEventListener('reasoning', (e) => {
    if (text) text.textContent += e.data;
  });

  es.addEventListener('revision', (e) => {
    try {
      const proposed = JSON.parse(e.data);
      renderProposed(proposed);
      if (proposal) proposal.style.display = '';
    } catch (err) {
      console.warn('failed to parse revision payload', err);
    }
  });

  es.addEventListener('done', () => {
    if (text) text.classList.remove('-streaming');
    es.close();
    if (state.eventSource === es) state.eventSource = null;
  });

  es.onerror = () => {
    if (text) text.classList.remove('-streaming');
    es.close();
    if (state.eventSource === es) state.eventSource = null;
  };
}

function renderProposed(proposed) {
  const head = $('#refl-proposal .refl-proposal-head');
  if (head) head.textContent = `Proposed: ${proposed.id} → ${proposed.id}'`;

  const changes = $('#refl-changes');
  if (!changes) return;
  const slots = (proposed.slots || []).map(s => {
    const v = s.kind === 'dynamic' ? 'dynamic' : (s.value || '—');
    return `<div class="refl-change">${escapeHTML(s.name)}: <b>${escapeHTML(v)}</b></div>`;
  });
  changes.innerHTML = slots.join('');
}

// ── Visitor panel ────────────────────────────────────────────────────

function applyVisitor(currentSession, recentEpisodes) {
  // Track current session id for choice-button POSTs
  state.currentSessionId = currentSession ? currentSession.id : null;

  const profile = currentSession ? currentSession.profile : null;
  const meta = $('#visitor-meta');

  if (!profile) {
    if (meta) meta.textContent = '— no active session —';
    setText('#visitor-name', '—');
    setText('#visitor-role', '—');
    setText('#visitor-archetype', '—');
    setText('#visitor-cluster', '—');
    setText('#visitor-seniority', '—');
    setText('#visitor-domain', '—');
    setText('#visitor-source', '—');
    setText('#visitor-embedding', '—');
    $('#visitor-signals').innerHTML = '<div class="post-snip">— none —</div>';
    return;
  }

  if (meta) {
    meta.textContent = `${profile.source_kind} · classified ${currentSession.cluster_id || '—'}`;
  }
  setText('#visitor-name', profile.name);
  setText('#visitor-role', profile.role);
  setText('#visitor-archetype', profile.id);
  setText('#visitor-cluster', currentSession.cluster_id || '—');
  setText('#visitor-seniority', profile.seniority);
  setText('#visitor-domain', profile.domain);
  setText('#visitor-source', profile.source_kind);
  setText('#visitor-embedding', profile.embedding ? `d=${profile.embedding.length}` : '— not embedded —');

  const signals = profile.recent_signals || [];
  $('#visitor-signals').innerHTML = signals.length
    ? signals.map(sig => `<div class="post-snip">${escapeHTML(sig)}</div>`).join('')
    : '<div class="post-snip">— none —</div>';
}

// ── Choice buttons ───────────────────────────────────────────────────

function applyChoices(currentSession) {
  // Only enable choices when an interactive session is in flight AND its
  // most-recent step has not yet recorded a visitor_choice (i.e., we're
  // waiting on the visitor to react).
  const hasOpenStep = currentSession
    && currentSession.dialogue
    && currentSession.dialogue.length
    && currentSession.dialogue[currentSession.dialogue.length - 1].visitor_choice == null;

  $$('.choice').forEach(btn => {
    if (hasOpenStep) {
      btn.removeAttribute('disabled');
      btn.classList.remove('-disabled');
    } else {
      btn.setAttribute('disabled', '');
      btn.classList.add('-disabled');
    }
  });
}

async function handleChoice(choice) {
  if (!state.currentSessionId) return;
  try {
    const result = await postJSON(`/sessions/${state.currentSessionId}/turn`, { visitor_choice: choice });
    if (result.terminated) {
      // Session ended — finalise the Episode so on_new_episode fires.
      try {
        await postJSON(`/sessions/${state.currentSessionId}/end`, {});
      } catch (e) {
        console.warn('end after terminate failed', e);
      }
    }
  } catch (e) {
    console.warn('turn failed', e);
  }
  await poll();
}

$$('.choice').forEach(btn => {
  btn.addEventListener('click', () => handleChoice(btn.dataset.choice));
});

// ── Operator buttons ─────────────────────────────────────────────────

$('#op-drift')?.addEventListener('click', async () => {
  await postJSON('/simulator/drift/ai_bubble_pops').catch(e => console.warn(e));
});

$('#op-segment')?.addEventListener('click', async () => {
  const id = SPAWNABLE_ROTATION[state.spawnIdx % SPAWNABLE_ROTATION.length];
  state.spawnIdx += 1;
  await postJSON('/simulator/inject_archetype', { archetype_id: id }).catch(e => console.warn(e));
});

$('#op-expert')?.addEventListener('click', () => {
  state.expertOn = !state.expertOn;
  document.body.classList.toggle('expert-off', !state.expertOn);
  const btn = $('#op-expert');
  if (btn) btn.textContent = state.expertOn ? 'Expert · On' : 'Expert · Off';
});

// ── Reflection accept/edit/keep ──────────────────────────────────────

$('#refl-accept')?.addEventListener('click', async () => {
  if (!state.activeRevisionId) return;
  await postJSON(`/revisions/${state.activeRevisionId}/decision`, { decision: 'accepted' })
    .catch(e => console.warn('accept', e));
  await poll();
});

$('#refl-keep')?.addEventListener('click', async () => {
  if (!state.activeRevisionId) return;
  await postJSON(`/revisions/${state.activeRevisionId}/decision`, { decision: 'rejected' })
    .catch(e => console.warn('keep', e));
  await poll();
});

$('#refl-edit')?.addEventListener('click', async () => {
  // Phase 2 keeps "Edit" minimal: same as Accept (operator can edit slots in a
  // future inline form). The endpoint accepts an `edited_rule` payload too.
  if (!state.activeRevisionId) return;
  await postJSON(`/revisions/${state.activeRevisionId}/decision`, { decision: 'edited' })
    .catch(e => console.warn('edit', e));
  await poll();
});

// ── Utility ──────────────────────────────────────────────────────────

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[c]));
}

// ── Live-mode form + Wi-Fi fallback ──────────────────────────────────

async function bootSources() {
  let sources;
  try {
    sources = await getJSON('/sessions/sources');
  } catch (e) {
    console.warn('sources failed', e);
    return;
  }
  state.liveMode = !!sources.live_mode;
  state.syntheticArchetypes = sources.synthetic_archetypes || [];

  // Populate fallback dropdown.
  const sel = $('#fallback-select');
  if (sel) {
    sel.innerHTML = state.syntheticArchetypes
      .map(a => `<option value="${escapeHTML(a)}">${escapeHTML(a)}</option>`)
      .join('');
  }

  // "Start Live" operator button is only useful when LinkedIn is the
  // active source. The dialog itself stays in the DOM (hidden) either way
  // so the fallback flow can still re-use its input.
  const toggle = $('#op-live-toggle');
  if (toggle) toggle.style.display = state.liveMode ? '' : 'none';
}

function setLiveStatus(msg, kind) {
  const el = $('#live-status');
  if (!el) return;
  el.textContent = msg || '';
  el.classList.remove('-error', '-ok');
  if (kind === 'error') el.classList.add('-error');
  if (kind === 'ok') el.classList.add('-ok');
}

async function startSession(sourceKind, identifier) {
  return await postJSON('/sessions/start', {
    source_kind: sourceKind,
    identifier: identifier,
  });
}

async function handleLiveStart() {
  const input = $('#live-url');
  const url = (input?.value || '').trim();
  if (!url) {
    setLiveStatus('paste a LinkedIn URL', 'error');
    return;
  }
  setLiveStatus('fetching…', 'ok');
  try {
    await startSession('linkedin_rapidapi', url);
    setLiveStatus('session live', 'ok');
    if (input) input.value = '';
    await poll();
  } catch (e) {
    const msg = String(e.message || e);
    if (/\b503\b/.test(msg) || /unavailable/i.test(msg)) {
      setLiveStatus('LinkedIn unavailable — falling back', 'error');
      state.pendingLiveUrl = url;
      hideLiveDialog();
      showFallback(`Wanted to fetch ${url}, but the source is unavailable. Pick a synthetic archetype to continue:`);
    } else if (/\b404\b/.test(msg) || /not found/i.test(msg)) {
      setLiveStatus('profile not found', 'error');
    } else {
      setLiveStatus('error: ' + msg.slice(0, 60), 'error');
    }
  }
}

function showFallback(body) {
  const dlg = $('#fallback-dialog');
  if (!dlg) return;
  if (body) setText('#fallback-body', body);
  dlg.classList.remove('-hidden');
}

function hideFallback() {
  const dlg = $('#fallback-dialog');
  if (dlg) dlg.classList.add('-hidden');
}

async function handleFallbackGo() {
  const sel = $('#fallback-select');
  const archetype = sel?.value;
  if (!archetype) {
    hideFallback();
    return;
  }
  hideFallback();
  setLiveStatus('starting synthetic ' + archetype, 'ok');
  try {
    await startSession('synthetic', archetype);
    setLiveStatus('synthetic visit live', 'ok');
    await poll();
  } catch (e) {
    setLiveStatus('synthetic start failed: ' + String(e.message || e).slice(0, 60), 'error');
  }
}

function showLiveDialog() {
  const dlg = $('#live-dialog');
  if (!dlg) return;
  dlg.classList.remove('-hidden');
  setLiveStatus('', null);
  const input = $('#live-url');
  if (input) {
    setTimeout(() => input.focus(), 0);
  }
}

function hideLiveDialog() {
  const dlg = $('#live-dialog');
  if (dlg) dlg.classList.add('-hidden');
}

$('#op-live-toggle')?.addEventListener('click', showLiveDialog);
$('#op-live-cancel')?.addEventListener('click', hideLiveDialog);
$('#op-live-start')?.addEventListener('click', async () => {
  await handleLiveStart();
  // If start succeeded (no error in status), close the dialog.
  const status = $('#live-status');
  if (status && !status.classList.contains('-error')) {
    hideLiveDialog();
  }
});
$('#live-url')?.addEventListener('keydown', async (e) => {
  if (e.key === 'Enter') {
    await handleLiveStart();
    const status = $('#live-status');
    if (status && !status.classList.contains('-error')) {
      hideLiveDialog();
    }
  } else if (e.key === 'Escape') {
    hideLiveDialog();
  }
});

$('#fallback-go')?.addEventListener('click', handleFallbackGo);
$('#fallback-cancel')?.addEventListener('click', () => {
  hideFallback();
  setLiveStatus('cancelled', 'error');
});

// ── Boot ─────────────────────────────────────────────────────────────

bootSources();
poll();
setInterval(poll, POLL_MS);
