#!/usr/bin/env python3
"""
Croise paires.json (vérité-terrain du concepteur) avec un ou plusieurs rapports de relecteur
(JSON {"paires": [{"id", "locuteur_clair", "plausibles_bon_registre", "tranchable", "choix", ...}]}).

Imprime, par relecteur : les paires qui échouent (locuteur / registre / tranchable=non),
les « trop_evident », l'accord avec la vérité-terrain séparé net / fin.
Avec deux relecteurs ou plus : l'accord entre relecteurs, séparé net / fin.

Usage : python croiser_relectures.py RELECTURE.json [RELECTURE2.json ...]
"""
import json
import sys
from itertools import combinations
from pathlib import Path

ICI = Path(__file__).resolve().parent


def charger(chemin):
    return {p["id"]: p for p in json.loads(Path(chemin).read_text(encoding="utf-8"))["paires"]}


def main(chemins):
    verite = charger(ICI / "paires.json")
    relectures = {Path(c).stem: charger(c) for c in chemins}
    for nom, r in relectures.items():
        manquants = set(verite) - set(r)
        assert not manquants, f"{nom} : paires manquantes {sorted(manquants)}"
        echecs = [(i, "locuteur") for i, p in r.items() if p["locuteur_clair"] != "oui"]
        echecs += [(i, "registre") for i, p in r.items() if p["plausibles_bon_registre"] != "oui"]
        echecs += [(i, "tranchable=non") for i, p in r.items() if p["tranchable"] == "non"]
        trop = sorted(i for i, p in r.items() if p["tranchable"] == "trop_evident")
        acc = {"net": [0, 0], "fin": [0, 0]}
        desaccords = []
        for i, v in verite.items():
            e = v["ecart"]
            ok = r[i]["choix"] == v["verite_terrain"]["choix"]
            acc[e][1] += 1
            acc[e][0] += ok
            if not ok:
                desaccords.append(f"{i} ({e})")
        print(f"== {nom}")
        print(f"   échecs : {echecs or 'aucun'}")
        print(f"   trop_evident ({len(trop)}) : {trop}")
        print(f"   trop_evident étiquetés fin : {[i for i in trop if verite[i]['ecart'] == 'fin']}")
        print(f"   nets non signalés trop_evident : "
              f"{[i for i, v in verite.items() if v['ecart'] == 'net' and i not in trop]}")
        for e in acc:
            print(f"   accord avec la vérité-terrain, {e} : {acc[e][0]}/{acc[e][1]}")
        print(f"   désaccords : {desaccords or 'aucun'}")
    for (n1, r1), (n2, r2) in combinations(relectures.items(), 2):
        acc = {"net": [0, 0], "fin": [0, 0]}
        diff = []
        for i, v in verite.items():
            e = v["ecart"]
            ok = r1[i]["choix"] == r2[i]["choix"]
            acc[e][1] += 1
            acc[e][0] += ok
            if not ok:
                diff.append(f"{i} ({e})")
        print(f"== {n1} vs {n2}")
        for e in acc:
            print(f"   accord entre relecteurs, {e} : {acc[e][0]}/{acc[e][1]}")
        print(f"   divergences : {diff or 'aucune'}")


if __name__ == "__main__":
    main(sys.argv[1:])
