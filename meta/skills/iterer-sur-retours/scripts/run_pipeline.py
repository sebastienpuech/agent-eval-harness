#!/usr/bin/env python3
"""run_pipeline.py -- chaine complete V1-noyau (branche factuelle) de bout en bout.

Etape 0 -> fork -> classer -> geler held-out (registre unique) -> matrice + anti-silence ->
G2 contrat -> gate regression -> rapport -> handoff.

MODE DEGRADE (patch SIM-006) : le corpus tableur est HORS-REPO (feasibility -> S3). On ne peut
donc pas invoquer le classificateur LLM sur les vrais retours. Le run tourne sur la FIXTURE de
classification golden (`evals/fixtures/tableur_classified.json`) et marque `degraded=true` dans
`memory/interactions.jsonl`. La chaine, elle, est reelle (fork/holdout/matrice/gate/contrat).

Produit dans .iter/ : classification.json, matrix.csv, detector_log.json,
auto_improver_call.json, regression_report.json, rapport.md  (+ signal/holdout.txt).

CLI :
  python run_pipeline.py                 # gate sur fixture whack-a-mole (exerce le refus S4)
  python run_pipeline.py --clean         # gate sur fixture clean (ship=true)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from build_contract import build_contract
from build_matrix import build_matrix, load_schema, write_matrix
from detector_log import build_detector_log
from fork import compute_fork
from regression_gate import evaluate
from split_holdout import REGLES_SEED, build_registry, write_registry

SKILL_ROOT = Path(__file__).resolve().parent.parent
ITER = SKILL_ROOT / ".iter"
SIGNAL = SKILL_ROOT / "signal"
FIXTURES = SKILL_ROOT / "evals" / "fixtures"
MEMORY = SKILL_ROOT / "memory"


def _run_id_from(seed: str) -> str:
    # Pas de Math.random ni d'horloge : id derive du contenu (reproductible).
    return "ir_" + format(abs(hash(seed)) % (16 ** 8), "08x")


def run(clean: bool = False) -> dict:
    ITER.mkdir(exist_ok=True)
    steps = []

    # --- Etape 0 + classification (degrade : fixture, corpus hors-repo) ---
    classif = json.loads((FIXTURES / "tableur_classified.json").read_text(encoding="utf-8"))
    fork = compute_fork(classif)
    classification = {
        "regime": fork["regime"],
        "part_oracle_mecanique": fork["part_oracle_mecanique"],
        "n_retours_normalises": fork["n_retours_normalises"],
        "familles": fork["familles"],
        "items": classif["items"],
        "degraded": True,
        "degraded_raison": "corpus tableur hors-repo -> classification issue de la fixture golden",
    }
    (ITER / "classification.json").write_text(
        json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")
    steps.append(f"fork={fork['regime']} part_oracle={fork['part_oracle_mecanique']}")

    # --- Held-out (registre unique) ---
    case = json.loads((SKILL_ROOT / "evals" / "cases" / "tableur.json").read_text(encoding="utf-8"))
    holdout = case["corpus"]["held_out_candidats"]
    registry = build_registry(case, holdout, REGLES_SEED)  # leve si incoherent
    write_registry(registry)
    steps.append(f"held-out={sorted(registry['holdout'])}")

    # --- Signal factuel : matrice + anti-silence ---
    schema = load_schema()
    matrix = build_matrix(registry, schema)
    write_matrix(matrix)
    detlog = build_detector_log(registry, schema)
    (ITER / "detector_log.json").write_text(
        json.dumps(detlog, ensure_ascii=False, indent=2), encoding="utf-8")
    n_silent = sum(1 for e in detlog["entries"] if e["etat"] == "non_detecte")
    steps.append(f"anti-silence={n_silent} non_detecte")

    # --- G2-factuel : contrat (0 patch code) ---
    contract = build_contract(registry, skill_path="chemin/vers/skill-tableur-demo")
    (ITER / "auto_improver_call.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    steps.append(f"contrat={contract['delegation_status']} (held-out exclu)")

    # --- Gate regression ---
    fx = "regression_clean.json" if clean else "regression_whack_a_mole.json"
    report = evaluate(json.loads((FIXTURES / fx).read_text(encoding="utf-8")))
    (ITER / "regression_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    steps.append(f"ship={report['ship']} delta_net={report['delta_net_holdout']:+}")

    # --- Rapport ---
    rapport = _rapport(classification, registry, matrix, detlog, contract, report, clean)
    (ITER / "rapport.md").write_text(rapport, encoding="utf-8")

    # --- Memoire (allowlist, degraded=true) ---
    routage = {}
    for it in classif["items"]:
        routage[it["type"]] = routage.get(it["type"], 0) + 1
    line = {
        "run_id": _run_id_from(fx + str(holdout)),
        "skill_cible": classif["skill_cible"], "regime": fork["regime"],
        "part_oracle": fork["part_oracle_mecanique"], "n_retours": fork["n_retours_normalises"],
        "routage": routage, "holdout_n": len(holdout),
        "delta_net": report["delta_net_holdout"], "significatif": True,
        "ship": report["ship"], "degraded": True,
    }
    MEMORY.mkdir(exist_ok=True)
    with (MEMORY / "interactions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

    return {"steps": steps, "report": report, "rapport_path": ITER / "rapport.md"}


def _rapport(classif, registry, matrix, detlog, contract, report, clean) -> str:
    counts = {}
    for it in classif["items"]:
        counts[it["famille"]] = counts.get(it["famille"], 0) + 1
    nf = [(c["rule_id"], c["case_id"]) for c in matrix["cells"] if c["status"] == "NOT_FOUND"]
    aps = report["anti_patterns"]
    L = []
    L.append("# Rapport iterer-sur-retours -- tableur (V1-noyau)\n")
    L.append("> Run DEGRADE : corpus tableur hors-repo -> classification issue de la fixture golden. "
             "Chaine (fork/held-out/matrice/gate/contrat) reelle.\n")
    L.append("## Fork")
    L.append(f"- regime = **{classif['regime']}** ; part_oracle_mecanique = "
             f"{classif['part_oracle_mecanique']} (seuil factuel 0.5)\n")
    L.append("## Classification (par famille)")
    L.append(f"- {counts}  (total {classif['n_retours_normalises']}, completude OK)\n")
    L.append("## Held-out (registre unique)")
    L.append(f"- porteurs = {sorted(registry['holdout'])} ; exclut C21/C32 (cas de retour)\n")
    L.append("## Signal factuel")
    L.append(f"- NOT_FOUND (hors denominateur, anti-silence) : {[f'{r}x{c}' for r, c in nf]}")
    L.append(f"- attendu_par_cas DERIVE : {matrix['attendu_derive']}")
    if matrix["a_valider_humain"]:
        L.append(f"- a_valider_humain : {matrix['a_valider_humain']}")
    L.append("")
    L.append("## Delegation (G2-factuel)")
    L.append(f"- contrat produit = auto_improver_call.json ; statut = **{contract['delegation_status']}**")
    L.append(f"- test_cases = {contract['test_case_ids']} (held-out EXCLU) ; **0 patch de code**\n")
    L.append("## Gate regression (held-out)")
    L.append(f"- delta_net = {report['delta_net_holdout']:+} ; regression_suite = "
             f"{report['regression_suite']} ; **ship = {report['ship']}**")
    if aps:
        for ap in aps:
            L.append(f"- ANTI-PATTERN **{ap['type']}** : {ap['evidence']}")
            L.append(f"  - sur-generalisation : {ap['sur_generalisation']}")
        L.append(f"- ERROR-ANALYSIS : lire les traces de {report['cas_regresses_error_analysis']} "
                 "(on ne fait pas confiance au delta sans les traces)")
    L.append("")
    L.append("## Budget tokens")
    L.append("- 0 token LLM : run deterministe sur fixtures (classificateur non invoque, corpus hors-repo). "
             "En run reel, le budget de la passe de classification par batch serait affiche ici.\n")
    return "\n".join(L)


if __name__ == "__main__":
    res = run(clean="--clean" in sys.argv)
    print("=== chaine complete ===")
    for s in res["steps"]:
        print(f"  - {s}")
    print(f"\n[OK] rapport : {res['rapport_path'].relative_to(SKILL_ROOT)}")
