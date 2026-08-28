#!/usr/bin/env python3
"""normalize_proposal.py -- 3 adaptateurs d'entree -> 1 PropositionUnifiee (dossier canonique).

Les 3 branches ont des sorties heterogenes (archi §2.4ter, data_model §1) :
  - jugement (`patch_jugement_iterer`)  : iterer produit un PATCH (principe+exemple), PAS un fichier
    complet -> on APPLIQUE (append) le patch au SKILL.md live -> candidate/SKILL.md + diff ;
  - prose (`patch_prose_muscle`)        : le muscle produit DEJA candidate/SKILL.md + diff -> tel quel ;
  - mecanique (`patch_mecanique`)       : V1.1 (hors V1).

Dossier canonique :
  proposals/<skill>/<date>/ { proposition.json, proposition.diff, candidate/SKILL.md, verdict.json }
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

MAX_BLOC = 400  # 4 blocs <= 400 car, 0 verbatim (data_model §1)


def _unified_diff(original: str, candidate: str) -> str:
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True), candidate.splitlines(keepends=True),
        fromfile="live", tofile="candidate"))


def apply_jugement_patch(original: str, patch: dict) -> str:
    """APPLIQUE un patch jugement (principe + exemple contraste) en append au SKILL.md live.
    Ancre append-only : jamais de suppression. Le patch = {titre?, principe, exemple_contraste}."""
    titre = patch.get("titre", "Principe (issu d'un retour mesure)")
    principe = patch.get("principe", "").strip()
    exemple = patch.get("exemple_contraste", "").strip()
    bloc = f"\n\n## {titre}\n{principe}\n"
    if exemple:
        bloc += f"\nExemple : {exemple}\n"
    return original.rstrip() + bloc


def normalize(remede: str, *, skill: str, date: str, run_id: str, proposals_root: Path,
              quoi: str, pourquoi: str, delta: str, verdict: dict,
              live_path: str | Path | None = None, patch: dict | None = None,
              candidate_md: str | None = None, diff_text: str | None = None) -> Path:
    """Produit le dossier canonique. Retourne le chemin de proposition.json."""
    dest = Path(proposals_root) / skill / date
    (dest / "candidate").mkdir(parents=True, exist_ok=True)

    if remede == "patch_jugement_iterer":
        if live_path is None or patch is None:
            raise ValueError("jugement : live_path + patch requis (le patch iterer n'est pas complet)")
        original = Path(live_path).read_text(encoding="utf-8")
        candidate = apply_jugement_patch(original, patch)
        diff = _unified_diff(original, candidate)
    elif remede == "patch_prose_muscle":
        if candidate_md is None:
            raise ValueError("prose : candidate_md complet requis (produit par le muscle)")
        candidate = candidate_md
        diff = diff_text if diff_text is not None else ""
    elif remede == "patch_mecanique":
        raise NotImplementedError("branche mecanique = V1.1 (hors V1)")
    else:
        raise ValueError(f"remede inconnu : {remede!r}")

    (dest / "candidate" / "SKILL.md").write_text(candidate, encoding="utf-8")
    # candidate.md a plat = format lu par apply_proposal du muscle (seul ecrivain live, S4).
    (dest / "candidate.md").write_text(candidate, encoding="utf-8")
    (dest / "proposition.diff").write_text(diff, encoding="utf-8")
    (dest / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")

    proposition = {
        "skill": skill, "date": date, "run_id": run_id, "remede": remede,
        "quoi": quoi[:MAX_BLOC], "pourquoi": pourquoi[:MAX_BLOC], "delta": delta[:MAX_BLOC],
        "telegram_message_id": None, "etat": "en_attente",
    }
    prop_path = dest / "proposition.json"
    prop_path.write_text(json.dumps(proposition, ensure_ascii=False, indent=2), encoding="utf-8")
    return prop_path
