# EDRA — Implementation Task

**Audience**: AI coding agent (Cursor / Claude Code / Cline)
**Goal**: Build a runnable demo + research artifact for **EDRA** (Experience-Driven Rule Adaptation), an independent research prototype investigating online rule induction and revision in personalized outreach agents. To be deployed at a research-conference booth and reused as the basis for SIGIR / ACM Multimedia submissions.
**Time budget**: ~2 working weeks for a single developer + AI agent.
**Target platform**: Single laptop, 1920×1080 fixed display, optional projector. Offline-capable in synthetic mode.

---

## 0. Read this first

Before generating any code, read this entire document. At every step you MUST:

1. Stay faithful to the data contracts in §4.
2. Prefer deterministic / seedable behaviour over LLM calls. LLM is used only where explicitly marked in §7.
3. Resist scope creep. Implement Phase 1 fully before touching Phase 2.
4. Keep the visual output aligned with the attached mockup (`edra_pitch_mockup.html`). The visual aesthetic is a Japanese-style **visual novel**, not a dashboard.
5. Keep the architecture to **two layers**: backend (Python, FastAPI) and frontend (HTML/JS). All orchestration is asyncio inside FastAPI. No external schedulers (no n8n, no Celery).
6. **EDRA is an independent system.** It is not a wrapper, plugin, or layer over any third-party product. External services (e.g. LinkedIn data providers) are accessed only through the abstract `ProfileSource` interface defined in §4.1. Implementation choices for those external services are swappable and not part of EDRA's scientific contribution.

---

## 1. Project overview

### 1.1 Scientific motivation

LLM-based agents that conduct personalized outreach face a fundamental problem: the strategies that work today stop working tomorrow. Audience preferences shift, platform algorithms change, what was a "warm" framing six months ago reads as cliché now. State-of-the-art systems compile their outreach rules manually — engineers tune system prompts based on intuition and aggregated metrics, with months of feedback lag. There is no principled mechanism for an outreach agent to *induce* its own rules from past episodes and *revise* them when those rules degrade.

EDRA proposes one. It is a research prototype that:

1. **Stores episodes** of past outreach attempts as structured records (profile snapshot, action taken, outcome).
2. **Clusters episodes** in embedding space to identify recurring contact archetypes.
3. **Induces hybrid rules** (à la MetaFlowLLM) when a cluster shows consistent successful patterns.
4. **Monitors consistency** — re-evaluates each rule against newly arriving episodes; emits a `revision_needed` signal when consistency drops below threshold.
5. **Reflectively revises** rules via LLM when contradictory evidence accumulates.
6. **Spawns specialist agents** when uncovered behavioural clusters form (Agent Factory).

The scientific claim is that EDRA reduces drift-recovery time for outreach strategies from weeks-of-manual-iteration to a single short feedback loop, while remaining interpretable (every action is traceable to a rule, every rule traceable to its inducing episodes).

EDRA draws on three lines of prior work, identified in the doctoral proposal: TRAD's step-wise thought retrieval and temporal alignment for episodic memory; MetaFlowLLM's hybrid (static + dynamic) rule structures induced from clustered trajectories; NeSyPR's neuro-symbolic procedural memory and contrastive feedback for rule adaptation. EDRA's contribution is the integration of these into a single closed loop with online rule revision — a capability none of the three offers individually.

EDRA is a standalone scientific artifact. It defines its own interfaces, vocabulary, and evaluation methodology. It is not coupled to any third-party agent, pipeline, or product.

### 1.2 Demo framing

The booth demonstration of EDRA is dramatized as a **research-collaboration pitch scenario**. A booth visitor either pastes their LinkedIn URL or selects a synthetic archetype. The system fetches their profile, classifies them into the existing cluster space, applies any active rule for that cluster (or improvises if none applies), and conducts a multi-turn dialogue attempting to interest the visitor in a research collaboration. The visitor's interest level is tracked on a gauge from −5 to +5; reaching either extreme ends the session.

The agent's persona for the booth demo is presented as a research-liaison representing **DEFY.group** (the conference partner). This is purely a narrative wrapper — like a researcher introducing themselves as "from MIT". DEFY is not a technical dependency; it is the brand identity used in outreach copy. `BRAND_CONFIG` parameterises this; the same EDRA can be re-pointed at any other identity.

### 1.3 What the booth visitor sees

A full-screen visual-novel scene styled in DEFY brand language (see `edra_pitch_mockup.html` and §10):

