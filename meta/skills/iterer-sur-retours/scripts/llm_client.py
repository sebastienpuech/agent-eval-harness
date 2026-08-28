#!/usr/bin/env python3
"""llm_client.py -- appel LLM via forfait Max (Claude Agent SDK, OAuth). Coût runtime = 0.

RÈGLE (comme le muscle) : tous les appels passent par `claude_agent_sdk.query()`
(auth OAuth `claude login`). AUCUN pay-per-token, aucun `import anthropic`. On retire
ANTHROPIC_API_KEY de l'env le temps de l'appel (sinon le CLI bascule en auth par clé facturée ->
"error result: success"). Self-contained. Client de completion pur : `complete_sync(system, user) -> str`.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import random
import time

DEFAULT_MODEL = "claude-opus-4-8"

_TRANSIENT = ("error result: success", "overloaded", "rate limit", "rate_limit", "529", "503", "500 ")
_API_AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def _is_transient(err: Exception) -> bool:
    m = str(err).lower()
    return any(t in m for t in _TRANSIENT)


@contextlib.contextmanager
def _force_oauth_max_env():
    """Retire les clés d'auth API le temps de l'appel -> force le forfait Max OAuth."""
    saved = {k: os.environ.pop(k) for k in _API_AUTH_VARS if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


async def _complete_async(system: str, user: str, model: str, max_turns: int = 8) -> str:
    from claude_agent_sdk import ClaudeAgentOptions, query

    full = (f"INSTRUCTIONS SYSTÈME (respecte-les strictement) :\n{system}\n\n"
            f"---\n\nMESSAGE UTILISATEUR :\n{user}")
    max_retries, base_delay = 5, 3.0
    with _force_oauth_max_env():
        for attempt in range(1, max_retries + 1):
            try:
                result_text = ""
                parts: list[str] = []
                async for message in query(
                    prompt=full,
                    options=ClaudeAgentOptions(model=model, system_prompt=system,
                                               allowed_tools=[], max_turns=max_turns),
                ):
                    if type(message).__name__ == "AssistantMessage":
                        content = getattr(message, "content", None)
                        if isinstance(content, str):
                            parts.append(content)
                        elif isinstance(content, list):
                            for block in content:
                                if hasattr(block, "text"):
                                    parts.append(block.text)
                    elif hasattr(message, "result") and message.result:
                        result_text = message.result
                joined = "".join(parts)
                if len(joined) > len(result_text or ""):
                    result_text = joined
                if not result_text:
                    raise RuntimeError("réponse vide (vérifier 'claude login' + modèle)")
                return result_text
            except Exception as e:  # noqa: BLE001
                if _is_transient(e) and attempt < max_retries:
                    delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
                    delay += random.uniform(0, delay * 0.25)
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"Agent SDK a échoué après {attempt} tentative(s) : {e}. "
                    "Cause probable : rate limit/surcharge (429/529) ou OAuth (claude login). "
                    "NE PAS fallback sur l'API Anthropic."
                ) from e


class AgentSDKClient:
    """Client de completion forfait Max. `complete_sync(system, user) -> str`."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def complete_sync(self, system: str, user: str, model: str | None = None) -> str:
        return asyncio.run(_complete_async(system, user, model or self.model))


if __name__ == "__main__":
    import sys
    print(repr(AgentSDKClient().complete_sync("Tu réponds en un mot.", "Dis 'pong'.")))
    sys.exit(0)
