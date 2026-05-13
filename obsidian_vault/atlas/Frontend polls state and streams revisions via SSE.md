---
tags: [atlas, frontend, sse, polling, ui]
date: 2026-05-13
---

# Frontend polls state and streams revisions via SSE

The frontend is vanilla HTML/JS with no build step — `index.html` + `app.js` + `styles.css`. It is a verbatim port of the mockup `edra_pitch_mockup.html`.

## Data flow

- **Polling**: `GET /state` every 1000ms — re-renders only changed fields
- **SSE**: `/reflections/stream/{revisionId}` — receives `reasoning` chunks and `revision` JSON in real time
- **Actions**: `POST /sessions/start`, `POST /sessions/{id}/turn`, `POST /sessions/{id}/end`

## UI structure (VN scene)

- **Centre**: anime portrait (6 emotion variants: neutral/pleased/thoughtful/concerned/confident/disappointed)
- **Bottom**: VN textbox with typewriter effect (30 CPS), speaker plate "Edra"
- **Left hover panel**: rulebook (active/deprecated/revising states, 440px)
- **Right hover panel**: visitor profile + avatar (400px)
- **Top hover panel**: day statistics (110px)
- **Interest gauge**: -5 to +5 cells with color transitions
- **Three buttons**: positive / skeptical / negative choices

## Brand compliance (Defy V2.0)

No rounded corners, no gradients, no shadows. Palette: #0A0A0A (black) / #F9F9F7 (warm white) / #CC0000 (Defy Red) in 50/40/10 ratio. Fonts: Playfair Display + DM Sans. Hover panels slide with cubic-bezier easing.

## Key files

- `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`
- `frontend/edra_pitch_mockup.html` — source-of-truth mockup
