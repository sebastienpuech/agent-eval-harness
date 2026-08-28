#!/usr/bin/env python3
"""run_pass_skill.py -- passe iterer PAR SKILL, bout en bout (branche jugement V1).

Ce qui manquait à iterer : une entrée « lance une passe sur le skill X » (le run_pipeline.py était
une démo tableur figée). Ici : corpus réel -> normalize -> classify (Opus) -> fork -> si jugement,
génère un remède (principe+exemple, Opus) + mesure via juge-par-grille (Opus) -> écrit dans .iter/
les artefacts que amelioration_continue consomme (classification.json, regression_report.json,
patch_jugement.json).

Confidentialité : corpus lu en headers only (adapt_jsonl_header_prose) ; remède + paires = exemples
générés (aucune donnée réelle). Tous les appels LLM = Opus forfait Max (llm_client). Client injectable.

CLI :
  python run_pass_skill.py --skill demo-revue --corpus <cases.jsonl> --skill-md <SKILL.md> [--sample 12]
  python run_pass_skill.py --self-test        # fake client, déterministe, 0 LLM
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import grade_grille
import run_grid
from classify import classify_all
from normalize_feedback import adapt_jsonl_header_prose

SKILL_ROOT = Path(__file__).resolve().parent.parent
ITER = SKILL_ROOT / ".iter"


def generate_remede(client, theme: str) -> dict:
    system = ("Tu es l'agent remède-jugement d'iterer. À partir d'un thème de ratés de JUGEMENT sur "
              "un skill de revue, produis un PRINCIPE scopé (POURQUOI + QUAND + QUAND PAS) + un EXEMPLE "
              "contrasté ❌->✅ (résumé, 0 verbatim). Append-only. Réponds UNIQUEMENT en JSON : "
              "{\"titre\": str, \"principe\": str, \"exemple_contraste\": str}.")
    return grade_grille.extract_json(client.complete_sync(system, "Thème des ratés : " + theme))


def generate_holdout_pairs(client, principe: str, n_pairs: int = 2) -> dict:
    system = ("À partir d'un PRINCIPE de revue, produis " + str(n_pairs) + " paires "
              "d'exemples de réponses courtes (held-out) : `coherent` respecte le principe, `fragmente` "
              "le viole. Zéro PII, situations génériques. Réponds UNIQUEMENT en JSON : "
              "{\"p1\": {\"coherent\": str, \"fragmente\": str}, \"p2\": {\"coherent\": str, \"fragmente\": str}}.")
    return grade_grille.extract_json(client.complete_sync(system, "Principe : " + principe[:800]))


def _dominant_jugement_theme(classif: dict) -> str:
    d_items = [i for i in classif["items"] if i.get("famille") == "D"]
    if not d_items:
        return ""
    return " ; ".join(dict.fromkeys(i["resume"] for i in d_items))[:600]  # thèmes dédupliqués


def run(client, skill: str, corpus_path: Path, skill_md_path: Path, sample: int = 12) -> dict:
    ITER.mkdir(exist_ok=True)
    raw = Path(corpus_path).read_text(encoding="utf-8")
    items = adapt_jsonl_header_prose(raw)
    skill_md = Path(skill_md_path).read_text(encoding="utf-8")

    classif = classify_all(client, items[:sample], skill_md)             # (Opus)
    n_oracle = sum(1 for i in classif["items"] if i["famille"] in ("A", "B"))
    regime = "factuel" if n_oracle / max(1, len(classif["items"])) >= 0.5 else \
             ("jugement" if sum(1 for i in classif["items"] if i["famille"] == "D") else "mixte")
    classification = {"regime": regime, "n_retours_normalises": len(classif["items"]),
                      "familles": classif["familles"], "items": classif["items"], "degraded": False}
    (ITER / "classification.json").write_text(json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")

    theme = _dominant_jugement_theme(classif)
    if not theme:
        (ITER / "pass_result.json").write_text(json.dumps({"regime": regime, "branche": "rien-a-faire",
            "raison": "aucun retour jugement dans l'échantillon"}, ensure_ascii=False), encoding="utf-8")
        return {"branche": "rien-a-faire", "regime": regime}

    patch = generate_remede(client, theme)                               # (Opus) principe+exemple
    pairs = generate_holdout_pairs(client, patch["principe"])            # (Opus) held-out illustratif
    variantes = {}
    for pid, p in pairs.items():
        variantes[f"{pid}_coherent"] = {"output": p["coherent"], "context": "contexte : reponse courte dans un fil de revue"}
        variantes[f"{pid}_fragmente"] = {"output": p["fragmente"], "context": "contexte : reponse courte dans un fil de revue"}
    scores = grade_grille.grade_all(client, variantes, n=2)              # (Opus) juge-par-grille

    deltas = {}
    for pid in pairs:
        c = scores["variantes"][f"{pid}_coherent"]["total_mean"]
        f = scores["variantes"][f"{pid}_fragmente"]["total_mean"]
        deltas[pid] = round((c - f) / 12, 4)
    delta_net = round(sum(deltas.values()) / len(deltas), 4)
    reg_suite = round(sum(1 for d in deltas.values() if d >= 0) / len(deltas), 4)
    report = {"signal": "grille_jugement", "delta_net_holdout": delta_net, "deltas_par_cas": deltas,
              "regression_suite": reg_suite, "ship": delta_net >= 0 and reg_suite == 1.0,
              "cas_regresses_error_analysis": [], "anti_patterns": []}
    (ITER / "regression_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ITER / "patch_jugement.json").write_text(json.dumps({**patch, "quoi": patch["titre"],
        "pourquoi": f"{len([i for i in classif['items'] if i['famille']=='D'])} raté(s) jugement miné(s)."},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"branche": "jugement", "regime": regime, "ship": report["ship"], "delta_net": delta_net,
            "iter_dir": str(ITER)}


def _self_test() -> int:
    from classify import _FakeClient as ClsFake  # noqa
    class Fake:
        def complete_sync(self, system, user, model=None):
            if "familles" in system.lower() or "classe" in system.lower() or "famille" in user.lower() or "type_itere" in system:
                pass
            if '"titre"' in system:
                return '{"titre":"Profondeur alignee","principe":"POURQUOI ... QUAND ... QUAND PAS ...","exemple_contraste":"❌ ... ✅ ..."}'
            if '"coherent"' in system:
                return '{"p1":{"coherent":"reprend le detail concret et precis du commentaire","fragmente":"tirade abstraite"},"p2":{"coherent":"reste factuel concret","fragmente":"force humour"}}'
            if "justesse_du_ton" in user:
                out = user[user.index("<OUT>")+5:user.index("</OUT>")].lower()
                s = 2 if ("concret" in out or "ton" in out or "precis" in out) else 0
                return json.dumps({c: s for c in grade_grille.CRITERES})
            # classify
            return '{"items":[{"id":"1","famille":"D","type":"jugement","resume":"humour mal recu"}]}'
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    corpus = tmp / "c.jsonl"; corpus.write_text('{"id":"1","header":"Cas 1 : humour mal recu"}\n', encoding="utf-8")
    smd = tmp / "s.md"; smd.write_text("# skill\n", encoding="utf-8")
    global ITER
    _orig = ITER; ITER = tmp / ".iter"
    try:
        res = run(Fake(), "x", corpus, smd, sample=1)
        ok = res["branche"] == "jugement" and (ITER / "patch_jugement.json").exists() and (ITER / "regression_report.json").exists()
        print("  [OK] pipeline jugement -> artefacts écrits" if ok else f"  [FAIL] {res}")
    finally:
        ITER = _orig
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    p = argparse.ArgumentParser()
    p.add_argument("--skill", required=True)
    p.add_argument("--corpus", required=True)
    p.add_argument("--skill-md", required=True)
    p.add_argument("--sample", type=int, default=12)
    a = p.parse_args(argv)
    from llm_client import AgentSDKClient
    res = run(AgentSDKClient(), a.skill, Path(a.corpus), Path(a.skill_md), a.sample)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
