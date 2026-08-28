#!/usr/bin/env python3
"""quarantaine.py -- garde-fou S6 : 2 erreurs consécutives sur un skill -> le CRON skippe.

Circuit-breaker automatique (spec §4 / patch PRAG-002). Sans état séparé : la quarantaine est
CALCULÉE depuis `memory/interactions.jsonl` (append-only, source de vérité des passes). Règle :
si les `threshold` DERNIÈRES passes d'un skill sont toutes `statut == "erreur"`, il est en quarantaine.

Levée = **commande manuelle** (le bot `ameliore <skill>` déclenche un run MANUEL qui bypasse la
quarantaine — l'humain décide de réessayer) : s'il réussit, les 2 dernières ne sont plus toutes
"erreur" → quarantaine levée d'elle-même. Le CRON, lui, respecte la quarantaine.
"""
from __future__ import annotations

import json
from pathlib import Path

THRESHOLD = 2  # nb d'erreurs consécutives déclenchant la quarantaine


def _statuts_for_skill(interactions_path, skill: str) -> list[str]:
    p = Path(interactions_path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("skill") == skill:
            out.append(rec.get("statut"))
    return out


def is_quarantined(interactions_path, skill: str, threshold: int = THRESHOLD) -> bool:
    """True si les `threshold` dernières passes du skill sont toutes 'erreur'."""
    statuts = _statuts_for_skill(interactions_path, skill)
    if len(statuts) < threshold:
        return False
    return all(s == "erreur" for s in statuts[-threshold:])


def quarantine_reason(interactions_path, skill: str, threshold: int = THRESHOLD) -> str | None:
    if not is_quarantined(interactions_path, skill, threshold):
        return None
    return (f"{threshold} passes consécutives en erreur sur '{skill}' -> quarantaine. "
            f"Le cron skippe. Relance MANUELLE (bot: ameliore {skill}) pour lever si ça repasse.")
