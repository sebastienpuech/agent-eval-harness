#!/usr/bin/env python3
"""build_matrix.py -- signal factuel : matrice regle x cas + attendu_par_cas DERIVE.

Statuts de cellule (data_model MatrixCell) :
  applique   (MATCH)  | regresse (FAIL) | NA_justifie | NOT_FOUND
`NOT_FOUND` = detecteur non declenche (colonne cible absente) -> rendu VISIBLE mais **exclu
du denominateur** (ne compte ni comme pass ni comme fail).

`attendu_par_cas` (famille B) est DERIVE par introspection des colonnes reelles (patch SIM-008),
JAMAIS devine : `fire` si une colonne matche le detecteur, `no_fire` sinon. Colonnes non
disponibles (dataset non monte) -> `a_valider_humain` (loggue, non bloquant).

Rappel frontiere : ce module MESURE, il n'ecrit AUCUN patch du skill cible.

CLI :
  python build_matrix.py                 # utilise la fixture columns_schema.json
  python build_matrix.py --demo          # affiche matrice + attendu derive + NOT_FOUND
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parent.parent
SIGNAL = SKILL_ROOT / "signal"
FIXTURES = SKILL_ROOT / "evals" / "fixtures"
ITER = SKILL_ROOT / ".iter"


def load_registry() -> dict:
    reg = SIGNAL / "registry.yaml"
    if not reg.exists():
        raise SystemExit("signal/registry.yaml absent -> lancer split_holdout.py d'abord.")
    return yaml.safe_load(reg.read_text(encoding="utf-8"))


def load_schema(path: Path | None = None) -> dict:
    path = path or (FIXTURES / "columns_schema.json")
    return json.loads(path.read_text(encoding="utf-8"))


def introspect_columns(case_id: str, schema: dict) -> list[str] | None:
    """Colonnes reelles d'un cas. En prod : lire l'entete du dataset (csv/xlsx). Ici : schema.
    None => dataset non monte => attente 'a_valider_humain'."""
    return schema.get(case_id)


def derive_attendu(detecteur: str | None, case_id: str, schema: dict):
    """Retourne (attendu, raison). attendu in {'fire','no_fire','a_valider_humain'}."""
    if not detecteur:
        return "no_fire", "regle sans detecteur"
    cols = introspect_columns(case_id, schema)
    if cols is None:
        return "a_valider_humain", f"colonnes de {case_id} non disponibles (dataset non monte)"
    pat = re.compile(detecteur)
    hit = next((c for c in cols if pat.search(c)), None)
    if hit:
        return "fire", f"colonne '{hit}' matche /{detecteur}/"
    return "no_fire", f"aucune colonne ne matche /{detecteur}/ dans {case_id}"


def build_matrix(registry: dict, schema: dict, outcomes: dict | None = None) -> dict:
    """outcomes : {(rule_id, case_id): 'applique'|'regresse'} issu d'un run reel (S5).
    Absent -> cellules 'a_evaluer' (structure seule)."""
    outcomes = outcomes or {}
    holdout = set(registry.get("holdout", []))
    regles = registry.get("regles", [])
    # cas cites (retour) : depuis attendu_par_cas seed + holdout pour la mesure.
    retour_cases = sorted({k for r in regles for k in (r.get("attendu_par_cas") or {})})
    cases = retour_cases + sorted(holdout)

    cells = []
    attendu_derive = {}
    a_valider = []
    for r in regles:
        rid, fam, det = r["id"], r.get("famille"), r.get("detecteur")
        for cid in cases:
            if fam == "B":
                attendu, raison = derive_attendu(det, cid, schema)
                if attendu == "a_valider_humain":
                    a_valider.append({"regle": rid, "cas": cid, "raison": raison})
                attendu_derive.setdefault(rid, {})[cid] = attendu
                if attendu == "no_fire":
                    status = "NOT_FOUND"  # detecteur non declenche -> hors denominateur
                    fired = False
                else:
                    status = outcomes.get((rid, cid), "a_evaluer")
                    fired = True
            else:  # famille A : universelle
                status = outcomes.get((rid, cid), "a_evaluer")
                fired = None
            cells.append({"rule_id": rid, "case_id": cid, "famille": fam,
                          "status": status, "detector_fired": fired,
                          "is_holdout": cid in holdout})

    return {"cells": cells, "attendu_derive": attendu_derive,
            "a_valider_humain": a_valider, "cases": cases}


def write_matrix(matrix: dict) -> Path:
    ITER.mkdir(exist_ok=True)
    csv_path = ITER / "matrix.csv"
    lines = ["rule_id,case_id,famille,status,detector_fired,is_holdout"]
    for c in matrix["cells"]:
        lines.append(f"{c['rule_id']},{c['case_id']},{c['famille']},{c['status']},"
                     f"{c['detector_fired']},{c['is_holdout']}")
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ITER / "attendu_derive.json").write_text(
        json.dumps({"attendu_derive": matrix["attendu_derive"],
                    "a_valider_humain": matrix["a_valider_humain"]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path


def _demo() -> int:
    registry = load_registry()
    schema = load_schema()
    m = build_matrix(registry, schema)
    print("=== attendu_par_cas DERIVE (famille B) ===")
    print(json.dumps(m["attendu_derive"], ensure_ascii=False, indent=2))
    print("\n=== NOT_FOUND (detecteur non declenche, hors denominateur) ===")
    nf = [(c["rule_id"], c["case_id"]) for c in m["cells"] if c["status"] == "NOT_FOUND"]
    for rid, cid in nf:
        print(f"  {rid} x {cid} : NOT_FOUND")
    print(f"\n=== a_valider_humain : {len(m['a_valider_humain'])} (non derivable mecaniquement) ===")
    # Assertions golden : C67 et C75 n'ont PAS la colonne -> no_fire/NOT_FOUND.
    ad = m["attendu_derive"].get("bins_duree", {})
    assert ad.get("C21") == "fire" and ad.get("C32") == "fire", ad
    assert ad.get("C67") == "no_fire", ad
    assert ("bins_duree", "C67") in nf, "C67 doit etre NOT_FOUND"
    csv_path = write_matrix(m)
    print(f"\n[OK] matrice ecrite : {csv_path.relative_to(SKILL_ROOT)}")
    print("=> DEMO OK : attendu derive (C21/C32 fire, C67 no_fire), NOT_FOUND visible.")
    return 0


if __name__ == "__main__":
    sys.exit(_demo())