- **Centre**: a monochrome editorial portrait illustration — the EDRA agent — half-body, with a single small red brand accent. Externally composited PNG, swapped per emotion. Half-body, occupying the visual focus of the screen.
- **Background**: a dark charcoal lounge with subtle monochrome cream haze suggesting windows, faint mullion silhouettes, no warm color casts, no neon accents. Atmospheric but editorial, not cinematic.
- **Lower third**: a VN-style dialogue textbox with a red top rule, a speaker name plate in italic Bodoni, an internal-thought line revealing which rule fired, and the spoken line in display serif. A solid red square indicates "click to continue".
- **Bottom**: a full-width segmented Interest gauge spanning from −5 to +5, with the current value floating above the active region in heavy Bodoni numerals.
- **Brand corners**: a solid red 24×24px square in the upper-left as the DEFY brand mark; an italic Bodoni "EDRA" wordmark in the upper-right.
- **Edges**: three nearly-invisible hover-handles (top, left, right) that slide out hidden panels on mouse-over — masthead with operator controls (top), profile detail (right), rulebook + reflection console (left). The default state shows none of these — only the scene.
- **Operator controls** (in the hidden top panel): `💥 AI Bubble Pops` (scripted drift), `👤+ New Segment` (inject previously-unseen archetype, triggers Agent Factory), `⚙ Expert View` (reveal/hide internal-thought lines).

### 1.4 Two operating modes

**Synthetic mode (default, fully offline).** Visitors are sampled from a seeded pool of archetypes with hand-authored preference functions. Used for the scripted scenario, unit tests, and as fallback when no internet is available.

**Live mode (toggleable).** A booth visitor pastes a LinkedIn URL. The system fetches their profile via the configured `ProfileSource` implementation, generates an archetype on the fly, classifies them, and runs a real session. Live profiles are purged from disk at session end — only the anonymised archetype embedding persists.

---

## 2. Architecture — two layers only

### Layer 1 — Backend (Python, FastAPI)

All state, logic, and LLM calls. REST + one SSE endpoint. No UI.

**Components** under `backend/`:

- `memory/` — Episode store. SQLite via SQLAlchemy. Tables: `episodes`, `profiles`, `clusters`, `rules`, `revisions`, `agents`.
- `profile_source/` — Abstract `ProfileSource` protocol + concrete implementations. See §4.1 for the protocol and §3 for shipped implementations.
- `clustering/` — HDBSCAN over embedding vectors (sentence-transformers `all-MiniLM-L6-v2`). Re-cluster every N new episodes (N=3, configurable).
- `induction/` — Rule induction. When a cluster reaches `n_min=5` episodes with `success_ratio >= θ_induce=0.6`, calls LLM with the induction prompt, parses output into a `Rule`.
- `pitch/` — Generates the next dialogue turn given (profile, applicable rule or null, dialogue history). Static rules apply without LLM call. Hybrid rules with dynamic slots → LLM. No applicable rule → improvises via LLM with cluster's recent episodes as few-shot.
- `simulator/` — Visitor simulator for synthetic mode. **Deterministic, seedable**. Given an archetype → samples a perturbed instance → given a pitch in dialogue → returns the visitor's reaction (interest delta + button-choice probabilities) by lookup in a hand-authored preference function. **Never an LLM**.
- `monitor/` — Consistency-score computation. On every new episode, recomputes CS for affected rules. Emits `revision_needed` event when below threshold.
- `reflection/` — Rule-revision via LLM. SSE-streamed. Returns proposal; UI accepts / rejects / edits.
- `factory/` — Agent Factory. Detects clusters not covered by any active rule. Spawns specialist agent stubs.
- `orchestrator/` — Three asyncio loops (tick / consistency / factory) + one reactive hook (`on_new_episode`). See §6.
- `llm/` — Unified Ollama / Anthropic client. Prompts in `llm/prompts/`.

### Layer 2 — Frontend (single-page HTML+JS)

Plain HTML, vanilla JS, no build step. Polls `GET /state` every 1000ms. Subscribes to SSE for active reflection. Renders the VN scene per the mockup.

---

## 3. Tech stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy + SQLite, `sentence-transformers`, `hdbscan`, `numpy`, `scikit-learn`, `httpx`, `sse-starlette`, `pydantic`.
- **Frontend**: plain HTML/CSS/JS, Google Fonts (`Bodoni Moda`, `Inter`, `IBM Plex Mono`). No build step. See §10 for full visual specification.
- **LLM**: `LLM_MODE={local|remote}`. Default `local` (Ollama on `:11434`, model `llama3.1:8b-instruct` or `qwen2.5:7b-instruct`). Remote uses Anthropic API for dev only.
- **Profile sources** (Layer 1 plugins, see §4.1): two implementations ship by default —
  - `SyntheticProfileSource` — reads from `archetypes.yaml`. Used in synthetic mode and as fallback.
  - `LinkedInRapidAPISource` — fetches via RapidAPI when `RAPIDAPI_KEY` env var is set. Used in live mode.
  - The system makes no architectural commitment to RapidAPI specifically. Additional implementations (`GoogleScholarSource`, `GitHubProfileSource`, etc.) can be added by conforming to the `ProfileSource` protocol.
- **No external orchestrators, no n8n, no Celery, no Redis.**

---

