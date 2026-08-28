#!/usr/bin/env python3
"""verify_citations.py -- ancrage des preuves d'un diagnosis (patch HARN-005).

Les resumes sont produits par l'extracteur (brut jete). « Citation ancree » = substring-match
TRIVIAL dans un resume auto-produit serait une preuve fantoche. On durcit : une preuve est valide
SSI les TROIS conditions tiennent :
  1. `citation` est un substring EXACT du `resume` du Rate de ce `session_id` ;
  2. `session_id` existe dans l'index (index.json) ;
  3. le Rate porte un `signal` du lexique (references/failure_signals.md).
Un failure_mode dont UNE preuve echoue est REJETE (il ne passe pas au rewriter).
G3 exige `ratio_ancrees == 1.0`.

CLI :
  python verify_citations.py --self-test   # diagnosis_valid (1.0) vs diagnosis_invalide (<1.0)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import extractor  # meme dossier lib/

SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = SKILL_ROOT / "evals" / "fixtures"

LEXIQUE = {"reformulation_manuelle", "refais", "bof_explicite", "abandon", "tag_rejete"}
GRAVITES = {"mineur", "majeur", "critique"}

# Specificite minimale d'une citation (patch red-team #2) : sans plancher, un substring trivial
# ("l'", 2 car.) ancre n'importe quoi. On exige une citation substantielle. NB : en prod, le
# `resume` est un resume LLM du raté REEL (pas un template fige de extractor.RESUME_TEMPLATES) ->
# l'ancrage compare alors a du contenu observe, pas a une chaine publique regenerable.
MIN_CITATION_LEN = 15
MIN_CITATION_WORDS = 3


def validate_schema(diagnosis: dict) -> list[str]:
    """Violations de schema (data_model 3). Vide = conforme."""
    problems = []
    payload = diagnosis.get("payload", {})
    if "skill" not in payload:
        problems.append("payload.skill manquant")
    fms = payload.get("failure_modes")
    if not isinstance(fms, list) or not fms:
        problems.append("failure_modes vide ou absent")
        return problems
    for i, fm in enumerate(fms):
        for f in ("nom", "gravite", "preuve", "frequence"):
            if f not in fm:
                problems.append(f"failure_modes[{i}].{f} manquant")
        if fm.get("gravite") not in GRAVITES:
            problems.append(f"failure_modes[{i}].gravite invalide ({fm.get('gravite')})")
        if not isinstance(fm.get("frequence"), int):
            problems.append(f"failure_modes[{i}].frequence non entier")
    return problems


def _preuve_ancree(preuve: dict, rates_by_sid: dict, index: dict) -> bool:
    sid = preuve.get("session_id")
    cit = preuve.get("citation", "")
    rate = rates_by_sid.get(sid)
    if not (cit and len(cit) >= MIN_CITATION_LEN and len(cit.split()) >= MIN_CITATION_WORDS):
        return False  # citation triviale (substring court) -> non ancrante
    return bool(rate and sid in index and rate.get("signal") in LEXIQUE
                and cit in rate.get("resume", ""))


def verify_diagnosis(diagnosis: dict, rates: list[dict], index: dict) -> dict:
    """Retourne {n_failure_modes, n_valides, ratio_ancrees, rejetes[], schema_problems[]}."""
    schema_problems = validate_schema(diagnosis)
    rates_by_sid = {r["session_id"]: r for r in rates}
    fms = diagnosis.get("payload", {}).get("failure_modes", [])
    valides, rejetes = [], []
    for fm in fms:
        preuves = fm.get("preuve", [])
        ancre = bool(preuves) and all(_preuve_ancree(p, rates_by_sid, index) for p in preuves)
        (valides if ancre else rejetes).append(fm.get("nom"))
    ratio = round(len(valides) / len(fms), 4) if fms else None
    return {"n_failure_modes": len(fms), "n_valides": len(valides),
            "ratio_ancrees": ratio, "rejetes": rejetes, "schema_problems": schema_problems}


def _self_test() -> int:
    ok = True
    res = extractor.extract_fixtures()
    rates, index = res["rates"], res["index"]

    valid = json.loads((FIXTURES / "diagnosis_valid.json").read_text(encoding="utf-8"))
    rv = verify_diagnosis(valid, rates, index)
    print(f"valide    -> ratio={rv['ratio_ancrees']} rejetes={rv['rejetes']} schema={rv['schema_problems']}")
    try:
        assert rv["ratio_ancrees"] == 1.0, "diagnosis_valid doit avoir 100% de citations ancrees"
        assert not rv["schema_problems"], rv["schema_problems"]
        print("  [OK] diagnosis_valid : ratio 1.0, schema conforme")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    invalide = json.loads((FIXTURES / "diagnosis_invalide.json").read_text(encoding="utf-8"))
    ri = verify_diagnosis(invalide, rates, index)
    print(f"invalide  -> ratio={ri['ratio_ancrees']} rejetes={ri['rejetes']}")
    try:
        assert ri["ratio_ancrees"] < 1.0, "diagnosis_invalide doit tomber sous 1.0"
        assert "reponses proposees systematiquement trop longues (invente)" in ri["rejetes"], ri["rejetes"]
        print("  [OK] diagnosis_invalide : citation inventee -> failure_mode rejete")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
    sys.exit(0)
