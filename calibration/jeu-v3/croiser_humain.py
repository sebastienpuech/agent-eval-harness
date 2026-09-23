#!/usr/bin/env python3
"""
Croise l'annotation humaine (CSV téléchargé depuis comparer.html) avec :
  - la vérité-terrain du concepteur (paires.json), séparée net / fin ;
  - les choix des relecteurs indépendants (relectures/*.json) passés en argument.

Le CSV a pour colonnes : id;choix;cote_gauche;cote_droite — « choix » vaut gauche / droite /
egales, et cote_gauche dit quelle réponse (A ou B) était affichée à gauche. On retraduit donc
le choix humain en A / B / egales avant toute comparaison.

Usage : python croiser_humain.py annotations/comparaison-<seed>.csv [relectures/*.json ...]
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def lire_csv(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    humain = {}
    for l in lignes:
        c = l["choix"]
        humain[l["id"]] = "egales" if c == "egales" else (l["cote_gauche"] if c == "gauche" else l["cote_droite"])
    return humain


def accord(ref, humain, ids):
    """(accords, tranchées, égales) sur les ids donnés ; les « egales » ne comptent ni pour ni contre."""
    tr = [i for i in ids if humain[i] != "egales"]
    return sum(1 for i in tr if humain[i] == ref[i]), len(tr), len(ids) - len(tr)


def main(csv_path, relectures):
    verite = {p["id"]: p for p in json.loads((ICI / "paires.json").read_text(encoding="utf-8"))["paires"]}
    humain = lire_csv(csv_path)
    assert set(humain) == set(verite), set(humain) ^ set(verite)
    vt = {i: p["verite_terrain"]["choix"] for i, p in verite.items()}
    ids_par = defaultdict(list)
    for i, p in verite.items():
        ids_par["tout"].append(i)
        ids_par[p["ecart"]].append(i)
        ids_par[p["domaine"]].append(i)

    print(f"annotation : {csv_path}")
    print(f"« les deux se valent » : {sum(1 for v in humain.values() if v == 'egales')} / 40 "
          f"({Counter(verite[i]['ecart'] for i, v in humain.items() if v == 'egales')})")
    print("\n== humain vs vérité-terrain du concepteur (égales exclues du compte)")
    for cle in ("tout", "net", "fin", "echanges-pro", "conduite-projet-ong", "course-a-pied"):
        a, n, e = accord(vt, humain, ids_par[cle])
        print(f"   {cle:22s} {a}/{n} tranchées ({a / n:.0%}), {e} égales")
    des = [i for i in ids_par["tout"] if humain[i] not in ("egales", vt[i])]
    print(f"   désaccords : {des}")
    print(f"   sur les 3 vérités contestées (P-06, C-05, C-07) : "
          f"{ {i: humain[i] + ' (concepteur ' + vt[i] + ')' for i in ('P-06', 'C-05', 'C-07')} }")

    for chemin in relectures:
        r = {p["id"]: p["choix"] for p in json.loads(Path(chemin).read_text(encoding="utf-8"))["paires"]}
        if set(r) != set(verite):
            print(f"\n== {Path(chemin).stem} : ignoré ({len(r)} paires seulement)")
            continue
        print(f"\n== humain vs {Path(chemin).stem}")
        for cle in ("tout", "net", "fin"):
            a, n, e = accord(r, humain, ids_par[cle])
            print(f"   {cle:6s} {a}/{n} tranchées ({a / n:.0%}), {e} égales")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