## 4. Data models

All IDs are `<prefix>_<6-char-random>` except seeded archetypes which use stable human-readable IDs.

### 4.1 ProfileSource protocol

The boundary between EDRA and any external profile-fetching service. EDRA makes no assumptions about how a profile is sourced, only about what a profile *looks like* once delivered. This abstraction is **load-bearing for the scientific framing** — it is what makes EDRA a domain-agnostic system rather than an integration layer over a particular vendor.

```python
from typing import Protocol

class ProfileSource(Protocol):
    """Any service capable of resolving an identifier to a Profile.

    Implementations are responsible for handling their own auth, rate
    limiting, and error recovery. EDRA core is unaware of these concerns.
    """
    async def fetch(self, identifier: str) -> "Profile":
        """Resolve an identifier (URL, handle, archetype id) to a Profile.

        Raises ProfileNotFound for unrecoverable lookup failures.
        Raises ProfileSourceUnavailable for transient errors (timeouts, etc).
        """
        ...

    @property
    def source_kind(self) -> str:
        """Short stable identifier, e.g. 'linkedin_rapidapi', 'synthetic'."""
        ...
```

Two implementations ship by default: `SyntheticProfileSource` (reads `archetypes.yaml`) and `LinkedInRapidAPISource` (fetches via RapidAPI). Additional implementations are out of scope for Phase 1 but the protocol must be adhered to so future ones can be plugged in without touching EDRA core.

### 4.2 Profile

Unified schema produced by any `ProfileSource`.

```python
class Profile(BaseModel):
    id: str
    source_kind: str               # provided by the ProfileSource
    source_identifier: str         # original URL / handle / archetype id
    name: str
    role: str                      # "PhD student" | "Postdoc" | "Founder" | ...
    domain: str                    # "NLP" | "CV" | "Systems" | ...
    seniority: Literal["early", "mid", "senior"]
    headline: str                  # one-line summary
    recent_signals: list[str]      # up to 3 short text snippets — could be
                                   # posts, paper abstracts, bio excerpts.
                                   # Source-agnostic: "snippets of recent
                                   # written output by this person."
    archetype_summary: str         # one paragraph; used for embedding
    embedding: list[float] | None  # 384-dim, computed lazily
    fetched_at: datetime
    ttl_seconds: int               # how long this profile is allowed to
                                   # be cached. Live profiles: 3600.
                                   # Synthetic: infinite (None).
```

Note: `recent_signals` deliberately uses neutral language ("signals") rather than "posts" or "publications" — different `ProfileSource` implementations populate it differently.

### 4.3 PitchStrategy

The output of a rule application. Five orthogonal slots define the space of pitches.

```python
FRAMING = Literal["strategic-alignment", "peer-collaboration",
                  "knowledge-share", "applied-curiosity",
                  "skeptical-respect", "follow-up-comment"]
TONE = Literal["formal", "warm", "socratic", "direct", "playful"]
OPENER_TYPE = Literal["question", "reference-to-signal", "shared-context",
                      "credential-anchor", "cold"]
WORD_TARGET = Literal["short", "medium", "long"]      # ~30 / ~80 / ~120 words
ASK_SIZE = Literal["chat", "co-author", "intro", "trial", "none"]

class PitchStrategy(BaseModel):
    framing: FRAMING
    tone: TONE
    opener_type: OPENER_TYPE
    word_target: WORD_TARGET
    ask_size: ASK_SIZE
    opener_text: str | None        # filled at application time if dynamic
```

Combination space = 6 × 5 × 5 × 3 × 5 = 2250 combos. The hidden preference function selects per-archetype winners from this space.

The slot vocabulary is grounded in the dialogue-act and persuasion literature, not in any product's prompt format. It is internal to EDRA and stable across deployments.

### 4.4 Episode

```python
class DialogueStep(BaseModel):
    turn: int
    agent_thought: str             # in-parens internal monologue
    agent_reply: str               # public-facing turn
    visitor_choice: Literal["positive", "skeptical", "negative"] | None
    interest_delta: int            # -2..+2 effect on the gauge
    rule_applied: str | None

class Episode(BaseModel):
    id: str
    timestamp: datetime
    day: int                       # game-time day, 1..N
    profile_id: str
    cluster_id: str | None
    pitch_strategy: PitchStrategy
    dialogue: list[DialogueStep]
    final_interest: int            # -5..+5
    outcome: Literal["accepted", "exploring", "rejected", "abandoned"]
    summary: str                   # LLM-generated one-sentence
    summary_embedding: list[float]
    rule_applied_top: str | None   # the rule that drove most decisions
```

Episodes are multi-step. A typical session has 3–7 dialogue steps before reaching ±5 interest or being abandoned.

### 4.5 Cluster

