#!/usr/bin/env python3
"""feasibility.py -- checklist de faisabilite corpus (spec 0bis), AVANT de s'engager.

`iterer-sur-retours` NE nettoie NI ne reconstruit un corpus. Si un pre-requis manque, on
range le blocage comme `bloque input externe` (Scenario 3) et on STOP proprement -- pas de
pipeline de nettoyage bricole.

Checklist (spec 0bis) :
  1. corpus localise ET lisible par le runner ;
  2. >=3 cas held-out candidats jamais cites par un retour existent ;
  3. le format des cas est parsable ;
  4. le lot de retours a un format normalisable (adaptateur present, cf. normalize_feedback).

Retourne un FeasibilityReport ; la fonction BLOQUE proprement (ok=False), ne crashe pas.
CLI : exit 0 si faisable, exit 2 si bloque (input externe), exit 1 si erreur interne.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from normalize_feedback import KNOWN_FORMATS

SKILL_ROOT = Path(__file__).resolve().parent.parent
# Racine de dev (ou vivent les repos de skills). Override explicite par variable d'env ;
# sinon on remonte l'arborescence depuis ce skill. Aucun nom de repo code en dur.
import os  # noqa: E402
_ENV_ROOT = os.environ.get("ITERER_DEV_ROOT")
DEV_ROOT = (Path(_ENV_ROOT) if _ENV_ROOT and Path(_ENV_ROOT).is_dir()
            else (SKILL_ROOT.parents[3] if len(SKILL_ROOT.parents) >= 4 else SKILL_ROOT))


def _resolve(pointer: str) -> Path | None:
    """Pointeur repo-relatif (ex. 'chemin/vers/skill') -> chemin disque s'il existe."""
    cand = DEV_ROOT / pointer
    return cand if cand.exists() else None


def check_corpus_feasibility(case_path: Path) -> dict:
    case = json.loads(Path(case_path).read_text(encoding="utf-8"))
    checks: list[dict] = []

    def add(name, ok, detail):
        checks.append({"name": name, "status": "OK" if ok else "BLOCK", "detail": detail})

    # 1. corpus localise ET lisible
    pointers = case.get("repo_pointer")
    pointers = pointers if isinstance(pointers, list) else [pointers]
    corpus_ptr = case.get("retours", {}).get("corpus_pointer")
    repo_ok = all(_resolve(p) for p in pointers if p)
    corpus_present = corpus_ptr is not None and _resolve(corpus_ptr) is not None
    if case.get("corpus", {}).get("hors_repo"):
        # corpus hors repo (ex. tableur datasets) : repo lisible mais datasets a monter (JIT).
        add("corpus_localise", repo_ok,
            "repo lisible" if repo_ok else f"repo introuvable sous {DEV_ROOT}")
        if not corpus_present:
            add("corpus_lisible", False,
                "corpus HORS-REPO non monte -> fournir le chemin des datasets held-out "
                f"(candidats a monter en JIT read-only). Cherche sous : {DEV_ROOT} "
                "ou un chemin de donnees configure. Run PARTIEL degrade possible (archi 3.1).")
        else:
            add("corpus_lisible", True, f"corpus present : {corpus_ptr}")
    else:
        ok = repo_ok and (corpus_present or corpus_ptr is None)
        add("corpus_localise_lisible", ok,
            f"repo={repo_ok}, corpus_pointer={'present' if corpus_present else 'n/a'}")

    # 2. >=3 held-out candidats non-cites
    holdout_cand = case.get("corpus", {}).get("held_out_candidats", [])
    cas_cites = case.get("retours", {}).get("cas_cites", [])
    if holdout_cand:
        disjoint = not (set(holdout_cand) & set(cas_cites))
        add("held_out_candidats", len(holdout_cand) >= 3 and disjoint,
            f"{len(holdout_cand)} candidats, disjoints des cas cites={disjoint}")
    elif case.get("held_out", {}).get("min"):
        m = case["held_out"]["min"]
        add("held_out_candidats", m >= 3,
            f"held-out par compte (min={m}) ; ids enumeres en V1.1 (branche jugement)")
    else:
        add("held_out_candidats", False, "aucun held-out candidat ni min defini")

    # 3+4. format parsable / normalisable (adaptateur present)
    fmts = case.get("retours", {}).get("format_origine", [])
    fmts = fmts if isinstance(fmts, list) else [fmts]
    unknown = [f for f in fmts if f not in KNOWN_FORMATS]
    add("format_normalisable", not unknown,
        "tous les formats ont un adaptateur" if not unknown
        else f"formats sans adaptateur : {unknown} -> Scenario 3")

    ok = all(c["status"] == "OK" for c in checks)
    return {
        "case": case.get("id"),
        "ok": ok,
        "classe_si_bloque": None if ok else "bloque_input_externe",
        "checks": checks,
    }


def _print(report: dict) -> int:
    print(f"faisabilite corpus -- cas '{report['case']}'")
    print("-" * 72)
    for c in report["checks"]:
        icon = "[OK]  " if c["status"] == "OK" else "[BLOCK]"
        print(f"{icon} {c['name']:<24} {c['detail']}")
    print("-" * 72)
    if report["ok"]:
        print("=> FAISABLE.")
        return 0
    print(f"=> BLOQUE ({report['classe_si_bloque']}) : range en Scenario 3, stop propre. "
          "iterer-sur-retours ne reconstruit pas de corpus.")
    return 2


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    target = Path(args[0]) if args else SKILL_ROOT / "evals" / "cases" / "tableur.json"
    try:
        rep = check_corpus_feasibility(target)
    except Exception as e:  # noqa: BLE001 -- erreur interne distincte d'un blocage input
        print(f"ERREUR INTERNE : {e}")
        sys.exit(1)
    sys.exit(_print(rep))
