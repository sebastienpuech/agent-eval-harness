#!/usr/bin/env python3
"""notify.py -- rendu 4 blocs + transport Telegram (mockable) + lint PII avant tout push.

Confidentialite (regle de fer 5) : AUCUN verbatim de session sur Telegram. `lint_pii` est une ceinture
de securite fail-closed AVANT l'envoi (gate E4). Le transport est abstrait -> `MockTransport` pour le
golden, `TelegramTransport` en prod (import python-telegram-bot paresseux).
"""
from __future__ import annotations

import re

# Motifs PII/verbatim genereux (fail-closed) : emails, URLs, telephones.
_PII_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),         # email
    re.compile(r"https?://\S+"),                      # URL
    re.compile(r"\+?\d[\d .()-]{7,}\d"),              # telephone
]


def render_4_blocs(proposition: dict, run_id: str | None = None) -> str:
    """4 blocs QUOI/POURQUOI/DELTA/VALIDER + run_id (data_model §3). 0 verbatim (garanti amont)."""
    rid = run_id or proposition.get("run_id", "?")
    skill = proposition.get("skill", "?")
    return (f"🔧 {skill} — proposition {rid}\n"
            f"QUOI : {proposition.get('quoi', '').strip()}\n"
            f"POURQUOI : {proposition.get('pourquoi', '').strip()}\n"
            f"DELTA : {proposition.get('delta', '').strip()}\n"
            f"VALIDER : « oui {rid} » (ou reponds a ce message) / « non <raison> ».")


def lint_pii(text: str, denylist: tuple[str, ...] = ()) -> list[str]:
    """Retourne la liste des hits PII/verbatim. Vide = OK pour push. Fail-closed en amont."""
    hits = []
    for pat in _PII_PATTERNS:
        hits += [f"pii:{m.group(0)}" for m in pat.finditer(text)]
    low = text.lower()
    hits += [f"denylist:{w}" for w in denylist if w.lower() in low]
    return hits


class MockTransport:
    """Transport de test : enregistre les messages, ne parle a personne."""

    def __init__(self):
        self.sent: list[str] = []

    def send(self, text: str) -> int:
        self.sent.append(text)
        return len(self.sent)  # faux message_id


class TelegramTransport:  # pragma: no cover (reseau, cable S6 ; ptb non installe en CI)
    """Transport reel python-telegram-bot. Token dedie, chat_id whiteliste en dur (instance unique)."""

    def __init__(self, token: str, chat_id: int):
        from telegram import Bot  # import paresseux : le golden n'a pas besoin de ptb
        self._bot = Bot(token=token)
        self._chat_id = chat_id

    def send(self, text: str) -> int:
        import asyncio
        msg = asyncio.get_event_loop().run_until_complete(
            self._bot.send_message(chat_id=self._chat_id, text=text))
        return msg.message_id


def push(proposition: dict, transport, run_id: str | None = None,
         denylist: tuple[str, ...] = ()) -> int:
    """Rend + LINT (fail-closed) + envoie. Retourne le message_id. Leve si PII detectee (0 envoi)."""
    text = render_4_blocs(proposition, run_id)
    hits = lint_pii(text, denylist)
    if hits:
        raise ValueError(f"push refuse (PII/verbatim detecte) : {hits}")
    return transport.send(text)