```python
class Cluster(BaseModel):
    id: str
    label: str                     # LLM-generated, e.g. "mid-career CV researchers"
    profile_ids: list[str]
    episode_ids: list[str]
    centroid_embedding: list[float]
    size: int
    success_ratio: float           # accepted / (accepted + rejected); ignores 'exploring'
    created_at: datetime
    last_updated: datetime
```

### 4.6 Rule (MetaFlow-style hybrid)

```python
class RuleSlot(BaseModel):
    name: Literal["framing", "tone", "opener_type", "word_target", "ask_size"]
    kind: Literal["static", "dynamic"]
    value: str | None
    prompt: str | None             # only for dynamic; sub-prompt for the LLM

class Rule(BaseModel):
    id: str                        # "R.07" — human-friendly, monotonic
    cluster_id: str
    slots: list[RuleSlot]          # always 5 slots: the PitchStrategy fields
    induced_at: datetime
    induced_from_episode_ids: list[str]
    status: Literal["active", "deprecated", "under_revision"]
    deprecated_by: str | None
    cs_history: list[tuple[datetime, float]]
```

### 4.7 Revision

```python
class Revision(BaseModel):
    id: str
    rule_id: str
    triggered_at: datetime
    contradicting_episode_ids: list[str]
    llm_reasoning: str             # streamed text, accumulated
    proposed_rule: Rule
    decision: Literal["pending", "accepted", "rejected", "edited"]
    resolved_at: datetime | None
```

---

## 5. Seeded data — the soul of the demo

### 5.1 Seeded archetypes (6 default + 2 spawnable)

Hand-authored. Each has a full `Profile` plus a hidden preference function over `PitchStrategy`. Stored in `backend/data/archetypes.yaml`. Loaded by `SyntheticProfileSource`.

| id | label | role | domain | seniority |
|---|---|---|---|---|
| `arch_phd_nlp_introvert` | "depth-seeking PhD" | PhD student | NLP | early |
| `arch_postdoc_cv_ambitious` | "rising postdoc" | Postdoc | CV | mid |
| `arch_tech_founder_applied` | "applied-AI founder" | Founder | applied-AI | mid |
| `arch_senior_prof_meta` | "established prof" | Full prof | any | senior |
| `arch_industry_pm_pragmatic` | "MLOps PM" | PM | MLOps | mid |
| `arch_research_engineer_skeptic` | "skeptical engineer" | Research engineer | systems | mid |
| `arch_vc_investor` | "VC investor" | Partner | venture | senior | *(spawnable)* |
| `arch_journalist_curious` | "tech journalist" | Journalist | media | mid | *(spawnable)* |

### 5.2 Preference function

For each archetype, a function `preference(archetype, pitch_strategy, dialogue_history) → interest_delta ∈ [-2, +2]` plus terminal-acceptance thresholds. **Implement as a hand-authored Python module, not as an LLM**. Reproducibility of the demo depends on this being deterministic.

```python
# backend/simulator/preferences.py

ARCHETYPE_PREFERENCES = {
    "arch_phd_nlp_introvert": {
        "framing_affinity":    {"strategic-alignment": 0.2, "peer-collaboration": 0.9,
                                "knowledge-share": 0.95, "applied-curiosity": 0.5,
                                "skeptical-respect": 0.7, "follow-up-comment": 0.6},
        "tone_affinity":       {"formal": 0.6, "warm": 0.7, "socratic": 0.95,
                                "direct": 0.4, "playful": 0.2},
        "opener_affinity":     {"question": 0.9, "reference-to-signal": 0.85,
                                "shared-context": 0.7, "credential-anchor": 0.5,
                                "cold": 0.1},
        "word_target_affinity":{"short": 0.4, "medium": 0.85, "long": 0.6},
        "ask_size_affinity":   {"chat": 0.7, "co-author": 0.95, "intro": 0.5,
                                "trial": 0.3, "none": 0.6},
        "combo_bonuses": [
            {"if": {"framing": "knowledge-share", "tone": "socratic", "opener_type": "question"},
             "bonus": +0.4},
        ],
    },
    # ... 5 more
}

def preference(archetype_id, strategy, history) -> int:
    base = (
        0.25 * topic_affinity(archetype_id, strategy.framing) +
        0.25 * tone_affinity(archetype_id, strategy.tone) +
        0.20 * opener_affinity(archetype_id, strategy.opener_type) +
        0.15 * word_affinity(archetype_id, strategy.word_target) +
        0.15 * ask_affinity(archetype_id, strategy.ask_size)
    )
    base += combo_bonus(archetype_id, strategy)
    base -= 0.1 * len(history)   # interest fatigue
    return discretise(base)
```

The whole matrix lives in YAML for editing. Commit a unit test asserting each archetype has at least 2 distinct sweet-spot combos that no other archetype has.

### 5.3 Drift events

Two scripted drifts:

