"""Kimi PPT generation adapter (kimi.com web session, plan A).

Confirmed working against the live web API (2026-07-22):
  1. POST /api/chat                       -> create a chat bound to a PPT kimiplus
  2. POST /api/chat/{id}/completion/stream -> SSE stream producing the PPT outline

Pending (needs a HAR capture of one real generation in the browser):
  3. The dedicated slides service that turns the outline into a .pptx
     (task create -> template -> render -> export). Endpoint family unknown;
     isolated in `_generate_slides()` so a future change touches one function.

KIMI_WEB_KEY is the user's web JWT (Authorization: Bearer ...). It expires
(~30 days); refresh via browser devtools and update the env var.
"""
import asyncio
import json
import os

import httpx

from . import config

BASE = "https://www.kimi.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# New official "PPT 助手" (special_id=slides); fallback: legacy "Kimi x AiPPT"
KIMIPLUS_SLIDES = "cvvm7bkheutnihqi2100"
KIMIPLUS_AIPPT = "conpg18t7lagbbsfqksg"

_MOCK_DELAY = float(os.environ.get("MOCK_GEN_SECONDS", "15"))


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.KIMI_WEB_KEY}",
            "User-Agent": UA, "Content-Type": "application/json"}


async def _create_chat(client: httpx.AsyncClient, name: str, kimiplus_id: str) -> str:
    r = await client.post(f"{BASE}/api/chat", headers=_headers(), json={
        "name": name, "is_example": False,
        "born_from": "kimiplus", "kimiplus_id": kimiplus_id})
    r.raise_for_status()
    return r.json()["id"]


async def _stream_outline(client: httpx.AsyncClient, chat_id: str, prompt: str) -> str:
    """Send the user message; collect streamed text. Returns full outline text."""
    parts: list[str] = []
    async with client.stream(
            "POST", f"{BASE}/api/chat/{chat_id}/completion/stream",
            headers=_headers(),
            json={"messages": [{"role": "user", "content": prompt}]}) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except json.JSONDecodeError:
                continue
            if evt.get("event") == "cmpl":
                parts.append(evt.get("text", ""))
            elif evt.get("event") == "all_done":
                break
    return "".join(parts)


async def _generate_slides(client: httpx.AsyncClient, chat_id: str, outline: str,
                           pages: str, style: str, files: list[str]) -> dict:
    """Turn the outline into an actual .pptx via Kimi's slides service.

    NOT YET WIRED: endpoint family still being mapped (waiting on a HAR
    capture). Raise so the job is marked failed with a clear reason instead
    of silently succeeding.
    """
    raise NotImplementedError(
        "slides generation endpoint pending HAR capture; outline was produced OK")


def _build_prompt(description: str, pages: str, style: str) -> str:
    page_hint = "" if pages in ("auto", "", None) else f"，页数 {pages.replace('-', '~')} 页"
    style_hint = "经典模版" if style == "classic" else "智能布局"
    return f"帮我生成一份PPT：{description}{page_hint}。风格版本：{style_hint}。"


async def generate_ppt(description: str, pages: str, style: str, files: list[str]) -> dict:
    """Returns {"result_url": str|None, "note": str}. Raises on failure."""
    if not config.KIMI_WEB_KEY:
        await asyncio.sleep(_MOCK_DELAY)
        return {"result_url": None,
                "note": "mock mode: set KIMI_WEB_KEY to enable real generation"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30)) as client:
        chat_id = await _create_chat(client, f"ppt-site {description[:18]}",
                                     KIMIPLUS_SLIDES)
        outline = await _stream_outline(client, chat_id,
                                        _build_prompt(description, pages, style))
        # TODO(files): upload reference files via /api/file first, then attach.
        return await _generate_slides(client, chat_id, outline, pages, style, files)
