#!/usr/bin/env python3
"""build_contract.py -- G2-factuel : produit le CONTRAT d'entree d'auto-improver.

FRONTIERE PAR ARTEFACT (patch ARCH-001) : ce module ECRIT 0 PATCH DE CODE du skill cible. Il
produit UNIQUEMENT `auto_improver_call.json` (registry + evals au format consomme + held-out
gele EXCLU des test_cases + regles-a-detecteur). Le patch factuel est ecrit par auto-improver.

INVARIANT anti-contournement : le held-out sanctuarise est RETIRE des evals passees au moteur
(sinon la digue anti-overfit est contournee).

STATUT : estampille par delegation.stamp() -> `HYPOTHESE_V2` tant que la cible (v2) n'a pas de
SKILL.md verifiable. Re-ouvrir le gate avant tout envoi effectif.

CLI : python build_contract.py   (lit signal/registry.yaml, ecrit .iter/auto_improver_call.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from delegation import current_status, stamp

SKILL_ROOT = Path(__file__).resolve().parent.parent
SIGNAL = SKILL_ROOT / "signal"
ITER = SKILL_ROOT / ".iter"
OUT = ITER / "auto_improver_call.json"


def build_contract(registry: dict, skill_path: str, max_iter: int = 5) -> dict:
    holdout = list(registry.get("holdout", []))
    regles = registry.get("regles", [])

    # test_cases = cas de retour SEULEMENT ; held-out EXCLU (invariant).
    retour_cases = sorted({k for r in regles for k in (r.get("attendu_par_cas") or {})})
    test_cases = [c for c in retour_cases if c not in set(holdout)]

    regles_a_detecteur = [
        {"id": r["id"], "detecteur": r.get("detecteur"),
         "attendu_par_cas": {k: v for k, v in (r.get("attendu_par_cas") or {}).items()
                             if k not in set(holdout)}}
        for r in regles if r.get("famille") == "B"
    ]

    call = {
        "skill_path": skill_path,
        "evals_file": "generated_evals.json",         # format critical_checks consomme (S2 doc)
        "test_case_ids": test_cases,                    # held-out EXCLU
        "holdout_case_ids": holdout,                    # a NE PAS mettre dans les test_cases
        "regles_a_detecteur": regles_a_detecteur,
        "max_iter": max_iter,
    }
    # Verification de l'invariant AVANT d'estampiller.
    assert not (set(call["test_case_ids"]) & set(holdout)), \
        "INVARIANT VIOLE : un cas held-out est dans les test_cases passes au moteur."
    return stamp(call)


def main() -> int:
    reg = SIGNAL / "registry.yaml"
    if not reg.exists():
        raise SystemExit("signal/registry.yaml absent -> lancer split_holdout.py d'abord.")
    registry = yaml.safe_load(reg.read_text(encoding="utf-8"))

    # 0-patch-code : instantane des fichiers du skill CIBLE avant/apres (aucun ne doit changer).
    # Ici la cible reelle est hors-repo/bloquee ; on prouve la propriete structurellement :
    # ce module n'ouvre AUCUN fichier cible en ecriture -- il n'ecrit que OUT (sous ce skill).
    call = build_contract(registry, skill_path="chemin/vers/skill-tableur-demo")
    ITER.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(call, ensure_ascii=False, indent=2), encoding="utf-8")

    assert OUT.resolve().is_relative_to(SKILL_ROOT), \
        "0-patch-code VIOLE : le seul ecrit doit etre sous le meta-skill."

    print(f"[OK] contrat produit : {OUT.relative_to(SKILL_ROOT)}")
    print(f"     delegation_status = {call['delegation_status']}")
    print(f"     test_case_ids     = {call['test_case_ids']}  (held-out EXCLU)")
    print(f"     holdout_case_ids  = {call['holdout_case_ids']}")
    print(f"     0 patch de code du skill cible ecrit (seul ecrit = {OUT.name} sous ce skill).")
    if current_status() != "VERIFIE_V2":
        print("     [!] HYPOTHESE : contrat non verifie contre un SKILL.md reel (v2 pas construit).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
