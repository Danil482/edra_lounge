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

const IDLE_ARCHETYPES = [
  'Next visitor could be a Curious Journalist...',
  'Next visitor could be a Skeptical VC...',
  'Next visitor could be a Rising Postdoc...',
  'Next visitor could be a Senior Professor...',
  'Next visitor could be a Tech Founder...',
];

const ARCHETYPE_LABELS = {
  arch_phd_nlp_introvert: 'The Researcher',
  arch_postdoc_cv_ambitious: 'The Rising Star',
  arch_tech_founder_applied: 'The Founder',
  arch_senior_prof_meta: 'The Professor',
  arch_industry_pm_pragmatic: 'The Pragmatist',
  arch_research_engineer_skeptic: 'The Skeptic',
  arch_vc_investor: 'The Strategist',
  arch_journalist_curious: 'The Explorer',
  arch_professor_skeptic: 'The Skeptic',
  arch_postdoc_eager: 'The Rising Star',
  arch_industry_pragmatist: 'The Pragmatist',
  arch_student_enthusiast: 'The Enthusiast',
};

// Live cluster id → display label, rebuilt every cluster-viz poll from the
// /api/cluster-viz `clusters` array. Seeded real clusters are not in the
// hardcoded ARCHETYPE_LABELS map, so this is the authoritative source.
const clusterLabelById = {};

// Live rule id → Rule from the most recent /state snapshot. The demo theater is
// pending-only: when a revision is raised the active rule flips to
// under_revision but KEEPS its original ("before") slot values, while the
// proposed ("after") slots live only in the streamed revision payload. So this
// lookup is the baseline for the before → after diff in renderProposed().
const rulesById = {};

const AUTH_EMAIL_RE = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$/;

const WELCOME_TEXT = "Hi! I'm Edra, a research liaison from the DEFY Lab. I help connect researchers with collaborative opportunities. Ready to learn about what we can offer based on your profile?";