**Drift A — AI Bubble Pops**
- Triggered by button or auto at `day=3, hour=10`.
- Effect: for `arch_tech_founder_applied`, swap affinity values of `framing="applied-curiosity"` ↔ `framing="skeptical-respect"`, and `tone="playful"` ↔ `tone="direct"`.
- Expected: rules induced for tech-founders drop in CS → reflection → revision.

**Drift B — Postdoc burnout creep**
- Runs in background over 15 episodes starting `day=2, hour=14`.
- Effect: linearly interpolate `arch_postdoc_cv_ambitious` framing affinity for `"strategic-alignment"` from 0.9 → 0.4, simulating audience fatigue with corporate-speak.
- Expected: rule for postdocs degrades slowly — illustrates `θ_revise` sensitivity.

### 5.4 Visit schedule

Reproducible per `seeded_run.yaml`. ~6 visitors per game-day across 3 days. Drift A fires day-3 morning. New-segment injection is operator-driven, not in YAML.

---

## 6. Orchestration

Everything inside one FastAPI process. Three asyncio coroutines + one reactive hook.

```python
# backend/orchestrator.py

import asyncio, logging
logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, memory, profile_source, clustering, induction,
                 pitch, monitor, reflection, factory, simulator):
        self.memory = memory
        self.profile_source = profile_source
        self.clustering = clustering
        self.induction = induction
        self.pitch = pitch
        self.monitor = monitor
        self.reflection = reflection
        self.factory = factory
        self.simulator = simulator
        self.paused = False
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        self._tasks = [
            asyncio.create_task(self._tick_loop(), name="tick"),
            asyncio.create_task(self._consistency_loop(), name="consistency"),
            asyncio.create_task(self._factory_loop(), name="factory"),
        ]

    async def stop(self):
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _tick_loop(self):
        """Spawns a new synthetic visitor every 30s if no live session active."""
        while True:
            try:
                if not self.paused and not self.simulator.live_session_active:
                    await self.simulator.spawn_synthetic_visitor()
            except Exception as e:
                logger.exception("tick loop: %s", e)
            await asyncio.sleep(30)

    async def _consistency_loop(self):
        while True:
            try:
                for rule in await self.memory.active_rules():
                    cs = await self.monitor.consistency_score(rule.id)
                    if cs < 0.5 and await self.monitor.has_enough_post_episodes(rule.id, 5):
                        await self.reflection.trigger_revision(rule.id)
            except Exception as e:
                logger.exception("consistency loop: %s", e)
            await asyncio.sleep(15)

    async def _factory_loop(self):
        while True:
            try:
                result = await self.factory.evaluate()
                if result.spawn_needed:
                    await self.factory.spawn(result.uncovered_cluster_id)
            except Exception as e:
                logger.exception("factory loop: %s", e)
            await asyncio.sleep(45)

    async def on_new_episode(self, episode):
        """Called from /episodes handler after persistence."""
        if await self.memory.count_episodes() % 3 == 0:
            await self.clustering.recompute()
        for cluster in await self.clustering.eligible_for_induction():
            await self.induction.induce(cluster.id)
```

That is the entire orchestration surface.

---

## 7. LLM touchpoints

Closed list. Five and only five.

| Where | Purpose | Prompt file | Streaming | Token budget |
|---|---|---|---|---|
| `memory.generate_summary()` | 1-sentence summary of completed episode | `prompts/summary.txt` | no | 200 |
| `induction.induce_rule()` | Generate hybrid rule from cluster | `prompts/induce.txt` | no | 800 |
| `clustering.label_cluster()` | Human-readable cluster label | `prompts/cluster_label.txt` | no | 100 |
| `reflection.revise_rule()` | Propose revised rule given contradictory evidence | `prompts/reflect.txt` | **yes** | 1500 |
| `pitch.fill_dynamic_slot()` | Fill hybrid-rule dynamic slot (e.g. opener text) | `prompts/opener.txt` | no | 300 |

All prompts in `backend/llm/prompts/`. Use the EDRA internal vocabulary defined in §4.3 (`framing`, `tone`, `opener_type`, `word_target`, `ask_size`) — this vocabulary is grounded in dialogue-act and persuasion theory. Cache LLM outputs in `memory.llm_cache` keyed by `(prompt_hash, input_hash)`.

LLM cost discipline: one call per touchpoint per trigger event. No multi-turn LLM dialogues, no agentic chains. The system is auditable.

---

## 8. API contracts

JSON. Errors return `{"error": "...", "detail": "..."}`.

### Profiles & sessions

- `POST /sessions/start` — body: `{ source_kind: str, identifier: str }`. The configured `ProfileSource` resolves the identifier to a Profile. Returns `{ session_id, profile_id, classified_cluster_id, applicable_rule_id | null }`.
- `POST /sessions/{id}/turn` — body: `{ visitor_choice: "positive" | "skeptical" | "negative" }`. Returns next `DialogueStep`.
- `POST /sessions/{id}/end` — finalises, persists Episode, returns summary. Triggers `on_new_episode`.

