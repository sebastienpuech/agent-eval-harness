#!/usr/bin/env python3
"""Baseline (b) du CADRE : le modele NU, sans grille ni sentinelles.

Le meme modele que le juge (llm_client.DEFAULT_MODEL) voit la situation et les deux
reponses, et repond a la question posee a l'annotateur humain : « Laquelle enverrais-tu,
toi, dans cette situation ? » — premiere, seconde, ou egales. Aucune grille, aucun critere,
aucune consigne de style : juste la question et le format de reponse.

N = 3 rejeux par paire. Sur le rejeu n° 2 l'ordre d'affichage est INVERSE (B montree en
premier) pour que le biais de position se mesure au lieu de se cacher. Chaque rejeu logue
l'ordre montre, la reponse brute et sa traduction en A / B / egales.

Preference retenue par paire (regle ecrite AVANT de voir un resultat) : la majorite des
3 votes ; si les 3 votes different (A, B, egales), la paire est « egales ».

Le modele nu ne voit jamais verite_terrain, defaut ni ecart. Ecriture apres chaque paire,
reprise sans rejouer ce qui est fait.

Usage :  python noter_modele_nu.py [n_rejeux] [n_fils]
Sortie :  notes-modele-nu.json (dans ce dossier)
"""
from __future__ import annotations

import json
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ICI = Path(__file__).resolve().parent
SCRIPTS = Path(__file__).resolve().parents[2] / "meta" / "skills" / "iterer-sur-retours" / "scripts"
PAIRES = ICI / "paires.json"
SORTIE = ICI / "notes-modele-nu.json"

sys.path.insert(0, str(SCRIPTS))
from llm_client import AgentSDKClient, DEFAULT_MODEL  # noqa: E402

QUESTION = "Laquelle enverrais-tu, toi, dans cette situation ?"
SYSTEM = ("Tu lis une situation et deux reponses possibles. On te pose une question de "
          "choix. Reponds par un seul mot, sans rien d'autre : PREMIERE, SECONDE ou EGALES.")
REJEU_INVERSE = {2}  # numeros (1..n) des rejeux ou B est montree en premier

_local = threading.local()
_verrou = threading.Lock()


def client_du_fil():
    if not hasattr(_local, "client"):
        _local.client = AgentSDKClient()
    return _local.client


def message(situation: str, premiere: str, seconde: str) -> str:
    return (f"Situation :\n{situation}\n\n"
            f"Premiere reponse :\n{premiere}\n\n"
            f"Seconde reponse :\n{seconde}\n\n"
            f"{QUESTION} Reponds PREMIERE, SECONDE ou EGALES.")


def lire(brut: str) -> str | None:
    """'PREMIERE' / 'SECONDE' / 'EGALES' -> 'premiere' / 'seconde' / 'egales' ; None si illisible."""
    t = brut.strip().upper()
    t = t.replace("É", "E").replace("È", "E").replace("Ê", "E")
    m = re.search(r"\b(PREMIERE|SECONDE|EGALES?|DEUXIEME)\b", t)
    if not m:
        return None
    mot = m.group(1)
    if mot == "DEUXIEME":
        return "seconde"
    if mot.startswith("EGALE"):
        return "egales"
    return mot.lower()


def traduire(position: str, inverse: bool) -> str:
    if position == "egales":
        return "egales"
    premiere_est = "B" if inverse else "A"
    seconde_est = "A" if inverse else "B"
    return premiere_est if position == "premiere" else seconde_est


def preference(votes: list[str]) -> str:
    c = Counter(votes)
    gagnant, nb = c.most_common(1)[0]
    return gagnant if nb >= 2 else "egales"


def noter_paire(client, p: dict, n: int) -> dict:
    rejeux = []
    for k in range(1, n + 1):
        inverse = k in REJEU_INVERSE
        prem, sec = (p["reponse_B"], p["reponse_A"]) if inverse else (p["reponse_A"], p["reponse_B"])
        brut = client.complete_sync(SYSTEM, message(p["situation"], prem, sec))
        pos = lire(brut)
        if pos is None:
            raise ValueError(f"reponse illisible : {brut[:80]!r}")
        rejeux.append({"rejeu": k, "ordre_montre": "B-A" if inverse else "A-B",
                       "position_choisie": pos, "choix": traduire(pos, inverse),
                       "brut": brut.strip()[:40]})
    votes = [r["choix"] for r in rejeux]
    return {"rejeux": rejeux, "votes": votes, "preference": preference(votes),
            "unanime": len(set(votes)) == 1}


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    fils = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if not (REJEU_INVERSE & set(range(1, n + 1))):
        print("ERREUR : aucun rejeu inverse dans la plage demandee", file=sys.stderr)
        return 2

    paires = {p["id"]: p for p in json.loads(PAIRES.read_text(encoding="utf-8"))["paires"]}
    if SORTIE.exists():
        out = json.loads(SORTIE.read_text(encoding="utf-8"))
    else:
        out = {
            "_note": ("Baseline (b) du CADRE : le modele nu, sans grille ni sentinelles, repond "
                      "a la question de l'annotateur humain sur les 40 paires du jeu v3. "
                      "N rejeux par paire, ordre inverse sur les rejeux listes dans "
                      "'rejeux_inverses'. Le modele n'a vu que la situation et les deux reponses. "
                      "Preference = majorite des votes, 'egales' si les trois different."),
            "modele": DEFAULT_MODEL, "n_rejeux": n,
            "rejeux_inverses": sorted(REJEU_INVERSE),
            "system": SYSTEM, "question": QUESTION,
            "_seed_note": ("l'appel via Agent SDK n'expose ni temperature ni seed ; la "
                           "variabilite se lit dans 'unanime' et 'votes'"),
            "notes": {},
        }

    a_faire = [cid for cid in sorted(paires) if cid not in out["notes"]]
    total = len(paires)
    print(f"{len(out['notes'])}/{total} deja notees ; {len(a_faire)} a faire sur {fils} fils, "
          f"N={n}, modele={out['modele']}")

    def travailler(cid):
        return cid, noter_paire(client_du_fil(), paires[cid], n)

    erreurs = []
    with ThreadPoolExecutor(max_workers=fils) as pool:
        futurs = {pool.submit(travailler, c): c for c in a_faire}
        for fut in as_completed(futurs):
            cid = futurs[fut]
            try:
                cid, r = fut.result()
            except Exception as exc:
                erreurs.append((cid, repr(exc)[:120]))
                print(f"  ECHEC {cid} : {repr(exc)[:90]}")
                continue
            with _verrou:
                out["notes"][cid] = {
                    "cas": cid, "domaine": paires[cid]["domaine"], "ecart": paires[cid]["ecart"],
                    **r,
                    "horodatage": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                fait = len(out["notes"])
            print(f"  {cid} votes={r['votes']} -> {r['preference']}  ({fait}/{total})", flush=True)

    print(f"\n{len(out['notes'])}/{total} notees")
    if erreurs:
        print(f"{len(erreurs)} echec(s) — relancer le script les reprendra :")
        for c, e in erreurs[:5]:
            print(f"  {c} : {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
