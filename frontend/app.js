/*
  Phase 1 stub — polls /state every 1000ms and renders into the three panels.
  Token-by-token reflection console via SSE lands in Phase 2.
*/

const API = "";  // same origin — FastAPI serves us
const POLL_MS = 1000;

const $ = (sel) => document.querySelector(sel);

async function getState() {
  const r = await fetch(`${API}/state`);
  if (!r.ok) throw new Error(`state ${r.status}`);
  return r.json();
}

function renderClock(clock) {
  $("#clock").textContent = `day ${clock.day} · ${clock.time}`;
}

function renderEpisodes(episodes) {
  const list = $("#episode-list");
  list.innerHTML = "";
  for (const ep of episodes) {
    const li = document.createElement("li");
    li.className = "episode";
    li.innerHTML = `
      <strong>${ep.visitor_persona_id}</strong>
      → ${ep.offer.topic}/${ep.offer.style}/${ep.offer.drink}
      → <em>${ep.outcome}</em>
    `;
    list.appendChild(li);
  }
}

function renderRules(rules) {
  const list = $("#rule-list");
  list.innerHTML = "";
  for (const r of rules) {
    const li = document.createElement("li");
    li.className = "rule" + (r.status === "under_revision" ? " -at-risk" : "");
    const slots = r.slots
      .map((s) => `${s.name}=${s.value ?? "<" + s.kind + ">"}`)
      .join(", ");
    li.innerHTML = `<strong>${r.id}</strong> <span>${slots}</span>`;
    list.appendChild(li);
  }
}

function renderRevision(rev) {
  const panel = $("#reflection-console");
  if (!rev) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }
  panel.classList.remove("hidden");
  panel.innerHTML = `
    <h3>Reflection · ${rev.rule_id}</h3>
    <pre id="reasoning-stream">${rev.llm_reasoning || ""}</pre>
  `;
  // TODO(phase2): subscribe to /reflections/stream/{rev.id} via EventSource.
}

async function tick() {
  try {
    const s = await getState();
    renderClock(s.clock);
    renderEpisodes(s.recent_episodes);
    renderRules(s.rules);
    renderRevision(s.active_revision);
  } catch (err) {
    console.warn(err);
  }
}

async function post(path, body) {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.ok;
}

$("#btn-bubble-pops").addEventListener("click", () =>
  post("/simulator/drift/ai_bubble_pops"),
);
$("#btn-new-segment").addEventListener("click", () =>
  post("/simulator/inject_persona", { persona_id: "persona_vc_investor" }),
);
$("#btn-expert-view").addEventListener("click", () =>
  document.body.classList.toggle("expert-view"),
);

setInterval(tick, POLL_MS);
tick();