### Episodes & clusters

- `GET /episodes?limit=20&order=desc`
- `POST /cluster/recompute`
- `GET /clusters`

### Rules & revisions

- `GET /rules?status=active`
- `POST /rules/induce?cluster_id=...`
- `GET /rules/{id}/consistency`
- `POST /rules/{id}/revise`
- `GET /reflections/stream/{revision_id}` — SSE
- `POST /revisions/{id}/decision` — body: `{ decision, edited_rule? }`

### Agents / Factory

- `GET /agents`
- `POST /factory/evaluate`
- `POST /factory/spawn`

### Simulator / drift

- `POST /simulator/pause` — body: `{ paused: bool }`
- `POST /simulator/drift/{drift_id}` — `drift_id ∈ {"ai_bubble_pops", "postdoc_burnout"}`
- `POST /simulator/inject_archetype` — body: `{ archetype_id }`

### State

- `GET /state` — single consolidated snapshot for UI:

```json
{
  "clock": {"day": 2, "time": "14:23"},
  "current_session": Session | null,
  "recent_episodes": [Episode x 20],
  "clusters_viz": [{"id", "label", "points": [[x,y]...]}],
  "rules": [Rule x N],
  "active_revision": Revision | null,
  "agents": [{id, zone_description}],
  "interest_gauge": int   // -5..+5 if a session is active
}
```

---

## 9. Demo scenario — 5-minute scripted arc

Seeded RNG = 42. Fresh start.

- **00:00–01:00** — Day 1. Empty rulebook. Three synthetic visitors. Bartender improvises (LLM-driven). Episodes accumulate.
- **01:00–02:00** — Day 2 morning. Cluster `c_phd_nlp` hits `n_min=5` with success ratio 0.8. **R.07 induced**. Next PhD-NLP visit: rule fires, gauge hits +4, accepted.
- **02:00–02:45** — Day 2 afternoon. Cluster `c_tech_founder` hits threshold. **R.12 induced**. Drift B starts in background.
- **02:45–03:30** — Day 3 morning. Operator clicks `💥 AI Bubble Pops`. Next tech-founder rejects. CS for R.12 drops. Reflection console opens. LLM streams reasoning. Operator clicks Accept. R.12 deprecated, R.13 induced.
- **03:30–04:15** — Day 3 midday. Operator clicks `👤+ New Segment`. Journalist archetype enters. No cluster matches. Improvised pitch. After 2 more journalists, cluster forms, factory fires, new agent spawned.
- **04:15–05:00** — Rest state. Six rules visible (one deprecated). Two active agents.

If nobody clicks anything, the scenario auto-runs from the seeded YAML. If a real visitor pastes a LinkedIn URL, synthetic ticks pause; live session takes over.

---

## 10. UI requirements

Source of truth: `edra_pitch_mockup.html`. The mockup is the visual ground truth — match its palette, typography, layout, spacing, and brand cues exactly. Do not improvise visual decisions; if the mockup doesn't show how something should look, ask in §15 rather than guess.

### 10.1 Visual aesthetic

**DEFY brand-aligned editorial monochrome, expressed through a visual-novel format.** The screen is a single full-bleed scene, not a dashboard. The scene contains:
- Central editorial portrait character (composited from external PNG, see §10.5)
- VN-style dialogue textbox in the lower third
- Full-width segmented interest gauge at the very bottom
- Three hover-out edge handles for hidden side panels (top, left, right)
- DEFY brand mark (solid red square) in the upper-left corner
- EDRA wordmark in the upper-right corner

The aesthetic is **late-evening editorial** — dark charcoal lounge with subtle monochrome cream haze suggesting windows, no neon, no warm color casts, no decorative gradients.

### 10.2 Brand palette — exact tokens, no others

Use these CSS variables verbatim. Do NOT introduce additional accent colors.

```css
--black:        #0A0A0A;     /* primary background */
--charcoal:     #202020;     /* secondary surfaces */
--charcoal-2:   #2c2c2c;
--rule-line:    #2e2e2e;
--rule-line-2:  #3a3a3a;

--cream:        #F3F1EC;     /* primary text */
--cream-soft:   #F9F9F7;
--cream-dim:    #c4bfb3;     /* secondary text */
--cream-faint:  #807a70;     /* tertiary text, eyebrow labels */

--red:          #CC0000;     /* DEFY Red — sole accent color */
--red-deep:     #8a0000;
--red-faint:    rgba(204, 0, 0, 0.14);
```

Distribution target: ~50% black/charcoal, ~40% cream, ~10% DEFY red. Red is reserved for: brand mark (solid square), active rule states, drift/danger states, primary call-to-action emphasis, gauge endpoints. Never use red for decorative purposes.

### 10.3 Typography — three families only

