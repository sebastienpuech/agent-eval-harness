#!/usr/bin/env python3
"""adapt_chat.py -- adaptateur 'chat-transcript' : une conversation -> candidats FeedbackItem.

4e format d'entree (apres tracker-HTML, jsonl-header-prose, tags). Prend un bundle de session
collecte par collect_sessions.py (tours user/assistant) et isole les CANDIDATS retour : un tour
USER qui SUIT un tour ASSISTANT (= reaction a une sortie du skill).

Le tri fin (est-ce un VRAI retour correctif ? de quel type ?) est le travail du classificateur
(LLM, agents/classificateur.md) : cet adaptateur fournit les candidats + le contexte, il ne juge pas.

CONFIDENTIALITE : les candidats restent en zone JIT (.iter/, gitignore). Le `resume` provisoire
est une ligne courte tronquee ; la neutralisation finale (sans PII) est faite par le classificateur
avant toute persistance en memoire (allowlist).

CLI :
  python adapt_chat.py .iter/collected/skill-jugement_01.json   # metadonnees seulement
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
EXCERPT = 100  # longueur max du resume provisoire (1 ligne)


def adapt_chat(bundle: dict) -> list[dict]:
    """Bundle {turns:[{role,text,ts}]} -> candidats FeedbackItem (format chat-transcript).
    Un tour user qui suit un tour assistant = 1 candidat retour."""
    turns = bundle.get("turns", [])
    sid = Path(bundle.get("session_file", "session")).stem[:8]
    items = []
    prev_assistant = False
    for i, t in enumerate(turns):
        if t["role"] == "assistant":
            prev_assistant = True
            continue
        if t["role"] == "user" and prev_assistant:
            excerpt = " ".join(t["text"].split())[:EXCERPT]
            items.append({
                "id": f"chat-{sid}-{i:03d}",
                "source_ref": f"{sid}#turn{i}",
                "resume": excerpt,          # provisoire, neutralise par le classificateur
                "format_origine": "chat-transcript",
                "_a_neutraliser": True,
            })
            prev_assistant = False
    return items


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: adapt_chat.py <bundle.json>")
        return 1
    bundle = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    items = adapt_chat(bundle)
    # Metadonnees seulement (pas de PII a l'ecran).
    print(f"session {Path(args[0]).name} ({bundle.get('date')}) : "
          f"{bundle.get('n_turns')} tours -> {len(items)} candidat(s) retour")
    print("  (tour user apres tour assistant = reaction a une sortie du skill)")
    print("  -> a passer au classificateur (fork + 4 types + neutralisation sans-PII).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
