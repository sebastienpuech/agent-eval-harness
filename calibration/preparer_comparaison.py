#!/usr/bin/env python3
"""Construit la page de comparaison deux a deux — jeu v3 (jeu-v3/paires.json).

Un ecran = une situation + deux reponses. L'annotateur choisit celle qu'il enverrait, ou
declare qu'elles se valent. Ordre des paires et cote gauche/droite tires au sort par une seed
loguee ; la seed est rejetee si elle aligne 4 paires du meme domaine d'affilee.

La verite-terrain, l'ecart et le defaut restent dans paires.json, jamais dans la page ni dans
le fichier d'ordre.

Usage :  python preparer_comparaison.py [seed]
Sortie :  jeu-v3/annotations/comparer.html  +  jeu-v3/annotations/comparaison-<seed>.ordre.json
(le jeu v2 et son dossier annotations/ ne sont plus touches par ce script depuis le 22/09/2026)
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ICI = Path(__file__).resolve().parent
PAIRES = ICI / "jeu-v3" / "paires.json"
DOSSIER = ICI / "jeu-v3" / "annotations"
SERIE_MAX = 3  # au-dela : la seed est rejetee (effet d'entrainement d'un domaine sur les notes)
DESEQUILIBRE_MAX = 4  # 1re reponse a gauche entre 16 et 24 fois sur 40, sinon seed rejetee

GABARIT = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Comparaison — etalonnage du juge</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; max-width: 900px;
         margin: 0 auto; padding: 24px 16px 96px; line-height: 1.55; }
  header { display: flex; justify-content: space-between; align-items: baseline;
           border-bottom: 1px solid #8884; padding-bottom: 8px; margin-bottom: 18px; }
  h1 { font-size: 15px; font-weight: 600; margin: 0; letter-spacing: .02em; }
  #avancement { font-variant-numeric: tabular-nums; font-size: 14px; opacity: .75; }
  .barre { height: 3px; background: #8883; border-radius: 2px; margin-bottom: 26px; }
  .barre > div { height: 100%; background: currentColor; border-radius: 2px; transition: width .2s; }
  .etiquette { font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
               opacity: .6; margin-bottom: 5px; }
  .situation { font-size: 16px; margin-bottom: 26px; }
  .paire { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .choix { border: 1px solid #8886; border-radius: 10px; padding: 18px 18px 16px;
           cursor: pointer; background: transparent; color: inherit; font: inherit;
           text-align: left; display: flex; flex-direction: column; gap: 12px; min-height: 150px; }
  .choix:hover { background: #8881; border-color: #8889; }
  .choix .texte { font-size: 16px; flex: 1; }
  .choix .touche { font-size: 11px; opacity: .5; letter-spacing: .06em; }
  .egales { margin-top: 14px; text-align: center; }
  .egales button { font: inherit; font-size: 13px; padding: 8px 18px; border-radius: 8px;
                   border: 1px solid #8886; background: transparent; color: inherit; cursor: pointer; }
  .egales button:hover { background: #8881; }
  footer { position: fixed; bottom: 0; left: 0; right: 0; padding: 10px 16px; background: Canvas;
           border-top: 1px solid #8884; display: flex; justify-content: space-between;
           align-items: center; font-size: 13px; }
  footer button { font: inherit; padding: 7px 14px; border-radius: 6px; cursor: pointer;
                  border: 1px solid #8886; background: transparent; color: inherit; }
  footer button:disabled { opacity: .35; cursor: default; }
  footer button.fort { background: currentColor; color: Canvas; border-color: currentColor; }
  #fini { display: none; text-align: center; padding: 56px 0; }
  kbd { font: inherit; font-size: 11px; border: 1px solid #8886; border-radius: 4px;
        padding: 1px 5px; opacity: .8; }
  @media (max-width: 680px) { .paire { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<header>
  <h1>Laquelle enverrais-tu, toi, dans cette situation&nbsp;?</h1>
  <span id="avancement"></span>
</header>
<div class="barre"><div id="progression" style="width:0"></div></div>

<main id="ecran">
  <div class="etiquette">La situation</div>
  <div class="situation" id="situation"></div>

  <div class="etiquette">Les deux reponses possibles</div>
  <div class="paire">
    <button class="choix" id="btnG" onclick="choisir('gauche')">
      <span class="texte" id="texteG"></span><span class="touche">← ou A</span>
    </button>
    <button class="choix" id="btnD" onclick="choisir('droite')">
      <span class="texte" id="texteD"></span><span class="touche">→ ou B</span>
    </button>
  </div>
  <div class="egales">
    <button onclick="choisir('egales')">Les deux se valent <kbd>Espace</kbd></button>
  </div>
</main>

<div id="fini">
  <p><strong>40 comparaisons faites.</strong></p>
  <p><button class="fort" onclick="telecharger()">Telecharger le resultat</button></p>
</div>

<footer>
  <span>Clique celle que tu enverrais, ou <kbd>A</kbd> / <kbd>B</kbd> / <kbd>Espace</kbd></span>
  <span>
    <button id="precedent" onclick="reculer()">Precedent</button>
  </span>
</footer>

<script>
const PAIRES = __DONNEES__;
const SEED = "__SEED__";
const CLE = "etalonnage-comparaison-" + SEED;

let i = 0;
// Reprise entre deux ouvertures via localStorage ; s'il est indisponible (page ouverte hors
// file:// ou http://, navigation privee), on continue en memoire et le CSV reste telechargeable.
let choix = {};
try { choix = JSON.parse(localStorage.getItem(CLE) || "{}"); } catch (e) { choix = {}; }

function sauver() { try { localStorage.setItem(CLE, JSON.stringify(choix)); } catch (e) {} }
function nbFaits() { return PAIRES.filter(p => choix[p.id]).length; }

function dessiner() {
  if (i >= PAIRES.length) { terminer(); return; }
  const p = PAIRES[i];
  document.getElementById("situation").textContent = p.situation;
  document.getElementById("texteG").textContent = p.gauche;
  document.getElementById("texteD").textContent = p.droite;
  document.getElementById("avancement").textContent = `${nbFaits()} / ${PAIRES.length}`;
  document.getElementById("progression").style.width = (100 * nbFaits() / PAIRES.length) + "%";
  document.getElementById("precedent").disabled = (i === 0);
}

function choisir(quoi) {
  choix[PAIRES[i].id] = quoi;
  sauver();
  i++;
  dessiner();
}

function reculer() { if (i > 0) { i--; dessiner(); } }

document.addEventListener("keydown", e => {
  if (i >= PAIRES.length) return;
  const k = e.key.toLowerCase();
  if (k === "a" || e.key === "ArrowLeft") { e.preventDefault(); choisir("gauche"); }
  else if (k === "b" || e.key === "ArrowRight") { e.preventDefault(); choisir("droite"); }
  else if (e.key === " " || e.code === "Space") { e.preventDefault(); choisir("egales"); }
});

function terminer() {
  document.getElementById("ecran").style.display = "none";
  document.querySelector("footer").style.display = "none";
  document.getElementById("fini").style.display = "block";
}

function telecharger() {
  const lignes = ["id;choix;cote_gauche;cote_droite"];
  PAIRES.forEach(p => lignes.push([p.id, choix[p.id] || "", p.idG, p.idD].join(";")));
  const blob = new Blob(["﻿" + lignes.join("\r\n")], {type: "text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "comparaison-" + SEED + ".csv";
  a.click();
}

// Reprise : on repart au premier non fait.
const premierNonFait = PAIRES.findIndex(p => !choix[p.id]);
i = premierNonFait === -1 ? PAIRES.length : premierNonFait;
dessiner();
</script>
</body>
</html>
"""


def serie_max(ids, paires):
    """Longueur de la plus longue suite de paires d'un meme domaine dans cet ordre."""
    pire = cour = 0
    prec = None
    for cid in ids:
        dom = paires[cid]["domaine"]
        cour = cour + 1 if dom == prec else 1
        pire = max(pire, cour)
        prec = dom
    return pire


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else int(date.today().strftime("%Y%m%d"))
    paires = {p["id"]: p for p in json.loads(PAIRES.read_text(encoding="utf-8"))["paires"]}
    ids = sorted(paires)
    rng = random.Random(seed)
    rng.shuffle(ids)
    if (serie := serie_max(ids, paires)) > SERIE_MAX:
        print(f"seed {seed} rejetee : {serie} paires du meme domaine d'affilee "
              f"(max {SERIE_MAX}). Relance avec une autre seed : "
              f"python preparer_comparaison.py {seed + 1}")
        return 2

    donnees, ordre = [], {}
    gauche_a = 0
    for cid in ids:
        p = paires[cid]
        inverse = rng.random() < 0.5
        g, d = ("B", "A") if inverse else ("A", "B")
        gauche_a += (g == "A")
        donnees.append({"id": cid, "situation": p["situation"],
                        "gauche": p["reponse_" + g], "droite": p["reponse_" + d],
                        "idG": g, "idD": d})
        ordre[cid] = {"gauche": g, "droite": d, "domaine": p["domaine"]}

    if abs(gauche_a - len(ids) / 2) > DESEQUILIBRE_MAX:
        print(f"seed {seed} rejetee : 1re reponse a gauche {gauche_a} fois sur {len(ids)} "
              f"(ecart max a la moitie : {DESEQUILIBRE_MAX}). Relance : "
              f"python preparer_comparaison.py {seed + 1}")
        return 2

    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / f"comparaison-{seed}.ordre.json").write_text(
        json.dumps({"seed": seed, "ordre_des_cas": ids, "cotes": ordre},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    html = (GABARIT.replace("__DONNEES__", json.dumps(donnees, ensure_ascii=False))
                   .replace("__SEED__", str(seed)))
    page = DOSSIER / "comparer.html"
    page.write_text(html, encoding="utf-8")

    print(f"seed {seed} | {len(donnees)} paires")
    print(f"cote gauche : {gauche_a} fois la 1re reponse, {len(donnees) - gauche_a} fois la 2nde")
    print(f"page : {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
