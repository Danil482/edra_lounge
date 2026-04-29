"""Unified LLM client — three modes switchable via LLM_MODE env var.

- `local`  → Ollama on localhost:11434 (booth-default, offline-capable)
- `remote` → Anthropic Messages API (dev/testing only)
- `openai` → OpenAI Chat Completions API (dev/testing only)

All providers use httpx directly per TASK.md §3. No provider SDKs.

Public surface:
    complete(prompt, *, system=None)      → str
    stream(prompt, *, system=None)        → async iterator of str tokens
    render(template_name, **fields)       → str   (loads prompts/<name>.txt)
"""

from pathlib import Path
from typing import AsyncIterator

import httpx

from backend.config import settings


PROMPTS_DIR = Path(__file__).parent / "prompts"


def render(template_name: str, **fields) -> str:
    """Load `prompts/<template_name>.txt` and substitute `{field}` placeholders."""
    path = PROMPTS_DIR / f"{template_name}.txt"
    template = path.read_text(encoding="utf-8")
    return template.format(**fields)


async def complete(prompt: str, *, system: str | None = None) -> str:
    """Non-streaming completion. Returns full response text."""
    if settings.llm_mode == "local":
        return await _ollama_complete(prompt, system)
    if settings.llm_mode == "openai":
        return await _openai_complete(prompt, system)
    return await _anthropic_complete(prompt, system)


async def stream(prompt: str, *, system: str | None = None) -> AsyncIterator[str]:
    """Token stream. Yields text chunks as they arrive."""
    if settings.llm_mode == "local":
        async for chunk in _ollama_stream(prompt, system):
            yield chunk
    elif settings.llm_mode == "openai":
        async for chunk in _openai_stream(prompt, system):
            yield chunk
    else:
        async for chunk in _anthropic_stream(prompt, system):
            yield chunk


# ── Ollama (local) ────────────────────────────────────────────────────────

async def _ollama_complete(prompt: str, system: str | None) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": _messages(prompt, system),
                "stream": False,
            },
        )
        r.raise_for_status()
        return r.json()["message"]["content"]


async def _ollama_stream(prompt: str, system: str | None) -> AsyncIterator[str]:
    import json

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": _messages(prompt, system),
                "stream": True,
            },
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
                if chunk.get("done"):
                    break


# ── Anthropic (remote) ────────────────────────────────────────────────────

async def _anthropic_complete(prompt: str, system: str | None) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=_anthropic_headers(),
            json={
                "model": settings.anthropic_model,
                "max_tokens": 2048,
                "system": system or "",
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]


async def _anthropic_stream(prompt: str, system: str | None) -> AsyncIterator[str]:
    import json

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=_anthropic_headers(),
            json={
                "model": settings.anthropic_model,
                "max_tokens": 2048,
                "system": system or "",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield delta.get("text", "")


def _anthropic_headers() -> dict[str, str]:
    return {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


# ── OpenAI (remote) ───────────────────────────────────────────────────────

async def _openai_complete(prompt: str, system: str | None) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_openai_headers(),
            json={
                "model": settings.openai_model,
                "messages": _messages(prompt, system),
                "stream": False,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _openai_stream(prompt: str, system: str | None) -> AsyncIterator[str]:
    import json

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers=_openai_headers(),
            json={
                "model": settings.openai_model,
                "messages": _messages(prompt, system),
                "stream": True,
            },
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                event = json.loads(data)
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text


def _openai_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }


def _messages(prompt: str, system: str | None) -> list[dict]:
    msgs: list[dict] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs
