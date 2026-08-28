#!/usr/bin/env python3
"""fork.py -- Fork detector (P1) : regime par SEUIL (patch ARCH-004), pas label libre.

Le classificateur (agents/classificateur.md) emet, par retour, une famille :
  A structurelle | B detecteur  -> ORACLE MECANIQUE (verifiable a la machine)
  C bloque input | D jugement   -> pas d'oracle mecanique

part_oracle_mecanique = (n_A + n_B) / n_total   dans [0,1]

Regime (seuil) :
  part_oracle >= 0.5  -> factuel   (matrice deterministe + contrat auto-improver)
  part_oracle <= 0.2  -> jugement  (juge-par-grille + exemples + reduction de regles)
  entre les deux      -> mixte     (regime primaire = dominant ; l'autre nature -> sous-routine)

COMPLETUDE (patch SIM-007) : n_total DOIT egaler n_retours_normalises declare, sinon stop
(un retour perdu fausse le fork). Assertion dure.

CLI :
  python fork.py <classified.json>      # calcule le fork d'un fichier classifie
  python fork.py --golden               # assertions garde-fou : cas tableur (factuel) + cas jugement (jugement)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = SKILL_ROOT / "evals" / "fixtures"

ORACLE_FAMILIES = {"A", "B"}
THRESH_FACTUEL = 0.5
THRESH_JUGEMENT = 0.2


def compute_fork(classified: dict) -> dict:
    items = classified.get("items", [])
    n_total = len(items)
    n_declared = classified.get("n_retours_normalises")

    # Completude : rien perdu entre normalisation et classification.
    if n_declared is not None and n_total != n_declared:
        raise AssertionError(
            f"COMPLETUDE VIOLEE : n_items({n_total}) != n_retours_normalises({n_declared}). "
            "Un retour perdu fausse le fork -> stop."
        )
    if n_total == 0:
        raise AssertionError("aucun item classifie -> fork indefini.")

    n_oracle = sum(1 for it in items if it.get("famille") in ORACLE_FAMILIES)
    part_oracle = n_oracle / n_total

    if part_oracle >= THRESH_FACTUEL:
        regime = "factuel"
    elif part_oracle <= THRESH_JUGEMENT:
        regime = "jugement"
    else:
        regime = "mixte"

    counts = {}
    for it in items:
        f = it.get("famille", "?")
        counts[f] = counts.get(f, 0) + 1

    return {
        "skill_cible": classified.get("skill_cible"),
        "regime": regime,
        "part_oracle_mecanique": round(part_oracle, 4),
        "n_retours_normalises": n_total,
        "familles": counts,
    }


def _golden() -> int:
    ok = True

    tableur = compute_fork(json.loads((FIXTURES / "tableur_classified.json").read_text(encoding="utf-8")))
    print(f"tableur   -> regime={tableur['regime']} part_oracle={tableur['part_oracle_mecanique']} "
          f"familles={tableur['familles']}")
    try:
        assert tableur["regime"] == "factuel", "tableur doit forker FACTUEL"
        assert tableur["part_oracle_mecanique"] >= 0.5, "tableur part_oracle doit etre >=0.5"
        # types_attendus expected.json : A>=5, B>=1, C>=1
        assert tableur["familles"].get("A", 0) >= 5, "tableur A>=5"
        assert tableur["familles"].get("B", 0) >= 1, "tableur B>=1"
        assert tableur["familles"].get("C", 0) >= 1, "tableur C>=1"
        print("  [OK] tableur factuel + part_oracle>=0.5 + A>=5,B>=1,C>=1")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    jugement = compute_fork(json.loads((FIXTURES / "jugement_classified.json").read_text(encoding="utf-8")))
    print(f"jugement  -> regime={jugement['regime']} part_oracle={jugement['part_oracle_mecanique']} "
          f"familles={jugement['familles']}")
    try:
        assert jugement["regime"] == "jugement", "le cas jugement doit forker JUGEMENT"
        assert jugement["part_oracle_mecanique"] <= 0.2, "jugement part_oracle doit etre <=0.2"
        print("  [OK] cas jugement -> regime jugement + part_oracle<=0.2")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    # Completude : un fichier ampute doit lever.
    try:
        compute_fork({"n_retours_normalises": 12, "items": [{"famille": "A"}]})
        ok = False
        print("  [FAIL] completude : aurait du lever sur n_items!=n_declared")
    except AssertionError:
        print("  [OK] completude : n_items != n_retours_normalises -> stop")

    print("=> GOLDEN OK" if ok else "=> GOLDEN ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--golden" in sys.argv:
        sys.exit(_golden())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        sys.exit(0)
    data = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    print(json.dumps(compute_fork(data), ensure_ascii=False, indent=2))
