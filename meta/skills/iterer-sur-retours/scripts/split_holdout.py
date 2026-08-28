#!/usr/bin/env python3
"""split_holdout.py -- ECRIT le held-out canonique (source de verite unique).

Regle de fer : une SEULE liste held-out. `split_holdout.py` ECRIT `signal/registry.yaml`
(champ `holdout`) ; `signal/holdout.txt` en est un RENDU DERIVE horodate read-only ;
`Case.id` est la cle de jointure.

Assertions dures (patch SIM-002 ; sinon STOP, rien n'est ecrit) :
  - intersection(holdout, cas_cites_par_retour) == vide
  - intersection(holdout, keys(attendu_par_cas))  == vide

Reconciliation (divergence tracee) : la data_model 2 montrait un exemple ou un cas held-out
(C67) apparaissait dans `attendu_par_cas`. C'est INCOMPATIBLE avec la 2e assertion.
On tranche : `attendu_par_cas` ne contient QUE des cas de RETOUR (jamais du held-out). Les
sorties detecteur sur le held-out sont MESUREES dans `detector_log.json` (Session 4), jamais
posees a la main -> sinon on reglerait sur le held-out.

CLI :
  python split_holdout.py                              # held-out = held_out_candidats de tableur.json
  python split_holdout.py --holdout C67,C21,X # override (teste le refus : C21 interdit)
  python split_holdout.py --case ../evals/cases/tableur.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parent.parent
SIGNAL = SKILL_ROOT / "signal"
DEFAULT_CASE = SKILL_ROOT / "evals" / "cases" / "tableur.json"

# Seed regles S3 (tableur). En Session 4, attendu_par_cas est enrichi par INTROSPECTION des
# colonnes reelles ; ici, seed minimal cadre sur les cas de RETOUR uniquement.
REGLES_SEED = [
    {"id": "limite_5_categories", "famille": "A", "detecteur": None, "attendu_par_cas": {}},
    {"id": "bins_duree", "famille": "B",
     "detecteur": "duration|duree",  # regex sur nom de colonne (pas le mot 'colonne')
     "attendu_par_cas": {"C21": "fire", "C32": "fire"}},  # cas de RETOUR only
]


class HoldoutError(Exception):
    """Held-out incoherent -> STOP, rien n'est ecrit."""


def _attendu_keys(regles) -> set:
    keys = set()
    for r in regles:
        keys |= set((r.get("attendu_par_cas") or {}).keys())
    return keys


def build_registry(case: dict, holdout: list[str], regles: list[dict]) -> dict:
    cas_cites = set(case.get("retours", {}).get("cas_cites", []))
    hset = set(holdout)

    inter_cites = hset & cas_cites
    if inter_cites:
        raise HoldoutError(
            f"intersection(holdout, cas_cites) = {sorted(inter_cites)} != vide -> "
            "un cas cite par un retour ne peut pas etre held-out (digue anti-overfit)."
        )
    inter_attendu = hset & _attendu_keys(regles)
    if inter_attendu:
        raise HoldoutError(
            f"intersection(holdout, keys(attendu_par_cas)) = {sorted(inter_attendu)} != vide -> "
            "un cas avec attente posee ne peut pas etre held-out (on reglerait dessus)."
        )
    return {"tolerance": 0.5, "holdout": list(holdout), "regles": regles}


def write_registry(registry: dict) -> tuple[Path, Path]:
    SIGNAL.mkdir(exist_ok=True)
    reg_path = SIGNAL / "registry.yaml"
    reg_path.write_text(
        "# GENERE par split_holdout.py -- source de verite unique du held-out.\n"
        "# Ne pas editer holdout a la main : relancer split_holdout.py.\n"
        + yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    # Rendu derive read-only horodate.
    txt_path = SIGNAL / "holdout.txt"
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    txt_path.write_text(
        f"# RENDU DERIVE read-only de registry.yaml:holdout -- genere {ts}\n"
        "# NE PAS EDITER : source = registry.yaml (split_holdout.py).\n"
        + "\n".join(registry["holdout"]) + "\n",
        encoding="utf-8",
    )
    return reg_path, txt_path


def main(argv: list[str]) -> int:
    case_path = DEFAULT_CASE
    holdout_override = None
    if "--case" in argv:
        case_path = Path(argv[argv.index("--case") + 1])
    if "--holdout" in argv:
        holdout_override = [x.strip() for x in argv[argv.index("--holdout") + 1].split(",") if x.strip()]

    case = json.loads(case_path.read_text(encoding="utf-8"))
    holdout = holdout_override or case.get("corpus", {}).get("held_out_candidats", [])
    if not holdout:
        print("Aucun held-out candidat (branche jugement enumere en V1.1 ?). Rien a ecrire.")
        return 0

    try:
        registry = build_registry(case, holdout, REGLES_SEED)
    except HoldoutError as e:
        print(f"[REFUS] held-out incoherent : {e}")
        print("=> Rien ecrit. Corrige le held-out et relance.")
        return 2

    reg_path, txt_path = write_registry(registry)
    print(f"[OK] held-out canonique ecrit : {sorted(registry['holdout'])}")
    print(f"     registry : {reg_path.relative_to(SKILL_ROOT)}")
    print(f"     rendu    : {txt_path.relative_to(SKILL_ROOT)} (read-only derive)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