const state = {
  lastUtterance: null,
  lastInterest: null,
  typewriterTimer: null,
  activeRevisionId: null,
  eventSource: null,
  currentSessionId: null,
  liveMode: false,
  syntheticArchetypes: [],
  pendingLiveUrl: null,
  idleRotationIdx: 0,
  idleRotationTimer: null,
  visitorId: null,
  visitorEmail: null,
  lastEmotion: 'idle',
  lastBubbleText: null,
  bubbleTypewriterTimer: null,
  bubbleGeneration: 0,
  welcomeActive: false,
  sessionResolved: false,
  awaitingLLM: false,
  thoughtPending: false,
  pendingReply: null,
  pollTimer: null,
  clusterVizTimer: null,
  booted: false,
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

function getEmotion(session) {
  if (!session || !session.dialogue || session.dialogue.length === 0) return 'idle';

  const steps = session.dialogue;
  const lastStep = steps[steps.length - 1];
  const prevStep = steps.length >= 2 ? steps[steps.length - 2] : null;
  const interest = session.interest !== undefined ? session.interest : 0;
  const lastChoice = lastStep.visitor_choice;
  const prevChoice = prevStep ? prevStep.visitor_choice : null;

  if (interest >= 5) return 'excited';
  if (interest <= -5) return 'sad';

  if (steps.length === 1 && !lastChoice) return 'greeting';

  if (lastChoice === 'positive' && prevChoice === 'negative') return 'surprised';

  if (lastChoice === 'skeptical') {
    if (prevChoice === 'skeptical') return 'skeptical-high';
    return 'skeptical-low';
  }

  if (interest >= 3) return 'interested-high';
  if (interest >= 1) return 'interested-low';
  if (interest <= -3) return 'disappointed-high';
  if (interest <= -1) return 'disappointed-low';

  return 'greeting';
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
  applyBubble(s);
  applyGauge(s);
  applyRulebook(s.rules || []);
  applyReflection(s.active_revision);
  applyVisitor(s.current_session, s.recent_episodes);
  applyChoices(s.current_session);
  applyAvatar(s);
}

function applyTopStats(s) {
  const episodes = s.total_episodes || (s.recent_episodes || []).length;
  const activeRules = (s.rules || []).filter(r => r.status === 'active').length;
  const revising = s.active_revision ? 1 : 0;
  setText('#stat-episodes', episodes);
  setText('#stat-rules', activeRules);
  setText('#stat-revising', revising);

  const injectBtn = $('#op-inject');
  if (injectBtn) injectBtn.disabled = !s.current_session;

  const strip = document.querySelector('.edge-top');
  if (strip) {
    strip.dataset.label = `▼  EDRA  ·  ${episodes} EPISODES  ·  ${activeRules} RULES  ·  ${revising} REVISING  ▼`;
  }
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
  if (state.welcomeActive) return;

  const step = pickStep(s);
  const utter = $('#utterance');
  const idleHero = $('#idle-hero');
  const thoughtBlock = $('#thought-block');
  const textbox = $('.textbox');

  if (textbox) textbox.classList.add('-bubble-hidden');

  if (!step) {
    if (idleHero) idleHero.classList.remove('-hidden');
    if (thoughtBlock) thoughtBlock.style.display = 'none';
    utter.style.display = 'none';
    $('#continue-marker').style.display = 'none';
    // In bubble mode, also hide the bubble when idle
    const bubble = $('#speech-bubble');
    if (bubble) bubble.classList.add('-hidden');
    state.lastBubbleText = null;
    startIdleRotation();
    return;
  }

  if (idleHero) idleHero.classList.add('-hidden');
  if (thoughtBlock) thoughtBlock.style.display = '';
  utter.style.display = '';
  $('#continue-marker').style.display = '';
  stopIdleRotation();

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

function startIdleRotation() {
  if (state.idleRotationTimer) return;
  const el = $('#idle-rotation');
  if (!el) return;
  el.textContent = IDLE_ARCHETYPES[state.idleRotationIdx % IDLE_ARCHETYPES.length];
  el.classList.remove('-fading');
  state.idleRotationTimer = setInterval(() => {
    el.classList.add('-fading');
    setTimeout(() => {
      state.idleRotationIdx = (state.idleRotationIdx + 1) % IDLE_ARCHETYPES.length;
      el.textContent = IDLE_ARCHETYPES[state.idleRotationIdx];
      el.classList.remove('-fading');
    }, 600);
  }, 4000);
}

function stopIdleRotation() {
  if (!state.idleRotationTimer) return;
  clearInterval(state.idleRotationTimer);
  state.idleRotationTimer = null;
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

// ── Speech bubble ────────────────────────────────────────────────────

function applyBubble(s) {
  if (state.welcomeActive) return;

  const bubble = $('#speech-bubble');
  if (!bubble) return;

  if (state.thoughtPending) return;

  const step = pickStep(s);

  if (!step || !step.agent_reply) {
    bubble.classList.add('-hidden');
    state.lastBubbleText = null;
    return;
  }

  bubble.classList.remove('-hidden');

  if (step.agent_reply !== state.lastBubbleText) {
    if (step.agent_thought && !step.agent_thought.startsWith('(')) {
      state.thoughtPending = true;
      state.pendingReply = step.agent_reply;
      state.lastBubbleText = step.agent_reply;
      showThoughtThenReply(step.agent_thought, step.agent_reply);
    } else {
      state.lastBubbleText = step.agent_reply;
      bubbleTransition(step.agent_reply);
    }
  }
}

function showThoughtThenReply(thought, reply) {
  const bubble = $('#speech-bubble');
  const textEl = $('#speech-bubble-text');
  if (!bubble || !textEl) return;

  if (state.bubbleTypewriterTimer) {
    clearInterval(state.bubbleTypewriterTimer);
    state.bubbleTypewriterTimer = null;
  }

  const gen = ++state.bubbleGeneration;

  bubble.classList.remove('-fade-in', '-fade-out');
  bubble.classList.add('-thought');

  textEl.innerHTML = '';
  const em = document.createElement('em');
  textEl.appendChild(em);

  let i = 0;
  const charStep = 1000 / TYPEWRITER_CPS;
  state.bubbleTypewriterTimer = setInterval(() => {
    if (gen !== state.bubbleGeneration) {
      clearInterval(state.bubbleTypewriterTimer);
      state.bubbleTypewriterTimer = null;
      return;
    }
    if (i >= thought.length) {
      clearInterval(state.bubbleTypewriterTimer);
      state.bubbleTypewriterTimer = null;
      const hint = document.createElement('div');
      hint.className = 'bubble-continue-hint';
      hint.textContent = '▸ Click to continue';
      textEl.appendChild(hint);
      waitForContinue(() => {
        if (gen !== state.bubbleGeneration) return;
        state.thoughtPending = false;
        state.pendingReply = null;
        bubble.classList.remove('-thought');
        bubbleTransition(reply);
      });
      return;
    }
    em.textContent += thought.charAt(i++);
  }, charStep);
}

function waitForContinue(callback) {
  function onClick(e) {
    if (e.target.closest('.choice') || e.target.closest('.resolve-btn')) return;
    cleanup();
    callback();
  }
  function onKey(e) {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      cleanup();
      callback();
    }
  }
  function cleanup() {
    document.removeEventListener('click', onClick);
    document.removeEventListener('keydown', onKey);
  }
  document.addEventListener('click', onClick);
  document.addEventListener('keydown', onKey);
}

function bubbleTransition(text) {
  const bubble = $('#speech-bubble');
  const textEl = $('#speech-bubble-text');
  if (!bubble || !textEl) return;

  if (state.bubbleTypewriterTimer) {
    clearInterval(state.bubbleTypewriterTimer);
    state.bubbleTypewriterTimer = null;
  }

  const gen = ++state.bubbleGeneration;

  bubble.classList.remove('-fade-in');
  bubble.classList.add('-fade-out');

  setTimeout(() => {
    if (gen !== state.bubbleGeneration) return;

    textEl.textContent = '';
    bubble.classList.remove('-fade-out');
    bubble.classList.add('-fade-in');

    let i = 0;
    const step = 1000 / TYPEWRITER_CPS;
    state.bubbleTypewriterTimer = setInterval(() => {
      if (gen !== state.bubbleGeneration || i >= text.length) {
        clearInterval(state.bubbleTypewriterTimer);
        state.bubbleTypewriterTimer = null;
        return;
      }
      textEl.textContent += text.charAt(i++);
    }, step);
  }, 300);
}

// Bubble mode is always on — hide the panel textbox on init
{
  const tb = $('.textbox');
  if (tb) tb.classList.add('-bubble-hidden');
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

  const gauge = $('.gauge');
  if (gauge) {
    gauge.classList.remove('-terminal-accepted', '-terminal-rejected');
    if (interest >= 5) gauge.classList.add('-terminal-accepted');
    if (interest <= -5) gauge.classList.add('-terminal-rejected');
  }

}

// ── Avatar ──────────────────────────────────────────────────────────

function setAvatarEmotion(emotion) {
  const avatar = $('#edra-avatar');
  if (!avatar || emotion === state.lastEmotion) return;
  const newSrc = `assets/avatar/edra-${emotion}.png?v=2`;
  avatar.style.opacity = '0';
  setTimeout(() => {
    avatar.src = newSrc;
    avatar.onload = () => { avatar.style.opacity = '1'; };
  }, 450);
  state.lastEmotion = emotion;
  avatar.setAttribute('data-emotion', emotion);
}

function applyAvatar(s) {
  if (state.welcomeActive || state.awaitingLLM) return;

  const avatar = $('#edra-avatar');
  if (!avatar) return;
  const placeholder = $('#agent-slot-placeholder');

  const session = s.current_session;
  const emotion = getEmotion(session);

  setText('#agent-emotion', `current — ${emotion}`);

  if (session && session.dialogue && session.dialogue.length > 0) {
    avatar.style.display = '';
    if (!avatar.classList.contains('-visible')) {
      avatar.classList.add('-entering');
      avatar.addEventListener('animationend', () => {
        avatar.classList.remove('-entering');
        avatar.classList.add('-visible');
      }, { once: true });
    }
    if (placeholder) placeholder.style.display = 'none';

    if (emotion !== state.lastEmotion) {
      const newSrc = `assets/avatar/edra-${emotion}.png?v=2`;
      avatar.style.opacity = '0';
      setTimeout(() => {
        avatar.src = newSrc;
        avatar.onload = () => { avatar.style.opacity = '1'; };
      }, 450);
      state.lastEmotion = emotion;
    }
  } else {
    avatar.src = 'assets/avatar/edra-idle.png?v=2';
    avatar.style.display = '';
    avatar.style.opacity = '1';
    avatar.classList.remove('-entering');
    avatar.classList.add('-visible');
    if (placeholder) placeholder.style.display = 'none';
    state.lastEmotion = 'idle';
  }

  avatar.setAttribute('data-emotion', emotion);
}

// ── Rulebook ─────────────────────────────────────────────────────────

function applyRulebook(rules) {
  for (const r of rules) {
    if (r && r.id) rulesById[r.id] = r;
  }

  const meta = $('#rulebook-meta');
  const list = $('#rules-list');
  if (!list) return;

  const active = rules.filter(r => r.status === 'active').length;
  const deprecated = rules.filter(r => r.status === 'deprecated').length;
  const revising = rules.filter(r => r.status === 'under_revision').length;

  const strip = document.querySelector('.edge-left');
  if (strip) {
    strip.dataset.label = `◀  RULEBOOK  ·  ${active} ACTIVE  ·  ${revising} REVISING  ·  HOVER`;
  }

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

  const clusterLabel = clusterLabelById[rule.cluster_id]
    || ARCHETYPE_LABELS[rule.cluster_id]
    || rule.cluster_id;

  if (rule.status === 'deprecated') {
    return `
      <div class="${cls.join(' ')}">
        <div class="rule-num">${num}</div>
        <div class="rule-body">
          <span class="if">If</span><span class="clu">${escapeHTML(clusterLabel)} <em>(replaced by ${escapeHTML(rule.deprecated_by || '—')})</em></span>
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
    if (!s) return '<span class="slot-val">—</span>';
    if (s.kind === 'dynamic') return `<span class="slot-val -dynamic">dynamic</span>`;
    return `<span class="slot-val">${escapeHTML(s.value || '—')}</span>`;
  };

  return `
    <div class="${cls.join(' ')}">
      <div class="rule-num">${num}</div>
      <div class="rule-body">
        <span class="if">If</span><span class="clu">${escapeHTML(clusterLabel)}</span><br>
        <span class="then">Then</span>
        <div class="slot-grid">
          <span class="slot-pair"><span class="slot-label">framing</span>${slotChip('framing')}</span>
          <span class="slot-pair"><span class="slot-label">tone</span>${slotChip('tone')}</span>
          <span class="slot-pair"><span class="slot-label">opener</span>${slotChip('opener_type')}</span>
          <span class="slot-pair"><span class="slot-label">words</span>${slotChip('word_target')}</span>
          <span class="slot-pair"><span class="slot-label">ask</span>${slotChip('ask_size')}</span>
        </div>
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

function slotDisplay(slot) {
  if (!slot) return '—';
  if (slot.kind === 'dynamic') return 'dynamic';
  return slot.value || '—';
}

function renderProposed(proposed) {
  const head = $('#refl-proposal .refl-proposal-head');
  if (head) head.textContent = `Proposed: ${proposed.id} → ${proposed.id}'`;

  const changes = $('#refl-changes');
  if (!changes) return;

  // Baseline ("before") is the rule with the same id in the latest /state
  // snapshot — its slots still hold the original values (pending-only theater).
  const baseline = rulesById[proposed.id];
  const baseSlots = {};
  if (baseline) {
    for (const s of baseline.slots || []) baseSlots[s.name] = s;
  }

  const rows = (proposed.slots || []).map(s => {
    const after = slotDisplay(s);

    // Fallback: no baseline for this rule id (race, or rule not yet in state) —
    // render the proposed value only, highlighted, as before.
    if (!baseline) {
      return `<div class="refl-change -changed">${escapeHTML(s.name)}: <b>${escapeHTML(after)}</b></div>`;
    }

    const before = slotDisplay(baseSlots[s.name]);
    const changed = before !== after;
    const cls = changed ? 'refl-change -changed' : 'refl-change -unchanged';
    return `<div class="${cls}">`
      + `<span class="refl-slot-name">${escapeHTML(s.name)}</span>`
      + `<span class="refl-diff">`
      + `<s>${escapeHTML(before)}</s>`
      + `<span class="refl-arrow">→</span>`
      + `<b>${escapeHTML(after)}</b>`
      + `</span>`
      + `</div>`;
  });
  changes.innerHTML = rows.join('');
}

// ── Visitor panel ────────────────────────────────────────────────────

function applyVisitor(currentSession, recentEpisodes) {
  // Track current session id for choice-button POSTs
  state.currentSessionId = currentSession ? currentSession.id : null;

  const profile = currentSession ? currentSession.profile : null;
  const meta = $('#visitor-meta');
  const strip = document.querySelector('.edge-right');

  if (!profile) {
    if (strip) strip.dataset.label = '◀  SUBJECT  ·  NO ACTIVE SESSION  ·  HOVER';
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
    setVisitorAvatar(null);
    return;
  }

  const clusterId = currentSession.cluster_id;
  const clusterName = clusterId
    ? (clusterLabelById[clusterId] || ARCHETYPE_LABELS[clusterId] || clusterId)
    : null;

  if (meta) {
    const clLabel = clusterName || 'unclustered';
    meta.textContent = `${profile.source_kind} · ${clLabel}`;
  }
  if (strip) strip.dataset.label = `◀  SUBJECT  ·  ${profile.name}  ·  HOVER`;
  setText('#visitor-name', profile.name);
  setText('#visitor-role', profile.role);
  setText('#visitor-archetype', clusterName || 'Unclustered — improvising');
  setText('#visitor-cluster', clusterName || '—');
  setText('#visitor-seniority', profile.seniority);
  setText('#visitor-domain', profile.domain);
  setText('#visitor-source', profile.source_kind);
  setText('#visitor-embedding', profile.embedding ? `d=${profile.embedding.length}` : '— not embedded —');
  setVisitorAvatar(profile.avatar_url || null);

  const signals = profile.recent_signals || [];
  $('#visitor-signals').innerHTML = signals.length
    ? signals.map(sig => `<div class="post-snip">${escapeHTML(sig)}</div>`).join('')
    : '<div class="post-snip">— none —</div>';
}

function setVisitorAvatar(url) {
  const box = $('#visitor-portrait-box');
  const img = $('#visitor-avatar');
  if (!box || !img) {
    console.warn('setVisitorAvatar: portrait elements not found in DOM');
    return;
  }
  if (url) {
    console.log('setVisitorAvatar: loading', url);
    // Reveal only after the image loads — if it 404s (signed URL expired,
    // network blocked, etc.) we silently fall back to the placeholder.
    img.onload = () => {
      console.log('setVisitorAvatar: loaded ✓');
      box.classList.add('-has-image');
    };
    img.onerror = (e) => {
      console.warn('setVisitorAvatar: image failed to load (expired/CORS/blocked)', e);
      box.classList.remove('-has-image');
    };
    img.setAttribute('src', url);
  } else {
    console.log('setVisitorAvatar: no url, showing placeholder');
    img.removeAttribute('src');
    box.classList.remove('-has-image');
  }
}

// ── Choice buttons ───────────────────────────────────────────────────

const STATIC_LABELS = {
  positive: 'Tell me more.',
  skeptical: 'Skeptical, why Defy?',
  negative: 'Not interested.',
};

function applyChoices(currentSession) {
  if (state.welcomeActive) return;

  const lastStep = currentSession
    && currentSession.dialogue
    && currentSession.dialogue.length
    ? currentSession.dialogue[currentSession.dialogue.length - 1]
    : null;

  const hasOpenStep = lastStep && lastStep.visitor_choice == null && !state.thoughtPending;
  const sessionActive = !!currentSession && !state.sessionResolved;

  const optionsBySentiment = {};
  if (lastStep && lastStep.response_options && lastStep.response_options.length === 3) {
    for (const opt of lastStep.response_options) {
      optionsBySentiment[opt.sentiment] = opt.text;
    }
  }

  $$('.choice').forEach(btn => {
    const sentiment = btn.dataset.choice;
    const label = optionsBySentiment[sentiment] || STATIC_LABELS[sentiment] || sentiment;
    const labelSpan = btn.querySelector('span:last-child');
    if (labelSpan && labelSpan.textContent !== label) {
      labelSpan.textContent = label;
    }

    if (hasOpenStep && !state.sessionResolved) {
      btn.removeAttribute('disabled');
      btn.classList.remove('-disabled');
    } else {
      btn.setAttribute('disabled', '');
      btn.classList.add('-disabled');
    }
  });

  const acceptBtn = $('#resolve-accept');
  const declineBtn = $('#resolve-decline');
  if (sessionActive && !state.sessionResolved) {
    if (acceptBtn) { acceptBtn.disabled = false; acceptBtn.classList.remove('-disabled'); }
    if (declineBtn) { declineBtn.disabled = false; declineBtn.classList.remove('-disabled'); }
  } else {
    if (acceptBtn) { acceptBtn.disabled = true; acceptBtn.classList.add('-disabled'); }
    if (declineBtn) { declineBtn.disabled = true; declineBtn.classList.add('-disabled'); }
  }
}

async function handleChoice(choice) {
  if (!state.currentSessionId || state.sessionResolved) return;
  state.awaitingLLM = true;
  setAvatarEmotion('thinking');
  try {
    const result = await postJSON(`/sessions/${state.currentSessionId}/turn`, { visitor_choice: choice });
    state.awaitingLLM = false;
    if (result.terminated) {
      state.sessionResolved = true;
      disableAllButtons();
      const outcome = result.outcome;
      try {
        await postJSON(`/sessions/${state.currentSessionId}/end`, { visitor_email: state.visitorEmail });
      } catch (e) {
        console.warn('end after terminate failed', e);
      }
      await poll();
      if (outcome === 'accepted' || outcome === 'rejected') {
        setTimeout(() => showEndDialog(outcome), 1000);
      }
      return;
    }
  } catch (e) {
    state.awaitingLLM = false;
    console.warn('turn failed', e);
  }
  await poll();
}

$$('.choice').forEach(btn => {
  btn.addEventListener('click', () => handleChoice(btn.dataset.choice));
});

// ── Resolve buttons (Accept / Decline) ──────────────────────────────

async function handleResolve(decision) {
  if (!state.currentSessionId || state.sessionResolved) return;

  state.sessionResolved = true;
  disableAllButtons();

  try {
    await postJSON(`/sessions/${state.currentSessionId}/resolve`, { decision, visitor_email: state.visitorEmail });
  } catch (e) {
    console.warn('resolve failed', e);
  }

  await poll();

  const outcome = decision === 'accept' ? 'accepted' : 'rejected';
  setTimeout(() => showEndDialog(outcome), 600);
}

function disableAllButtons() {
  $$('.choice').forEach(btn => {
    btn.setAttribute('disabled', '');
    btn.classList.add('-disabled');
  });
  const acceptBtn = $('#resolve-accept');
  const declineBtn = $('#resolve-decline');
  if (acceptBtn) { acceptBtn.disabled = true; acceptBtn.classList.add('-disabled'); }
  if (declineBtn) { declineBtn.disabled = true; declineBtn.classList.add('-disabled'); }
}

$('#resolve-accept')?.addEventListener('click', () => handleResolve('accept'));
$('#resolve-decline')?.addEventListener('click', () => handleResolve('decline'));

// ── Operator buttons ─────────────────────────────────────────────────

// Inject Contradiction — no body; the backend picks the largest cluster.
$('#op-inject')?.addEventListener('click', async () => {
  await postJSON('/simulator/inject_contradiction', {})
    .catch(e => console.warn(e));
});

// ── Reflection console — single OK (preview, no real rule change) ─────

// "OK" acknowledges the preview and rolls everything back: deletes the
// injected episodes + pending revision and restores the rule to active.
$('#refl-ok')?.addEventListener('click', async () => {
  await postJSON('/simulator/reset_injection', {}).catch(e => console.warn('ok', e));
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

}

async function startSession(sourceKind, identifier) {
  return await postJSON('/sessions/start', {
    source_kind: sourceKind,
    identifier: identifier,
  });
}

// ── End-of-dialog popup ─────────────────────────────────────────

function showEndDialog(outcome) {
  const overlay = $('#end-dialog');
  const card = $('#end-card');
  if (!overlay || !card) return;

  card.classList.remove('-success', '-failure');

  if (outcome === 'accepted') {
    card.classList.add('-success');
    setText('#end-headline', 'Collaboration Initiated');
    setText('#end-body',
      'We\'ll send a personalized follow-up to your email shortly based on our conversation. Looking forward to working together.');
  } else {
    card.classList.add('-failure');
    setText('#end-headline', 'Until Next Time');
    setText('#end-body',
      'We appreciate your time. We\'ll send a brief summary of our conversation to your email. If you\'d like to explore collaboration in the future, you know where to find us.');
  }

  overlay.classList.remove('-hidden');
}

function hideEndDialog() {
  const overlay = $('#end-dialog');
  if (overlay) overlay.classList.add('-hidden');
  state.lastUtterance = null;
  state.lastInterest = null;
  state.lastBubbleText = null;
  state.sessionResolved = false;
  state.currentSessionId = null;
  state.thoughtPending = false;
  state.pendingReply = null;
  state.lastEmotion = null;
  if (state.pollTimer != null) { clearInterval(state.pollTimer); state.pollTimer = null; }
  if (state.clusterVizTimer != null) { clearInterval(state.clusterVizTimer); state.clusterVizTimer = null; }
  resetAuthGate();
}

function resetAuthGate() {
  state.visitorId = null;
  state.visitorEmail = null;

  const overlay = $('#auth-overlay');
  const input = $('#auth-email');
  const submit = $('#auth-submit');
  const error = $('#auth-error');

  if (input) {
    input.value = '';
    input.classList.remove('-invalid');
  }
  if (error) error.textContent = '';
  if (submit) submit.disabled = true;

  // Reverse exactly what the submit handler did when it faded the gate out.
  if (overlay) {
    overlay.classList.remove('-fading');
    overlay.style.display = '';
  }
  const stage = $('#stage');
  if (stage) stage.style.display = 'none';

  if (input) input.focus();
}

$('#end-btn')?.addEventListener('click', hideEndDialog);

// ── Cluster visualization ────────────────────────────────────────────

const CLUSTER_VIZ_POLL_MS = 5000;

const clusterVizState = {
  lastData: null,
  animFrame: null,
  pulsePhase: 0,
};

async function pollClusterViz() {
  let data;
  try {
    data = await getJSON('/api/cluster-viz');
  } catch (e) {
    return;
  }
  clusterVizState.lastData = data;
  renderClusterViz(data);
}

function renderClusterViz(data) {
  const placeholder = $('#cluster-viz-placeholder');
  const canvas = $('#cluster-viz-canvas');
  const legend = $('#cluster-viz-legend');
  const neighborsList = $('#neighbors-list');

  if (!data || data.status !== 'ok' || !data.points || data.points.length === 0) {
    if (placeholder) placeholder.classList.remove('-hidden');
    if (placeholder) placeholder.textContent = data && data.status === 'no_embeddings'
      ? 'No profile embeddings yet...'
      : `Need ${5 - (data?.points?.length || 0)} more visitors to cluster`;
    if (legend) legend.innerHTML = '';
    if (neighborsList) neighborsList.innerHTML = '<div class="neighbor-empty">— awaiting visitor —</div>';
    return;
  }

  if (placeholder) placeholder.classList.add('-hidden');

  rebuildClusterLabels(data.clusters);
  drawScatterPlot(canvas, data);
  renderLegend(legend, data.clusters);
  renderNeighbors(neighborsList, data.neighbors, data.archetype_label);

  const archetypeVal = $('#visitor-archetype');
  if (archetypeVal && data.archetype_label) {
    archetypeVal.textContent = data.archetype_label;
  }
}

function drawScatterPlot(canvas, data) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  ctx.fillStyle = '#2D2D2D';
  ctx.fillRect(0, 0, w, h);

  const pad = 16;
  const plotW = w - 2 * pad;
  const plotH = h - 2 * pad;

  ctx.strokeStyle = 'rgba(243, 241, 236, 0.06)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {
    const gx = pad + (plotW * i / 4);
    ctx.beginPath();
    ctx.moveTo(gx, pad);
    ctx.lineTo(gx, pad + plotH);
    ctx.stroke();

    const gy = pad + (plotH * i / 4);
    ctx.beginPath();
    ctx.moveTo(pad, gy);
    ctx.lineTo(pad + plotW, gy);
    ctx.stroke();
  }

  const current = data.current_visitor;

  for (const pt of data.points) {
    if (pt.is_current) continue;
    const px = pad + pt.x * plotW;
    const py = pad + pt.y * plotH;
    const radius = 18;

    ctx.beginPath();
    ctx.arc(px, py, radius + 6, 0, Math.PI * 2);
    ctx.fillStyle = hexToRGBA(pt.color, 0.1);
    ctx.fill();

    ctx.beginPath();
    ctx.arc(px, py, radius, 0, Math.PI * 2);
    ctx.fillStyle = hexToRGBA(pt.color, 0.25);
    ctx.fill();
    ctx.strokeStyle = pt.color;
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(px, py, 4, 0, Math.PI * 2);
    ctx.fillStyle = pt.color;
    ctx.fill();

  }

  if (current) {
    const cx = pad + current.x * plotW;
    const cy = pad + current.y * plotH;

    clusterVizState.pulsePhase = (clusterVizState.pulsePhase + 0.08) % (Math.PI * 2);
    const pulseScale = 1 + 0.3 * Math.sin(clusterVizState.pulsePhase);
    const outerR = 8 * pulseScale;

    ctx.beginPath();
    ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(204, 0, 0, 0.2)';
    ctx.fill();

    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#CC0000';
    ctx.fill();
    ctx.strokeStyle = '#F3F1EC';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.fillStyle = '#F3F1EC';
    ctx.font = '500 10px "DM Sans", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('YOU', cx + 9, cy + 4);
  }

  if (clusterVizState.lastData === data && current) {
    if (clusterVizState.animFrame) cancelAnimationFrame(clusterVizState.animFrame);
    clusterVizState.animFrame = requestAnimationFrame(() => drawScatterPlot(canvas, data));
  }
}

function hexToRGBA(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function rebuildClusterLabels(clusters) {
  if (!clusters) return;
  for (const c of clusters) {
    clusterLabelById[c.id] = c.archetype || c.label || c.id;
  }
}

function renderLegend(el, clusters) {
  if (!el || !clusters) return;
  el.innerHTML = clusters.map(c =>
    `<div class="legend-item">
      <div class="legend-dot" style="background:${escapeHTML(c.color)}"></div>
      <span>${escapeHTML(c.archetype)}</span>
    </div>`
  ).join('');
}

function renderNeighbors(el, neighbors, archetypeLabel) {
  if (!el) return;
  if (!neighbors || neighbors.length === 0) {
    el.innerHTML = '<div class="neighbor-empty">— awaiting visitor —</div>';
    return;
  }

  el.innerHTML = neighbors.slice(0, 5).map((n, i) => {
    const initials = (n.name || '?').split(' ').map(w => w[0] || '').join('').slice(0, 2).toUpperCase();
    const avatarContent = n.avatar_url
      ? `<img src="${escapeHTML(n.avatar_url)}" alt="" onerror="this.parentNode.innerHTML='${initials}'">`
      : initials;
    const simPct = Math.round(n.similarity * 100);
    const simClass = simPct >= 90 ? '-top' : (simPct >= 70 ? '-high' : '');
    return `<div class="neighbor-card">
      <div class="neighbor-avatar">${avatarContent}</div>
      <div class="neighbor-info">
        <div class="neighbor-name">${escapeHTML(n.name)}</div>
        <div class="neighbor-role">${escapeHTML(n.role)}</div>
      </div>
      <div class="neighbor-sim ${simClass}">${simPct}%</div>
    </div>`;
  }).join('');
}

// ── Auth gate ────────────────────────────────────────────────────────

function initAuthGate() {
  const overlay = $('#auth-overlay');
  const form = $('#auth-form');
  const input = $('#auth-email');
  const submit = $('#auth-submit');
  const error = $('#auth-error');

  if (!overlay || !form) {
    bootAfterAuth();
    return;
  }

  input.addEventListener('input', () => {
    const valid = AUTH_EMAIL_RE.test(input.value.trim());
    submit.disabled = !valid;
    if (valid) {
      input.classList.remove('-invalid');
      error.textContent = '';
    }
  });

  input.addEventListener('blur', () => {
    const val = input.value.trim();
    if (val && !AUTH_EMAIL_RE.test(val)) {
      input.classList.add('-invalid');
      error.textContent = 'Please enter a valid email address';
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = input.value.trim();
    if (!AUTH_EMAIL_RE.test(email)) return;

    submit.disabled = true;
    error.textContent = '';

    try {
      const res = await postJSON('/api/visitors', { email });
      state.visitorId = res.id;
      state.visitorEmail = res.email;

      overlay.classList.add('-fading');
      setTimeout(() => {
        overlay.style.display = 'none';
        const stage = $('#stage');
        if (stage) stage.style.display = '';
        bootAfterAuth();
      }, 500);
    } catch (err) {
      error.textContent = 'Something went wrong. Please try again.';
      submit.disabled = false;
    }
  });
}

function showWelcome() {
  state.welcomeActive = true;

  const avatar = $('#edra-avatar');
  if (avatar) {
    avatar.src = 'assets/avatar/edra-idle.png?v=2';
    avatar.style.display = '';
    avatar.style.opacity = '1';
    avatar.classList.remove('-entering');
    avatar.classList.add('-visible');
    avatar.setAttribute('data-emotion', 'idle');
    const placeholder = $('#agent-slot-placeholder');
    if (placeholder) placeholder.style.display = 'none';
  }

  const idleHero = $('#idle-hero');
  if (idleHero) idleHero.classList.add('-hidden');

  const thoughtBlock = $('#thought-block');
  if (thoughtBlock) thoughtBlock.style.display = 'none';

  const utter = $('#utterance');
  if (utter) {
    utter.style.display = '';
    utter.classList.remove('-waiting');
  }
  const marker = $('#continue-marker');
  if (marker) marker.style.display = 'none';

  stopIdleRotation();

  const bubble = $('#speech-bubble');
  if (bubble) {
    bubble.classList.remove('-hidden', '-thought');
    const textEl = $('#speech-bubble-text');
    if (textEl) textEl.innerHTML = '';
    bubbleTransition(WELCOME_TEXT);
  }

  const choices = $('#choices');
  if (choices) choices.style.display = 'none';

  const resolveAccept = $('#resolve-accept');
  const resolveDecline = $('#resolve-decline');
  if (resolveAccept) resolveAccept.style.display = 'none';
  if (resolveDecline) resolveDecline.style.display = 'none';

  const welcomeBtn = document.createElement('button');
  welcomeBtn.className = 'welcome-cta';
  welcomeBtn.id = 'welcome-start-btn';
  welcomeBtn.textContent = 'Start Conversation';

  const choicesParent = choices ? choices.parentNode : null;
  if (choicesParent && choices) {
    choicesParent.insertBefore(welcomeBtn, choices);
  }

  welcomeBtn.style.position = 'absolute';
  welcomeBtn.style.left = '50%';
  welcomeBtn.style.transform = 'translateX(-50%)';
  welcomeBtn.style.bottom = '130px';
  welcomeBtn.style.zIndex = '10';

  welcomeBtn.addEventListener('click', () => {
    welcomeBtn.disabled = true;
    welcomeBtn.style.opacity = '0.5';
    showSessionStartDialog(welcomeBtn, choices, resolveAccept, resolveDecline);
  });
}

// ── Session-start dialog (welcome flow) ─────────────────────────────

function showSessionStartDialog(welcomeBtn, choices, resolveAccept, resolveDecline) {
  const dlg = $('#session-start-dialog');
  if (!dlg) return;

  setSessionStartStatus('', null);
  dlg.classList.remove('-hidden');

  const urlInput = $('#session-start-url');
  if (urlInput) setTimeout(() => urlInput.focus(), 0);

  function teardown() {
    dlg.classList.add('-hidden');
    welcomeBtn.remove();
    state.welcomeActive = false;
    if (choices) choices.style.display = '';
    if (resolveAccept) resolveAccept.style.display = '';
    if (resolveDecline) resolveDecline.style.display = '';
  }

  function startPolling() {
    poll();
    pollClusterViz();
    // Guard against stacking a fresh pair of intervals on every session start —
    // hideEndDialog → showWelcome → showSessionStartDialog re-enters this path,
    // and unguarded setInterval would leave the old pollers running forever.
    if (state.pollTimer == null) {
      state.pollTimer = setInterval(poll, POLL_MS);
    }
    if (state.clusterVizTimer == null) {
      state.clusterVizTimer = setInterval(pollClusterViz, CLUSTER_VIZ_POLL_MS);
    }
  }

  function closeAndRestore() {
    dlg.classList.add('-hidden');
    welcomeBtn.disabled = false;
    welcomeBtn.style.opacity = '';
  }

  const oldLiveGo = $('#session-start-live-go');
  if (oldLiveGo) oldLiveGo.replaceWith(oldLiveGo.cloneNode(true));
  const oldUrlEl = $('#session-start-url');
  if (oldUrlEl) { const c = oldUrlEl.cloneNode(true); oldUrlEl.replaceWith(c); }

  const liveGoHandler = async () => {
    const urlEl = $('#session-start-url');
    const btn = $('#session-start-live-go');
    const url = (urlEl?.value || '').trim();
    if (!url) {
      setSessionStartStatus('paste a LinkedIn URL', 'error');
      return;
    }
    setSessionStartStatus('fetching...', 'ok');
    setAvatarEmotion('thinking');
    if (btn) btn.disabled = true;
    try {
      await startSession('linkedin_rapidapi', url);
      teardown();
      startPolling();
    } catch (e) {
      if (btn) btn.disabled = false;
      const msg = String(e.message || e);
      if (/\b503\b/.test(msg) || /unavailable/i.test(msg)) {
        setSessionStartStatus('LinkedIn unavailable', 'error');
      } else if (/\b404\b/.test(msg) || /not found/i.test(msg)) {
        setSessionStartStatus('profile not found', 'error');
      } else {
        setSessionStartStatus('error: ' + msg.slice(0, 60), 'error');
      }
    }
  };
  const liveGoBtn = $('#session-start-live-go');
  // The previous session disabled this button on submit and never re-enabled it
  // on the success path. cloneNode(true) above copies the reflected `disabled`
  // attribute, so without this the second open is born disabled and the dialog
  // is stuck. Clear it every time the dialog opens.
  if (liveGoBtn) liveGoBtn.disabled = false;
  liveGoBtn?.addEventListener('click', liveGoHandler);
  $('#session-start-url')?.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') await liveGoHandler();
    else if (e.key === 'Escape') closeAndRestore();
  });

  const cancelBtn = $('#session-start-cancel');
  cancelBtn?.replaceWith(cancelBtn.cloneNode(true));
  $('#session-start-cancel')?.addEventListener('click', closeAndRestore);
}

function setSessionStartStatus(msg, kind) {
  const el = $('#session-start-status');
  if (!el) return;
  el.textContent = msg || '';
  el.classList.remove('-error', '-ok');
  if (kind === 'error') el.classList.add('-error');
  if (kind === 'ok') el.classList.add('-ok');
}

async function bootAfterAuth() {
  if (!state.booted) {
    state.booted = true;
    ['idle','greeting','interested-low','interested-high','excited','thinking',
     'skeptical-low','skeptical-high','disappointed-low','disappointed-high','sad','surprised'
    ].forEach(e => { const i = new Image(); i.src = `assets/avatar/edra-${e}.png?v=2`; });

    await bootSources();
  }
  showWelcome();
}

// ── Boot ─────────────────────────────────────────────────────────────

initAuthGate();
