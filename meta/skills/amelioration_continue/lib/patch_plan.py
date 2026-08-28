#!/usr/bin/env python3
"""patch_plan.py -- rigueur PROPORTIONNELLE : un gros patch déclenche une revue renforcée (plan).

Un principe de 1500 caractères ne se valide pas comme une règle de 2 lignes. Au-delà d'un seuil de
taille, la proposition porte un `revue_renforcee=true` + un PLAN structuré (résumé / ce que ça
modifie+pourquoi / risques / décomposition) pour que l'humain valide la STRUCTURE, pas le blob brut.

Mesure = déterministe (0 LLM). Génération du plan : `client` injectable (LLM en prod) ; sans client,
fallback déterministe (taille + texte ajouté + garde-fous génériques) -> testable.
"""
from __future__ import annotations

import json
import re

BIG_CHARS = 800          # au-delà : gros patch
BIG_SECTIONS = 1         # > 1 section ajoutée : gros patch


def _added_text(before: str, after: str) -> str:
    common = before.rstrip()
    return after[len(common):].strip() if after.startswith(common) else after


def measure(before: str, after: str) -> dict:
    added = _added_text(before, after)
    return {"chars_added": len(added),
            "sections_added": sum(1 for l in added.splitlines() if l.strip().startswith("## ")),
            "added_text": added}


def needs_plan(before: str, after: str, big_chars: int = BIG_CHARS, big_sections: int = BIG_SECTIONS) -> bool:
    m = measure(before, after)
    return m["chars_added"] > big_chars or m["sections_added"] > big_sections


def build_plan(before: str, after: str, client=None) -> dict:
    """Retourne le plan de revue. client=None -> fallback déterministe ; sinon LLM structure."""
    m = measure(before, after)
    base = {"revue_renforcee": True, "chars_added": m["chars_added"],
            "sections_added": m["sections_added"], "texte_ajoute": m["added_text"][:2500]}
    if client is None:
        return {**base,
                "resume": f"Gros patch : {m['chars_added']} caractères, {m['sections_added']} section(s).",
                "modifie_pourquoi": "(résumé LLM non généré — mode déterministe)",
                "risques": "Revue renforcée : lire l'intégralité du texte ajouté avant d'appliquer.",
                "decomposition": "Envisager de scinder en patchs plus petits si plusieurs idées."}
    system = ("Tu produis un PLAN DE REVUE d'un patch append-only sur un SKILL.md, pour aider un humain "
              "à décider. Réponds UNIQUEMENT en JSON : {\"resume\": str, \"modifie_pourquoi\": str, "
              "\"risques\": str, \"decomposition\": str}.")
    txt = client.complete_sync(system, "Texte ajouté au SKILL.md :\n" + m["added_text"][:3000])
    fm = re.search(r"\{.*\}", txt, re.DOTALL)
    data = json.loads(fm.group(0)) if fm else {}
    return {**base, **{k: data.get(k, "") for k in ("resume", "modifie_pourquoi", "risques", "decomposition")}}
