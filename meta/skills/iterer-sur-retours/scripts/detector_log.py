#!/usr/bin/env python3
"""detector_log.py -- garde-fou anti-NON-APPLICATION-SILENCIEUSE (famille B).

Une regle-a-detecteur qui ne se declenche pas doit le DIRE (patch LM2). Pour chaque regle B x
cas : `detecte` / `non_detecte` + POURQUOI (colonne presente/absente). Rend visible le silencieux.

Sortie : `.iter/detector_log.json`.
CLI : python detector_log.py   (utilise la fixture columns_schema.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from build_matrix import (ITER, SKILL_ROOT, derive_attendu, introspect_columns,
                          load_registry, load_schema)


def build_detector_log(registry: dict, schema: dict) -> dict:
    holdout = set(registry.get("holdout", []))
    regles_b = [r for r in registry.get("regles", []) if r.get("famille") == "B"]
    retour_cases = sorted({k for r in registry.get("regles", []) for k in (r.get("attendu_par_cas") or {})})
    cases = retour_cases + sorted(holdout)

    entries = []
    for r in regles_b:
        det = r.get("detecteur")
        for cid in cases:
            attendu, raison = derive_attendu(det, cid, schema)
            cols = introspect_columns(cid, schema)
            if attendu == "a_valider_humain":
                etat = "indetermine"
            elif attendu == "fire":
                etat = "detecte"
            else:
                etat = "non_detecte"
            entries.append({
                "regle": r["id"], "cas": cid, "etat": etat, "pourquoi": raison,
                "is_holdout": cid in holdout,
                "colonnes_connues": cols is not None,
            })
    return {"detecteur": [r["id"] for r in regles_b], "entries": entries}


def main() -> int:
    registry = load_registry()
    schema = load_schema()
    log = build_detector_log(registry, schema)
    ITER.mkdir(exist_ok=True)
    (ITER / "detector_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== detector_log (detecte / non_detecte + pourquoi) ===")
    for e in log["entries"]:
        flag = " [held-out]" if e["is_holdout"] else ""
        print(f"  {e['regle']} x {e['cas']:<16} {e['etat']:<12}{flag}  <- {e['pourquoi']}")
    # Assertion golden : la non-application silencieuse est RENDUE VISIBLE.
    silent = [e for e in log["entries"] if e["etat"] == "non_detecte"]
    assert any(e["cas"] == "C67" for e in silent), \
        "C67 (colonne absente) doit apparaitre 'non_detecte'"
    print(f"\n[OK] {len(silent)} non-application(s) rendue(s) visible(s) (dont C67).")
    print(f"[OK] log ecrit : {(ITER / 'detector_log.json').relative_to(SKILL_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