```css
--f-display:    'Bodoni Moda', 'Didot', Georgia, serif;     /* Didone — display headlines, character names, dialogue utterance */
--f-sans:       'Inter', 'Helvetica Neue', sans-serif;       /* body, choice buttons, panel content */
--f-mono:       'IBM Plex Mono', monospace;                  /* technical metadata, IDs, percentages, eyebrow labels */
```

Bodoni Moda is the *only* serif. Do not introduce Cormorant Garamond, Instrument Serif, Fraunces, or any transitional/old-style serif — they violate brand. Inter is the *only* sans. Do not introduce Archivo, Helvetica directly, or any other geometric.

### 10.4 Strict visual constraints (DEFY brand)

Forbidden everywhere in the UI:
- `border-radius` other than 0 (no rounded corners; everything rectangular)
- `box-shadow` of any kind (no drop shadows on cards, panels, buttons, character)
- `linear-gradient` / `radial-gradient` for non-atmospheric purposes (the only gradients allowed are the very subtle monochrome-cream window haze in the background; no UI element uses gradients)
- Glow effects on UI elements (no `text-shadow` for emphasis, no `filter: drop-shadow` on UI)
- Any color outside the §10.2 palette
- Decorative shapes other than the solid red square (no circles, ovals, hexagons, etc., for ornamental purposes)
- 3D effects, skeuomorphism, beveling

Required:
- All accent shapes are perfect squares (e.g. continue-marker is a 14×14 red square, not a triangle ▼; brand mark is 24×24 red square; corner cuts on portraits are red squares)
- All borders are 1px or 2px solid lines
- All transitions are linear or simple ease, no bouncy easing

### 10.5 Agent character

The central character is an externally-composited PNG, swapped via JS. Do not generate the character in code.

The illustration must follow DEFY brand:
- High-contrast monochrome (B&W) with a single small red accent (lipstick / lapel pin / collar detail — pick one and keep consistent across emotions)
- Editorial illustration style or documentary B&W photography — NOT bright anime, NOT cartoon, NOT colorful
- Half-body portrait, transparent background, 720×1080
- 6 emotion variants required: `neutral`, `pleased`, `thoughtful`, `concerned`, `confident`, `disappointed`
- Identity, outfit, lighting, framing must be identical across all six — only the expression varies

JS swaps the visible variant based on current interest gauge:
```javascript
function getEmotion(interest) {
  if (interest >= 4)  return 'confident';
  if (interest >= 1)  return 'pleased';
  if (interest === 0) return 'neutral';
  if (interest >= -2) return 'thoughtful';
  if (interest >= -4) return 'concerned';
  return 'disappointed';
}
```

PNG generation prompt and full specification are in HTML comments at the bottom of `edra_pitch_mockup.html`.

### 10.6 Behaviours

- Polls `GET /state` every 1000ms.
- Subscribes to `/reflections/stream/{id}` SSE when `active_revision` is non-null.
- Agent reply text types out character-by-character (VN typewriter effect, ~30 cps). The red square continue-marker appears when typing completes.
- Interest gauge animates smoothly (CSS transform, not stepped) when value changes.
- When session starts: visitor portrait slides into right panel; agent emotion swap is instant.
- Edge handles are minimal in resting state — barely-visible labels on a 1px cream border. On mouse-over, the corresponding panel slides in over the scene at 0.35s cubic-bezier.
- `Expert View` toggle: when off, hides the agent's italic internal-thought lines and the reflection console's `Evidence` and `LLM reasoning` sections.

### 10.7 Do NOT add

- Dark/light mode toggle (the design is dark-only by brand)
- Responsive / mobile layout (fixed 1920×1080 booth display)
- User accounts, settings, preferences pages
- Any decorative imagery beyond what's specified
- Any color, font, or shape outside §10.2 / §10.3 / §10.4 / §10.5

---

## 11. Implementation phases

### Phase 1 — Synthetic core (days 1–5)

End-to-end synthetic mode: archetypes → simulator → clustering → induction → revision → UI.

- `uvicorn backend.app:api` on `:8000`.
- Frontend served from same FastAPI app.
- `make demo` startup in <30s.
- Local Ollama only.
- Five-minute scripted scenario plays out unattended.
- Only `SyntheticProfileSource` wired; `ProfileSource` protocol defined but no live implementations yet.

### Phase 2 — Polish (days 6–10)

- Streaming reflection via SSE.
- Cluster UMAP viz, recomputed on change.
- Anime-style agent portrait integrated (initially placeholder SVG, then real illustration).
- VN textbox with typewriter effect.
- Hover-out side panels with smooth slide animation.
- Interest gauge animation polish.
- Operator buttons functional.
- Agent Factory spawn animation.
- Unit tests (preferences, clustering stability, induction eligibility, orchestrator cancel).

### Phase 3 — Live mode + booth-ready (days 11–14)

