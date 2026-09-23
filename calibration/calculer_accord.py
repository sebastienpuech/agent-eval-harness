#!/usr/bin/env python3
"""Le chiffre : l'accord entre le juge et l'humain sur les 40 comparaisons.

Le juge note chaque reponse sur 12. Pour chaque paire, sa preference est la reponse au
total le plus haut — et « egales » quand l'ecart est INFERIEUR OU EGAL A SON PROPRE BRUIT.
C'est la baseline (a) du CADRE.md : un ecart plus petit que le bruit du juge n'est pas une
preference, c'est du hasard. L'ignorer gonflerait artificiellement l'accord.

Deux jeux :
  - v2 (defaut, code inchange) : profils voulus comme verite faible, taux d'accord + bootstrap ;
  - v3 (--jeu jeu-v3) : verite-terrain du concepteur, annotation humaine (fichier nomme par sa
    graine d'ordre 20260924 ; l'annotation est du 22/09/2026, commit c445db5), notes du
    juge ET du modele nu (baseline b). Quatre accords, chacun separe net / fin et par domaine,
    avec taux brut sur les paires tranchees par les deux, taux 3 classes (A / B / egales),
    kappa de Cohen et IC95 par bootstrap (10 000 tirages, graine loguee). Produit
    jeu-v3/resultat.json et jeu-v3/RESULTAT.md.

L'intervalle de confiance est calcule par bootstrap (10 000 tirages) : avec 40 paires il
est large, et le publier large vaut mieux que le taire.

Usage :  python calculer_accord.py [--jeu jeu-v3]
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ICI = Path(__file__).resolve().parent
ANNOT = ICI / "annotations"
SEED = 20260920
ORDRE = ANNOT / f"comparaison-{SEED}.ordre.json"
CHOIX = ANNOT / f"comparaison-{SEED}.csv"
NOTES = ICI / "notes-du-juge.json"
SORTIE = ICI / "resultat.json"
GRAINE_BOOTSTRAP = 12345
N_BOOTSTRAP = 10000

# Ordre de qualite voulu a la fabrication (v2). Sert de verite-terrain FAIBLE : il dit ce que
# la consigne demandait, pas ce que le modele a reellement produit a chaque fois.
RANG = {"soigne": 3, "expedie": 2, "verbeux": 1}


def bootstrap(paires, n=N_BOOTSTRAP, graine=GRAINE_BOOTSTRAP):
    """Intervalle de confiance a 95 % par re-tirage avec remise (v2 : moyenne d'une serie 0/1)."""
    rng = random.Random(graine)
    n_p = len(paires)
    if not n_p:
        return (0.0, 0.0)
    tirages = []
    for _ in range(n):
        ech = [paires[rng.randrange(n_p)] for _ in range(n_p)]
        tirages.append(sum(ech) / n_p)
    tirages.sort()
    return (tirages[int(0.025 * n)], tirages[int(0.975 * n)])


def accord(a, b):
    """Taux d'accord sur les paires ou les deux se prononcent (egalites incluses)."""
    comm = [1.0 if x == y else 0.0 for x, y in zip(a, b)]
    taux = sum(comm) / len(comm) if comm else 0.0
    return taux, comm


# ============================================================================ v2 (inchange)
def main_v2() -> int:
    for f in (ORDRE, CHOIX, NOTES):
        if not f.exists():
            print(f"ERREUR : manquant — {f.name}", file=sys.stderr)
            return 2

    ordre = json.loads(ORDRE.read_text(encoding="utf-8"))["cotes"]
    notes = json.loads(NOTES.read_text(encoding="utf-8"))["notes"]
    lignes = list(csv.DictReader(CHOIX.open(encoding="utf-8-sig"), delimiter=";"))

    manquantes = [k for cid in ordre for k in (f"{cid}.A", f"{cid}.B") if k not in notes]
    if manquantes:
        print(f"ERREUR : {len(manquantes)} notation(s) du juge manquante(s), "
              f"ex. {manquantes[:3]}", file=sys.stderr)
        return 2

    lignes_res, h_vs_p, j_vs_p, h_vs_j = [], [], [], []
    bruits = []

    for l in lignes:
        cid, ch = l["id"], l["choix"]
        o = ordre[cid]
        pg, pd = o["profil_gauche"], o["profil_droite"]
        cg, cd = o["gauche"], o["droite"]

        h = "egales" if ch == "egales" else (pg if ch == "gauche" else pd)

        rg = notes[f"{cid}.{cg}"]["resultat"]
        rd = notes[f"{cid}.{cd}"]["resultat"]
        tg, td = rg["total_mean"], rd["total_mean"]
        bruit = max(rg.get("bruit_intra_juge", 0.0), rd.get("bruit_intra_juge", 0.0))
        bruits.append(bruit)
        if abs(tg - td) <= bruit:
            j = "egales"
        else:
            j = pg if tg > td else pd

        attendu = pg if RANG[pg] > RANG[pd] else pd

        h_vs_p.append(1.0 if h == attendu else 0.0)
        j_vs_p.append(1.0 if j == attendu else 0.0)
        h_vs_j.append(1.0 if h == j else 0.0)

        lignes_res.append({
            "cas": cid, "domaine": o["domaine"],
            "profil_gauche": pg, "profil_droite": pd,
            "humain": h, "juge": j, "attendu": attendu,
            "total_gauche": tg, "total_droite": td, "bruit": round(bruit, 3),
            "accord": h == j,
        })

    n = len(lignes_res)
    res = {}
    for nom, serie in (("humain_vs_profils", h_vs_p),
                       ("juge_vs_profils", j_vs_p),
                       ("humain_vs_juge", h_vs_j)):
        taux = sum(serie) / n
        bas, haut = bootstrap(serie)
        res[nom] = {"taux": round(taux, 3), "ic95": [round(bas, 3), round(haut, 3)], "n": n}

    egal_h = sum(1 for r in lignes_res if r["humain"] == "egales")
    egal_j = sum(1 for r in lignes_res if r["juge"] == "egales")
    bruit_moyen = sum(bruits) / len(bruits)

    print(f"=== ETALONNAGE DU JUGE — {n} comparaisons ===\n")
    print(f"Bruit intra-juge moyen (ecart-type des totaux sur 3 rejeux) : {bruit_moyen:.2f} pts sur 12")
    print(f"Egalites : humain {egal_h}, juge {egal_j}\n")
    libelle = {
        "humain_vs_profils": "L'humain suit-il la qualite voulue ?",
        "juge_vs_profils": "Le juge suit-il la qualite voulue ?",
        "humain_vs_juge": "LE CHIFFRE — le juge prefere-t-il comme l'humain ?",
    }
    for k, v in res.items():
        print(f"{libelle[k]:52} {v['taux']:.0%}  (IC95 {v['ic95'][0]:.0%}-{v['ic95'][1]:.0%})")

    print("\n--- par domaine (indicatif, ~13 cas chacun) ---")
    for dom in sorted({r["domaine"] for r in lignes_res}):
        s = [r for r in lignes_res if r["domaine"] == dom]
        print(f"  {dom:8} accord {sum(r['accord'] for r in s)}/{len(s)}")

    print("\n--- par contraste ---")
    contr = {}
    for r in lignes_res:
        contr.setdefault(" vs ".join(sorted([r["profil_gauche"], r["profil_droite"]])), []).append(r)
    for k, s in sorted(contr.items()):
        print(f"  {k:22} accord {sum(r['accord'] for r in s)}/{len(s)}")

    rng2 = random.Random(7)
    serie_j = [r["juge"] for r in lignes_res]
    serie_h = [r["humain"] for r in lignes_res]
    sims = sorted(sum(a == rng2.choice(serie_j) for a in serie_h) / n for _ in range(20000))
    hasard = sum(sims) / len(sims)
    hasard_p95 = sims[int(0.95 * len(sims))]
    trivial = sum(r["humain"] == r["attendu"] for r in lignes_res) / n

    ecarts = [r for r in lignes_res if r["humain"] != r["attendu"]]
    suivi_ecarts = sum(r["accord"] for r in ecarts)

    print("\n--- ce a quoi le chiffre doit etre compare ---")
    print(f"  hasard (meme distribution)            {hasard:.0%}  (95e centile {hasard_p95:.0%})")
    print(f"  strategie triviale 'toujours le mieux concu'  {trivial:.0%}")
    print(f"  la ou l'humain s'ecarte de la conception : le juge le suit "
          f"{suivi_ecarts}/{len(ecarts)}")

    res["baselines"] = {
        "hasard": round(hasard, 3), "hasard_p95": round(hasard_p95, 3),
        "strategie_triviale": round(trivial, 3),
        "ecarts_humain_conception": len(ecarts),
        "juge_suit_humain_sur_ecarts": suivi_ecarts,
    }

    SORTIE.write_text(json.dumps(
        {"seed": SEED, "n": n, "bruit_intra_juge_moyen": round(bruit_moyen, 3),
         "egalites": {"humain": egal_h, "juge": egal_j},
         "mesures": res, "detail": lignes_res}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetail complet : {SORTIE.name}")
    return 0


# ============================================================================ v3
CLASSES = ("A", "B", "egales")
DOMAINES = ("echanges-pro", "conduite-projet-ong", "course-a-pied")
SOUS_ENSEMBLES = ("tout", "net", "fin") + DOMAINES
COMPARAISONS = (
    ("juge_vs_verite", "juge", "verite", "juge ↔ vérité-terrain du concepteur"),
    ("humain_vs_juge", "humain", "juge", "humain ↔ juge — LE CHIFFRE"),
    ("humain_vs_nu", "humain", "nu", "humain ↔ modèle nu"),
    ("juge_vs_nu", "juge", "nu", "juge ↔ modèle nu"),
    ("humain_vs_verite", "humain", "verite", "humain ↔ vérité-terrain (rappel, déjà connu)"),
)


def kappa_cohen(x: list[str], y: list[str]) -> float | None:
    """Kappa de Cohen sur les classes A / B / egales. None si p_e = 1 (kappa indefini)."""
    n = len(x)
    if n == 0:
        return None
    po = sum(1 for a, b in zip(x, y) if a == b) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[c] * cy[c] for c in CLASSES) / (n * n)
    if abs(1 - pe) < 1e-12:
        return None
    return (po - pe) / (1 - pe)


def mesurer(x: list[str], y: list[str], graine: int = GRAINE_BOOTSTRAP, n_boot: int = N_BOOTSTRAP) -> dict:
    """Taux brut (paires tranchees par les deux), taux 3 classes, kappa, IC95 bootstrap sur les deux derniers."""
    n = len(x)
    tranchees = [(a, b) for a, b in zip(x, y) if a != "egales" and b != "egales"]
    brut_acc = sum(1 for a, b in tranchees if a == b)
    taux3 = sum(1 for a, b in zip(x, y) if a == b) / n if n else None
    k = kappa_cohen(x, y)

    rng = random.Random(graine)
    ks, ts = [], []
    indefinis = 0
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        bx, by = [x[i] for i in idx], [y[i] for i in idx]
        ts.append(sum(1 for a, b in zip(bx, by) if a == b) / n)
        kb = kappa_cohen(bx, by)
        if kb is None:
            indefinis += 1
        else:
            ks.append(kb)
    ts.sort()
    ks.sort()

    def ic(serie):
        if len(serie) < 100:
            return None
        return [round(serie[int(0.025 * len(serie))], 3), round(serie[int(0.975 * len(serie))], 3)]

    return {
        "n": n,
        "tranchees_par_les_deux": len(tranchees),
        "accord_brut": brut_acc,
        "taux_brut": round(brut_acc / len(tranchees), 3) if tranchees else None,
        "taux_3_classes": round(taux3, 3) if taux3 is not None else None,
        "taux_3_classes_ic95": ic(ts),
        "kappa": round(k, 3) if k is not None else None,
        "kappa_ic95": ic(ks),
        "bootstrap": {"tirages": n_boot, "graine": graine, "kappa_indefini": indefinis},
    }


def preference_juge(ra: dict, rb: dict) -> tuple[str, float, float, float]:
    ta, tb = ra["total_mean"], rb["total_mean"]
    bruit = max(ra.get("bruit_intra_juge", 0.0), rb.get("bruit_intra_juge", 0.0))
    if abs(ta - tb) <= bruit:
        return "egales", ta, tb, bruit
    return ("A" if ta > tb else "B"), ta, tb, bruit


def main_v3(jeu: str) -> int:
    dossier = ICI / jeu
    paires_f = dossier / "paires.json"
    csv_f = dossier / "annotations" / "comparaison-20260924.csv"
    notes_f = dossier / "notes-du-juge.json"
    nu_f = dossier / "notes-modele-nu.json"
    sortie_json = dossier / "resultat.json"
    sortie_md = dossier / "RESULTAT.md"
    for f in (paires_f, csv_f, notes_f, nu_f):
        if not f.exists():
            print(f"ERREUR : manquant — {f}", file=sys.stderr)
            return 2

    paires = {p["id"]: p for p in json.loads(paires_f.read_text(encoding="utf-8"))["paires"]}
    notes_doc = json.loads(notes_f.read_text(encoding="utf-8"))
    nu_doc = json.loads(nu_f.read_text(encoding="utf-8"))
    notes, nu = notes_doc["notes"], nu_doc["notes"]

    # --- l'humain, relu comme croiser_humain.py : gauche/droite -> A/B via cote_gauche
    humain = {}
    with open(csv_f, encoding="utf-8-sig", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            c = l["choix"]
            humain[l["id"]] = "egales" if c == "egales" else (l["cote_gauche"] if c == "gauche" else l["cote_droite"])

    ids = sorted(paires)
    manquantes = [k for cid in ids for k in (f"{cid}.A", f"{cid}.B") if k not in notes]
    manquantes_nu = [cid for cid in ids if cid not in nu]
    if manquantes or manquantes_nu or set(humain) != set(ids):
        print(f"ERREUR : juge manque {len(manquantes)}, nu manque {len(manquantes_nu)}, "
              f"humain {len(humain)}/{len(ids)}", file=sys.stderr)
        return 2

    # --- une ligne par paire, avec les quatre lectures
    detail = []
    for cid in ids:
        p = paires[cid]
        j, ta, tb, bruit = preference_juge(notes[f"{cid}.A"]["resultat"], notes[f"{cid}.B"]["resultat"])
        detail.append({
            "cas": cid, "domaine": p["domaine"], "ecart": p["ecart"],
            "verite": p["verite_terrain"]["choix"], "contestee": bool(p["verite_terrain"].get("contestee")),
            "humain": humain[cid], "juge": j, "nu": nu[cid]["preference"],
            "juge_total_A": ta, "juge_total_B": tb, "juge_bruit": round(bruit, 3),
            "nu_votes": nu[cid]["votes"], "nu_unanime": nu[cid]["unanime"],
        })

    def sous_ensemble(cle):
        if cle == "tout":
            return detail
        if cle in ("net", "fin"):
            return [d for d in detail if d["ecart"] == cle]
        return [d for d in detail if d["domaine"] == cle]

    mesures = {}
    for nom, a, b, _ in COMPARAISONS:
        mesures[nom] = {}
        for cle in SOUS_ENSEMBLES:
            s = sous_ensemble(cle)
            mesures[nom][cle] = mesurer([d[a] for d in s], [d[b] for d in s])

    # --- bruit du juge et egalites
    bruits = [d["juge_bruit"] for d in detail]
    bruit_moyen = sum(bruits) / len(bruits)
    bruit_par_reponse = [v["resultat"]["bruit_intra_juge"] for v in notes.values()]
    egalites = {k: sum(1 for d in detail if d[k] == "egales") for k in ("humain", "juge", "nu")}
    egalites_par_ecart = {k: dict(Counter(d["ecart"] for d in detail if d[k] == "egales"))
                          for k in ("humain", "juge", "nu")}

    # --- biais de position du modele nu, lu sur les rejeux bruts
    rejeux = [r for cid in ids for r in nu[cid]["rejeux"]]
    par_ordre = {}
    for ordre in ("A-B", "B-A"):
        rs = [r for r in rejeux if r["ordre_montre"] == ordre]
        par_ordre[ordre] = {
            "rejeux": len(rs),
            "premiere": sum(1 for r in rs if r["position_choisie"] == "premiere"),
            "seconde": sum(1 for r in rs if r["position_choisie"] == "seconde"),
            "egales": sum(1 for r in rs if r["position_choisie"] == "egales"),
        }
    # accord entre le choix (en A/B) du rejeu inverse et celui des rejeux droits, par paire
    stable = 0
    for cid in ids:
        rs = nu[cid]["rejeux"]
        inv = [r["choix"] for r in rs if r["ordre_montre"] == "B-A"]
        dro = [r["choix"] for r in rs if r["ordre_montre"] == "A-B"]
        if inv and dro and all(c == inv[0] for c in dro):
            stable += 1
    nu_unanimes = sum(1 for d in detail if d["nu_unanime"])

    # --- effet plafond de la grille : reponses a 12/12, paires ou les deux y sont
    a_12 = sum(1 for v in notes.values() if v["resultat"]["total_mean"] >= 12)
    paires_12_12 = sum(1 for d in detail if d["juge_total_A"] >= 12 and d["juge_total_B"] >= 12)
    egales_juge_12_12 = sum(1 for d in detail if d["juge"] == "egales"
                            and d["juge_total_A"] >= 12 and d["juge_total_B"] >= 12)
    plafond = {"reponses_a_12_sur_12": a_12, "reponses": len(notes),
               "paires_les_deux_a_12": paires_12_12, "egales_juge_dues_au_plafond": egales_juge_12_12}

    # --- ecart APPARIE entre modele nu et juge (memes 40 paires, memes indices de bootstrap)
    hx = [d["humain"] for d in detail]
    jx = [d["juge"] for d in detail]
    nx = [d["nu"] for d in detail]
    rng = random.Random(GRAINE_BOOTSTRAP)
    diffs = []
    n_d = len(detail)
    for _ in range(N_BOOTSTRAP):
        idx = [rng.randrange(n_d) for _ in range(n_d)]
        kj = kappa_cohen([hx[i] for i in idx], [jx[i] for i in idx])
        kn = kappa_cohen([hx[i] for i in idx], [nx[i] for i in idx])
        if kj is not None and kn is not None:
            diffs.append(kn - kj)
    diffs.sort()
    k_j = kappa_cohen(hx, jx)
    k_n = kappa_cohen(hx, nx)
    ecart_nu_juge = {
        "kappa_nu_moins_juge": round(k_n - k_j, 3),
        "ic95_apparie": [round(diffs[int(0.025 * len(diffs))], 3), round(diffs[int(0.975 * len(diffs))], 3)],
        "p_nu_superieur": round(sum(1 for x in diffs if x > 0) / len(diffs), 3),
        "note": "bootstrap apparie : memes tirages de paires pour les deux kappas ; graine et tirages du protocole",
    }

    # --- le plafond explique-t-il l'accord bas ? kappa humain-juge sans les paires 12-12
    hors_plafond = [d for d in detail if not (d["juge_total_A"] >= 12 and d["juge_total_B"] >= 12)]
    sans_plafond = {
        "paires": len(hors_plafond),
        "kappa_humain_juge": round(kappa_cohen([d["humain"] for d in hors_plafond], [d["juge"] for d in hors_plafond]), 3),
        "kappa_humain_juge_fin": round(kappa_cohen([d["humain"] for d in hors_plafond if d["ecart"] == "fin"],
                                                   [d["juge"] for d in hors_plafond if d["ecart"] == "fin"]), 3),
    }

    # --- les trois verites contestees
    contestees = {d["cas"]: {k: d[k] for k in ("verite", "humain", "juge", "nu")}
                  for d in detail if d["contestee"]}

    # --- protocole (dates lues dans les fichiers, pas inventees)
    dates_juge = sorted(v["horodatage"][:10] for v in notes.values())
    dates_nu = sorted(v["horodatage"][:10] for v in nu.values())
    protocole = {
        "jeu": f"{jeu}/paires.json (40 paires, seed_cotes 20260922)",
        "annotation_humaine": "annotations/comparaison-20260924.csv (1 annotateur, ordre seed 20260924)",
        "juge": {
            "modele": notes_doc["modele"], "n_rejeux": notes_doc["n_rejeux"],
            "seed_nominale": notes_doc.get("seed"), "seed_note": notes_doc.get("_seed_note"),
            "reponses_notees": len(notes), "appels": len(notes) * notes_doc["n_rejeux"],
            "dates": [dates_juge[0], dates_juge[-1]],
            "regle_egales": "|total_A - total_B| <= max(bruit_A, bruit_B) -> egales (ecrite avant la mesure)",
        },
        "modele_nu": {
            "modele": nu_doc["modele"], "n_rejeux": nu_doc["n_rejeux"],
            "rejeux_inverses": nu_doc["rejeux_inverses"], "system": nu_doc["system"],
            "question": nu_doc["question"], "paires_notees": len(nu),
            "appels": len(nu) * nu_doc["n_rejeux"], "dates": [dates_nu[0], dates_nu[-1]],
            "regle_preference": "majorite des 3 votes ; 'egales' si les trois different",
        },
        "bootstrap": {"tirages": N_BOOTSTRAP, "graine": GRAINE_BOOTSTRAP},
        "calcul": str(date.today()),
    }

    resultat = {
        "n": len(detail),
        "protocole": protocole,
        "bruit_intra_juge": {
            "moyen_par_paire_max_des_deux": round(bruit_moyen, 3),
            "moyen_par_reponse": round(sum(bruit_par_reponse) / len(bruit_par_reponse), 3),
            "reponses_a_bruit_nul": sum(1 for b in bruit_par_reponse if b == 0),
        },
        "egalites": egalites, "egalites_par_ecart": egalites_par_ecart,
        "modele_nu": {"biais_de_position": par_ordre, "paires_stables_sous_inversion": stable,
                      "paires_unanimes": nu_unanimes},
        "verites_contestees": contestees,
        "plafond": plafond,
        "ecart_nu_juge": ecart_nu_juge,
        "sans_plafond": sans_plafond,
        "mesures": mesures,
        "detail": detail,
    }
    sortie_json.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    sortie_md.write_text(rapport_md(resultat), encoding="utf-8")

    m = mesures["humain_vs_juge"]["tout"]
    print(f"LE CHIFFRE — humain ↔ juge : kappa {m['kappa']} (IC95 {m['kappa_ic95']}), "
          f"brut {m['accord_brut']}/{m['tranchees_par_les_deux']}, 3 classes {m['taux_3_classes']}")
    mn = mesures["humain_vs_nu"]["tout"]
    print(f"baseline modèle nu — humain ↔ nu : kappa {mn['kappa']} (IC95 {mn['kappa_ic95']}), "
          f"brut {mn['accord_brut']}/{mn['tranchees_par_les_deux']}")
    print(f"bruit intra-juge moyen par réponse {resultat['bruit_intra_juge']['moyen_par_reponse']:.2f}/12 "
          f"(max des deux, par paire : {bruit_moyen:.2f}) ; égalités {egalites}")
    print(f"écrit : {sortie_json.name}, {sortie_md.name}")
    return 0


def fmt_k(m: dict) -> str:
    if m["kappa"] is None:
        return "indéfini"
    ic = m["kappa_ic95"]
    return f"{m['kappa']:+.2f} [{ic[0]:+.2f} ; {ic[1]:+.2f}]" if ic else f"{m['kappa']:+.2f} [—]"


def fmt_brut(m: dict) -> str:
    if not m["tranchees_par_les_deux"]:
        return "—"
    return f"{m['accord_brut']}/{m['tranchees_par_les_deux']} ({m['taux_brut']:.0%})"


def fmt_3(m: dict) -> str:
    ic = m["taux_3_classes_ic95"]
    return f"{m['taux_3_classes']:.0%} [{ic[0]:.0%} ; {ic[1]:.0%}]" if ic else f"{m['taux_3_classes']:.0%}"


def rapport_md(r: dict) -> str:
    P, M = r["protocole"], r["mesures"]
    hj, hn, jv, jn = (M[k]["tout"] for k in ("humain_vs_juge", "humain_vs_nu", "juge_vs_verite", "juge_vs_nu"))
    L = []
    L.append(f"# Étalonnage du juge sur le jeu v3 — accord humain ↔ juge : kappa {fmt_k(hj)}")
    L.append("")
    L.append(f"> Calculé le {P['calcul']} par `calculer_accord.py --jeu jeu-v3`. {r['n']} paires, un seul "
             f"annotateur humain. Kappa de Cohen sur trois classes (A / B / les deux se valent), "
             f"intervalle de confiance à 95 % par bootstrap ({P['bootstrap']['tirages']} tirages, "
             f"graine {P['bootstrap']['graine']}). Le CADRE dit : sous 0,4 la grille est ambiguë, "
             f"au-dessus de 0,6 acceptable — et **on publie le chiffre quel qu'il soit**.")
    L.append("")
    L.append("## En une ligne")
    L.append("")
    L.append(f"- **Humain ↔ juge (LE chiffre)** : kappa **{fmt_k(hj)}**, accord brut sur les paires "
             f"tranchées par les deux {fmt_brut(hj)}, accord sur trois classes {fmt_3(hj)}.")
    L.append(f"- **Humain ↔ modèle nu (baseline b)** : kappa {fmt_k(hn)}, brut {fmt_brut(hn)}, "
             f"trois classes {fmt_3(hn)}.")
    L.append(f"- **Juge ↔ vérité-terrain du concepteur** : kappa {fmt_k(jv)}, brut {fmt_brut(jv)}.")
    L.append(f"- **Juge ↔ modèle nu** : kappa {fmt_k(jn)}, brut {fmt_brut(jn)}.")
    L.append("- Les taux « brut » ci-dessus ont des dénominateurs différents (chaque notateur choisit les "
             "paires qu'il tranche) : ils ne se comparent pas entre eux, seuls les kappas se comparent.")
    L.append(f"- Bruit intra-juge (baseline a) : {r['bruit_intra_juge']['moyen_par_reponse']:.2f} point sur 12 "
             f"en moyenne par réponse, {r['bruit_intra_juge']['reponses_a_bruit_nul']}/{P['juge']['reponses_notees']} "
             f"réponses à bruit nul. « Égales » : humain {r['egalites']['humain']}, juge {r['egalites']['juge']}, "
             f"modèle nu {r['egalites']['nu']} (sur {r['n']}).")
    L.append("")
    L.append("## Les mesures — net / fin et par domaine")
    L.append("")
    L.append("Lecture : kappa [IC95] · brut = accords / paires tranchées par les deux · 3 cl. = accord "
             "en comptant « égales » comme une classe. Sous-ensembles de 13 ou 14 paires : "
             "l'intervalle y est très large, c'est indicatif. **Les taux « brut » ne se comparent pas "
             "d'une ligne à l'autre** : leurs dénominateurs diffèrent (le juge s'abstient sur "
             f"{r['egalites']['juge']} paires, le modèle nu sur {r['egalites']['nu']}), et le sous-ensemble "
             "est choisi par le notateur qu'on évalue. Seul le kappa, sur les 40 paires, se compare.")
    L.append("")
    L.append("| Accord | tout (40) | net (13) | fin (27) | pro (13) | ONG (13) | course (14) |")
    L.append("|---|---|---|---|---|---|---|")
    for nom, _, _, lib in COMPARAISONS:
        cells = []
        for cle in SOUS_ENSEMBLES:
            m = M[nom][cle]
            cells.append(f"{fmt_k(m)}<br>brut {fmt_brut(m)}<br>3 cl. {m['taux_3_classes']:.0%}")
        L.append(f"| {lib} | " + " | ".join(cells) + " |")
    L.append("")
    nu = r["modele_nu"]
    ab, ba = nu["biais_de_position"]["A-B"], nu["biais_de_position"]["B-A"]
    L.append("## Le modèle nu et la position")
    L.append("")
    L.append(f"- Rejeux dans l'ordre A-B ({ab['rejeux']}) : première choisie {ab['premiere']}, seconde "
             f"{ab['seconde']}, égales {ab['egales']}. Rejeu inversé B-A ({ba['rejeux']}) : première "
             f"{ba['premiere']}, seconde {ba['seconde']}, égales {ba['egales']}.")
    L.append(f"- Paires aux trois votes unanimes (donc stables sous l'inversion, c'est la même quantité avec "
             f"un seul rejeu inversé sur trois) : {nu['paires_unanimes']}/{r['n']}.")
    L.append("")
    pl = r["plafond"]
    b_rate_ab = ab["seconde"] / ab["rejeux"] if ab["rejeux"] else 0
    b_rate_ba = ba["premiere"] / ba["rejeux"] if ba["rejeux"] else 0
    L.append("## Ce que la mesure a trouvé en route (à documenter, pas à corriger)")
    L.append("")
    sp, en = r["sans_plafond"], r["ecart_nu_juge"]
    L.append(f"- **La grille sature sur ce jeu.** {pl['reponses_a_12_sur_12']}/{pl['reponses']} réponses "
             f"reçoivent 12/12 en moyenne ; dans {pl['paires_les_deux_a_12']}/{r['n']} paires les deux réponses "
             f"sont à 12, et {pl['egales_juge_dues_au_plafond']} des {r['egalites']['juge']} « égales » du juge "
             f"viennent de là. Les deux réponses de chaque paire ont été écrites pour être envoyables : une grille "
             f"qui note une qualité absolue ne sépare pas deux bonnes réponses. La saturation est mesurée ; "
             f"qu'elle soit la cause principale est une inférence, et elle n'explique qu'une partie : sans les "
             f"{pl['paires_les_deux_a_12']} paires au plafond, le kappa humain ↔ juge passe de "
             f"{hj['kappa']:+.2f} à {sp['kappa_humain_juge']:+.2f} ({sp['paires']} paires ; sur les fines, "
             f"{sp['kappa_humain_juge_fin']:+.2f}), toujours sous 0,6.")
    L.append(f"- **Le modèle nu tranche toujours** ({r['egalites']['nu']} égales sur {r['n']}). Son kappa avec "
             f"l'humain dépasse celui de la grille de {en['kappa_nu_moins_juge']:+.2f}, mais l'écart apparié "
             f"(mêmes 40 paires, mêmes tirages) a pour IC95 [{en['ic95_apparie'][0]:+.2f} ; "
             f"{en['ic95_apparie'][1]:+.2f}] et P(nu > juge) = {en['p_nu_superieur']:.2f} : **on ne voit pas "
             f"la grille faire mieux que le modèle nu, et on ne peut pas non plus dire qu'elle fait moins bien.** "
             f"Ce qui est établi, c'est qu'elle s'abstient là où lui tranche.")
    L.append(f"- **Position, modèle nu** : B est choisie {b_rate_ab:.0%} du temps quand elle est montrée en "
             f"second ({ab['rejeux']} rejeux), {b_rate_ba:.0%} quand elle est montrée en premier "
             f"({ba['rejeux']} rejeux). Écart non distinguable de zéro à cette taille (z ≈ 1,2, rejeux groupés "
             f"par paire) ; le dispositif le mesurerait s'il était grand, il ne l'est pas.")
    L.append("")
    L.append("## Les trois vérités-terrain contestées (P-06, C-05, C-07)")
    L.append("")
    L.append("| paire | concepteur | humain | juge | modèle nu |")
    L.append("|---|---|---|---|---|")
    for cid, v in r["verites_contestees"].items():
        L.append(f"| {cid} | {v['verite']} | {v['humain']} | {v['juge']} | {v['nu']} |")
    L.append("")
    L.append("## Protocole exact")
    L.append("")
    J, N = P["juge"], P["modele_nu"]
    L.append(f"- Jeu : `{P['jeu']}`, écrit par une session Claude (Fable 5.1) avec l'auteur du dépôt, validé "
             f"par quatre relecteurs indépendants qui sont des sous-agents Claude Opus 5 en contexte frais "
             f"(`validation.md`). Les étiquettes net / fin ont été posées par le premier relecteur sur la version "
             f"v3a, puis confirmées 13/13 et 12/13 par les deux suivants sur v3b.")
    L.append(f"- Annotation humaine : `{P['annotation_humaine']}`. **L'annotateur est l'auteur du dépôt** ; il n'a "
             f"pas écrit la vérité-terrain (elle vient de la session de conception) et n'a jamais vu une note du "
             f"juge. Le nombre 20260924 est la graine de l'ordre d'affichage, pas une date : l'annotation est du "
             f"22/09/2026 (commit `c445db5` du dépôt privé), la notation machine du 23/09/2026.")
    L.append(f"- Juge `juge-par-grille` (6 critères 0-2) : modèle `{J['modele']}` (celui du harnais publié, "
             f"`llm_client.DEFAULT_MODEL`), N = {J['n_rejeux']} rejeux par réponse, {J['reponses_notees']} "
             f"réponses, {J['appels']} appels, du {J['dates'][0]} au {J['dates'][1]}. Le juge n'a reçu que la "
             f"situation et la réponse notée. Préférence par paire : {J['regle_egales']}.")
    L.append(f"- Seed : `{J['seed_nominale']}` est la seed nominale du harnais, loguée pour la traçabilité ; "
             f"**l'appel par l'Agent SDK n'expose ni température ni seed**, donc elle ne fige rien — le "
             f"non-déterminisme réel est ce que mesure le bruit intra-juge.")
    L.append(f"- Juge et modèle nu ont tourné en même temps (juge {J['dates'][0]} 07:51 → 08:32 UTC, nu "
             f"07:58 → 08:34 UTC) : aucun des deux ne lit les sorties de l'autre, l'ordre n'a pas d'importance.")
    L.append(f"- Modèle nu : même modèle `{N['modele']}`, sans grille ni sentinelles, consigne système "
             f"« {N['system']} », question « {N['question']} », N = {N['n_rejeux']} rejeux par paire dont "
             f"le rejeu {N['rejeux_inverses']} avec l'ordre d'affichage inversé, {N['paires_notees']} paires, "
             f"{N['appels']} appels, du {N['dates'][0]} au {N['dates'][1]}. Préférence : {N['regle_preference']}.")
    L.append(f"- Bootstrap : {P['bootstrap']['tirages']} tirages avec remise sur les paires, graine "
             f"{P['bootstrap']['graine']} ; percentiles 2,5 et 97,5 du kappa recalculé à chaque tirage.")
    L.append("- Règles d'« égales » et de préférence écrites avant de voir un résultat. **Depuis le début de "
             "l'annotation humaine**, rien n'a été retouché : ni le jeu, ni l'annotation, ni le modèle, ni les "
             "règles. Avant elle, le jeu a été réécrit deux fois pendant sa validation (`validation.md`), et "
             "une version a été refusée précisément parce qu'un chiffre (28/28) était trop bon.")
    L.append("- Seuils de lecture (0,4 ambiguë / 0,6 acceptable) : écrits dans le cadre de l'étalonnage le "
             "28/08/2026 (commit `e6c2b7f` du dépôt privé), avant tout jeu et toute mesure. Le fichier n'est "
             "pas public ; la date l'est par ce hash.")
    L.append("- Bruit intra-juge = écart-type de population (ddof = 0) des 3 totaux, comme dans le harnais. "
             "Avec n = 3 il est biaisé vers le bas, donc le seuil d'« égales » est plutôt serré ; sur ces "
             "données, 11 des 12 égales du juge sont des égalités exactes, la règle n'a joué que sur P-11.")
    L.append("")
    L.append("## Ce que le chiffre ne dit pas")
    L.append("")
    L.append("- **Un seul annotateur humain.** Le chiffre dit « le juge préfère comme cet humain », pas "
             "« comme les humains ». Un désaccord peut venir du juge, de la grille, ou de l'annotateur ; "
             "sans second annotateur on ne peut pas départager. Un kappa inter-annotateurs reste à faire.")
    L.append("- **Trois domaines de messages courts** (échanges pro, conduite de projet ONG, course à pied), "
             "réponses de 10 à 60 mots. Ce n'est pas de la revue de code, domaine du skill de démonstration "
             "du dépôt public : le chiffre ne se transporte pas tel quel.")
    L.append("- **Trois vérités-terrain contestées** (P-06, C-05, C-07) par deux relecteurs sur deux : la "
             "colonne « juge ↔ vérité-terrain » porte une opinion de conception sur ces trois paires, "
             "pas une mesure. Le tableau ci-dessus les isole.")
    L.append("- **Une règle mécanique résiduelle** vue par les relecteurs (`validation.md`) : « prends celle "
             "qui s'engage sur un acte daté » prédit une partie des vérités-terrain, surtout les 13 nettes. "
             "Si juge et humain suivent tous deux cette règle, l'accord monte sans prouver un jugement "
             "situé. La colonne « fin (27) » est celle qui en dépend le moins.")
    L.append("- **40 paires** : l'intervalle est large par construction. Les sous-ensembles (13-14 paires) "
             "ne tranchent rien seuls.")
    L.append("- **Le taux brut 19/22 n'est pas un score.** Il porte sur les paires que le juge a bien voulu "
             "trancher ; le juge choisit lui-même son dénominateur. Le kappa sur 40 est le chiffre.")
    L.append("- **Les justifications du juge sont des gabarits**, pas du texte libre : trois formules "
             "canoniques produites par l'agrégateur du harnais à partir des scores. Elles garantissent l'absence "
             "de verbatim, elles n'expliquent rien.")
    L.append("- **Deux chiffres de `validation.md` ne se recoupent pas** : « 12/12 · 28/28 » pour le premier "
             "relecteur sur v3a a des dénominateurs (12, 28) qui ne correspondent pas à la répartition 13 / 27, "
             "et la même passe de réécriture y est comptée « 27 paires fines réécrites » à un endroit et "
             "« 12 paires réécrites » à un autre (la liste nominative donne 12 réécritures de fond). La version "
             "v3a n'est pas conservée. C'est un document d'historique de la session de conception ; il est "
             "laissé tel quel et signalé ici.")
    L.append("- **La seed ne fige rien** (voir protocole) : deux relances de ce script sur de nouvelles "
             "notations donneraient des totaux différents, dans la marge du bruit publié.")
    L.append("")
    L.append(f"Détail paire par paire : `resultat.json` (clé `detail`).")
    return "\n".join(L) + "\n"


def main() -> int:
    if "--jeu" in sys.argv:
        return main_v3(sys.argv[sys.argv.index("--jeu") + 1])
    return main_v2()


if __name__ == "__main__":
    sys.exit(main())
