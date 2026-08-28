#!/usr/bin/env python3
"""apply_live.py -- SEULE écriture live, GATÉE (structurel) puis commit + push.

Flux « oui » : lit l'avant -> gate structurel (apply_gate) sur (avant, candidate) AVANT d'écrire ->
si rouge : rien écrit, rien commité (refus) ; si vert : écrit le candidate sur le live -> commit ->
push (optionnel). Retourne un rapport visible (checks + diff ajouté).
"""
from __future__ import annotations

from pathlib import Path

import apply_gate


def apply_with_gate(skill: str, date: str, *, proposals_root, live_path, git,
                    muscle_import=None, push: bool = True) -> dict:
    d = Path(proposals_root) / skill / date
    candidate = d / "candidate.md"
    if not candidate.exists():
        return {"action": "erreur", "ok": False, "raison": f"candidate introuvable : {candidate}"}
    live = Path(live_path)
    before = live.read_text(encoding="utf-8")
    after = candidate.read_text(encoding="utf-8")

    gate = apply_gate.check(before, after, muscle_import)
    if not gate["ok"]:
        rouges = [c["name"] for c in gate["checks"] if not c["ok"]]
        return {"action": "refuse-gate", "ok": False, "gate": gate, "raison_courte": ", ".join(rouges)}

    live.write_text(after, encoding="utf-8")               # SEULE écriture live
    commit = git.commit_file(live, f"[{skill}] apply proposal {date} (valide par l'utilisateur)")
    pushed = None
    if push:
        try:
            pushed = git.push()
        except Exception as e:                              # commit fait, push a échoué -> on le dit
            pushed = f"ECHEC push : {e}"
    added = after[len(before):].strip()
    return {"action": "applied", "ok": True, "gate": gate, "commit": commit,
            "pushed": pushed, "diff_added": added}