- `LinkedInRapidAPISource` implementation. Behind `LIVE_MODE=true` flag.
- Privacy: live profiles purged from disk after session end.
- Wi-Fi failure fallback: if `LinkedInRapidAPISource.fetch()` raises `ProfileSourceUnavailable`, suggest the visitor pick a synthetic archetype.
- `make booth` script: starts backend, waits for health, opens browser fullscreen.
- Reset button clears SQLite and re-seeds in <5s.
- 2-page operator cheat sheet (PDF) covering button meanings, scripted scenario timing, and live-mode fallback.

---

## 12. Non-goals

- Sending real emails or posting real LinkedIn comments. EDRA never executes an outreach action against a real person — the dialogue is a simulation. The pitch never leaves the booth.
- Persistent storage of live profile data past session end.
- Mobile / responsive.
- Multi-user concurrency.
- Authentication.
- External orchestrators (n8n, Airflow, Celery).
- Cloud deployment.
- Integration with any specific third-party agent platform, CRM, or product. EDRA is independent.
- A "score" or "win" condition.
- Showing the raw preference function on the UI.

---

## 13. File layout

```
edra/
├── backend/
│   ├── app.py
│   ├── orchestrator.py
│   ├── memory/
│   ├── profile_source/
│   │   ├── __init__.py            # ProfileSource protocol + exceptions
│   │   ├── synthetic.py           # SyntheticProfileSource
│   │   └── linkedin_rapidapi.py   # LinkedInRapidAPISource
│   ├── clustering/
│   ├── induction/
│   ├── pitch/
│   ├── simulator/
│   │   ├── preferences.py
│   │   ├── drift.py
│   │   └── schedule.py
│   ├── monitor/
│   ├── reflection/
│   ├── factory/
│   ├── llm/
│   │   ├── client.py
│   │   └── prompts/
│   │       ├── summary.txt
│   │       ├── induce.txt
│   │       ├── cluster_label.txt
│   │       ├── reflect.txt
│   │       └── opener.txt
│   ├── data/
│   │   ├── archetypes.yaml
│   │   └── seeded_run.yaml
│   └── db.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── assets/
│       ├── agent/                 # monochrome editorial portraits per emotion
│       └── visitor/               # generic line-art portraits
├── tests/
│   ├── test_preferences.py
│   ├── test_clustering.py
│   ├── test_induction.py
│   ├── test_profile_source.py     # protocol conformance tests
│   └── test_orchestrator.py
├── Makefile                       # demo / booth / reset / test
├── docker-compose.yml             # backend + ollama
├── pyproject.toml
└── README.md
```

---

## 14. Acceptance checklist

- [ ] `make demo` starts everything in <30s.
- [ ] UI matches `edra_pitch_mockup.html` layout, fonts, palette, atmosphere.
- [ ] Five-minute scenario plays out unattended on fresh state.
- [ ] `💥 AI Bubble Pops` causes CS drop → revision within 60s.
- [ ] `👤+ New Segment` causes Agent Factory spawn within 3 episodes.
- [ ] `Expert View` toggles correctly.
- [ ] No network calls leave the machine when `LLM_MODE=local LIVE_MODE=false`.
- [ ] `make reset` deterministically replays the same trajectory.
- [ ] Five LLM prompts in `prompts/`, each documented.
- [ ] Orchestrator loops survive in-loop exceptions.
- [ ] `ProfileSource` protocol is the *only* coupling point between EDRA core and external services. Verified by import-graph test (`tests/test_profile_source.py` asserts that no module under `backend/{memory,clustering,induction,pitch,monitor,reflection,factory,orchestrator}` imports anything from `backend/profile_source/linkedin_rapidapi.py`).
- [ ] In live mode, a real LinkedIn URL produces a Profile, classifies into a cluster, runs a 3-turn dialogue.
- [ ] Live profile data is purged after session end (test verifies SQLite has no PII for source_kind != "synthetic" profiles older than 1 hour).
- [ ] `pytest` passes.

---

## 15. Open questions to confirm with the author before coding

File as GitHub issues, tag the author:

1. Which Ollama model do we ship with — `llama3.1:8b-instruct` or `qwen2.5:7b-instruct`? Both ~5GB; pick one for the offline bundle.
2. Should the live-mode profile-fetch cost be capped per booth-day (e.g. max 100 fetches/day) to control spend?
3. On revision acceptance, deprecate-with-pointer or hard-delete the old rule? **Default: deprecate** for ablation studies.
4. Reset behaviour: same seed every time (default) or randomised?
5. In live mode, do we show the visitor a "take-home card" (their classified cluster + applied rule, printable / QR-share)? Adds a render step but is a powerful narrative.
6. Which `ProfileSource` implementations beyond LinkedIn are worth shipping in Phase 3+ as proof of source-agnosticism — `GoogleScholarSource`? `GitHubProfileSource`? **Default for Phase 1: only Synthetic + LinkedIn-RapidAPI**, others deferred.

Default answers above; flag the author on first PR.