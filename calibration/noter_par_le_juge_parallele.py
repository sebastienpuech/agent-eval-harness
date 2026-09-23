#!/usr/bin/env python3
"""Version parallele de la notation par le juge.

La version sequentielle tournait a ~2 min par reponse (3 appels chacune), soit pres de
3 h pour 80 reponses. Les notations sont independantes les unes des autres : rien ne
justifie de les faire a la queue leu leu.

Prudence : un client par fil (rien ne dit que le client du harnais est partageable entre
threads), concurrence modeste pour ne pas se faire limiter, ecriture du fichier protegee
par un verrou et faite apres CHAQUE reponse — une coupure ne perd que le travail en cours.

Reprise : les reponses deja notees ne sont pas rejouees.

Deux jeux sont lisibles :
  - v2 (defaut) : reponses-paires.json  -> notes-du-juge.json, dans ce dossier ;
  - v3 : --jeu jeu-v3 -> jeu-v3/paires.json -> jeu-v3/notes-du-juge.json.
Dans les deux cas le juge ne voit QUE la situation et la reponse notee : ni profil (v2),
ni verite_terrain ni defaut (v3) ne lui sont transmis, et ils ne sont pas recopies dans
la sortie pour le v3 (l'analyse les relit dans paires.json).

Usage :  python noter_par_le_juge_parallele.py [n_rejeux] [n_fils] [--jeu jeu-v3]
"""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ICI = Path(__file__).resolve().parent
SCRIPTS = Path(__file__).resolve().parents[1] / "meta" / "skills" / "iterer-sur-retours" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import run_grid  # noqa: E402
from grade_grille import grade_variante  # noqa: E402
from lint_pii import lint_grid_scores  # noqa: E402
from llm_client import AgentSDKClient, DEFAULT_MODEL  # noqa: E402

_local = threading.local()
_verrou = threading.Lock()


def client_du_fil():
    if not hasattr(_local, "client"):
        _local.client = AgentSDKClient()
    return _local.client


def charger_v2(chemin: Path) -> dict:
    """{cid: {brief, domaine, A: {reponse, profil}, B: {...}}} — format natif du v2."""
    return json.loads(chemin.read_text(encoding="utf-8"))["paires"]


def charger_v3(chemin: Path) -> dict:
    """Meme forme que le v2, SANS profil, SANS verite_terrain, SANS defaut."""
    brut = json.loads(chemin.read_text(encoding="utf-8"))["paires"]
    return {
        p["id"]: {
            "brief": p["situation"], "domaine": p["domaine"], "ecart": p["ecart"],
            "A": {"reponse": p["reponse_A"], "profil": None},
            "B": {"reponse": p["reponse_B"], "profil": None},
        }
        for p in brut
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    jeu = None
    if "--jeu" in sys.argv:
        jeu = sys.argv[sys.argv.index("--jeu") + 1]
        args = [a for a in args if a != jeu]
    n = int(args[0]) if len(args) > 0 else 3
    fils = int(args[1]) if len(args) > 1 else 5

    if jeu:
        dossier = ICI / jeu
        paires = charger_v3(dossier / "paires.json")
        sortie = dossier / "notes-du-juge.json"
        note = ("Notes du juge-par-grille sur les 80 reponses du jeu v3 (2 par paire), N rejeux "
                "chacune. Produites APRES l'annotation humaine, sans y avoir acces. Le juge n'a "
                "recu que la situation et la reponse notee : ni verite_terrain, ni defaut, ni "
                "ecart. Le champ 'ecart' est recopie ici pour l'analyse seulement.")
    else:
        paires = charger_v2(ICI / "reponses-paires.json")
        sortie = ICI / "notes-du-juge.json"
        note = ("Notes du juge-par-grille sur les 80 reponses (2 par situation), N rejeux "
                "chacune. Produites APRES l'annotation humaine, sans y avoir acces. Le champ "
                "'profil' sert a l'analyse, le juge ne l'a jamais vu.")

    if sortie.exists():
        out = json.loads(sortie.read_text(encoding="utf-8"))
    else:
        out = {
            "_note": note,
            "modele": DEFAULT_MODEL, "n_rejeux": n,
            "seed": run_grid.SEED,
            "_seed_note": ("seed nominale du harnais (run_grid.SEED), loguee pour la "
                           "tracabilite ; l'appel via Agent SDK n'expose ni temperature ni "
                           "seed, le bruit reel se lit dans bruit_intra_juge"),
            "notes": {},
        }

    a_faire = [(cid, cote) for cid in sorted(paires) for cote in ("A", "B")
               if f"{cid}.{cote}" not in out["notes"]]
    total = len(paires) * 2
    print(f"{len(out['notes'])}/{total} deja notees ; {len(a_faire)} a faire "
          f"sur {fils} fils, N={n}, modele={out['modele']}, sortie={sortie}")

    def travailler(t):
        cid, cote = t
        p = paires[cid]
        r = grade_variante(client_du_fil(), p[cote]["reponse"],
                           f"Situation : {p['brief']}", n=n)
        return cid, cote, p, r

    erreurs = []
    with ThreadPoolExecutor(max_workers=fils) as pool:
        futurs = {pool.submit(travailler, t): t for t in a_faire}
        for fut in as_completed(futurs):
            t = futurs[fut]
            try:
                cid, cote, p, r = fut.result()
            except Exception as exc:
                erreurs.append((t, repr(exc)[:120]))
                print(f"  ECHEC {t[0]}.{t[1]} : {repr(exc)[:90]}")
                continue
            with _verrou:
                enreg = {
                    "cas": cid, "cote": cote, "domaine": p["domaine"], "resultat": r,
                    "horodatage": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                if jeu:
                    enreg["ecart"] = p["ecart"]
                else:
                    enreg["profil"] = p[cote]["profil"]
                out["notes"][f"{cid}.{cote}"] = enreg
                sortie.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
                fait = len(out["notes"])
            etiquette = p[cote]["profil"] or p.get("ecart", "")
            print(f"  {cid}.{cote} [{etiquette:8}] total={r['total_mean']} "
                  f"bruit={r['bruit_intra_juge']}  ({fait}/{total})", flush=True)

    print(f"\n{len(out['notes'])}/{total} notees")
    # Garde-fou PII du harnais sur les justifications, meme forme que grid_scores.json.
    problemes = lint_grid_scores({"variantes": {k: v["resultat"] for k, v in out["notes"].items()}})
    print(f"lint PII : {len(problemes)} violation(s)")
    if erreurs:
        print(f"{len(erreurs)} echec(s) — relancer le script les reprendra :")
        for t, e in erreurs[:5]:
            print(f"  {t[0]}.{t[1]} : {e}")
        return 1
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())
