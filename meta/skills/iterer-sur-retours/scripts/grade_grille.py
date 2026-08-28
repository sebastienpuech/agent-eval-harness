#!/usr/bin/env python3
"""grade_grille.py -- CÂBLAGE LLM du juge-par-grille (branche jugement). Le grader qui manquait.

`run_grid.py` AGRÈGE des scores (moyenne, bruit, significativité) mais ne SCORE rien. Ce module
appelle le juge-par-grille (Opus, prompt `agents/juge-par-grille.md`) pour noter une SORTIE du skill
sur 6 critères 0-2, N≥3 fois (seed figé), puis délègue l'agrégation à `run_grid.score_variante`.
Parallèle exact du classifieur : LLM ici, agrégation déterministe là.

Confidentialité (impératif jugement) : justifications `<critere>=<score> : <raison>`, jamais de
verbatim ; `lint_pii.lint_grid_scores` bloque avant écriture. Client injectable (_FakeClient en test).

CLI :
  python grade_grille.py --self-test           # fake client, déterministe
  python grade_grille.py --smoke               # 2 vraies notations Opus (bon vs plat) -> la grille sépare
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import run_grid  # agrégation déterministe (score_variante / significativite)
from lint_pii import lint_grid_scores

SKILL_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = SKILL_ROOT / "agents"
ITER = SKILL_ROOT / ".iter"
SEED = run_grid.SEED
CRITERES = ["justesse_du_ton", "ancrage_concret", "absence_vibe_ia",
            "pertinence", "clarte", "concision"]


def extract_json(text: str) -> dict:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    if start == -1:
        raise ValueError(f"aucun JSON : {text[:150]!r}")
    depth = 0
    for i in range(start, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return json.loads(text[start:i + 1])
    raise ValueError("JSON non équilibré")


def _one_run(client, candidate_output: str, case_context: str) -> dict:
    system = (AGENTS_DIR / "juge-par-grille.md").read_text(encoding="utf-8")
    user = (
        "Contexte du cas (sans PII) :\n" + case_context[:1500] + "\n\n"
        "SORTIE du skill à noter (bloc délimité) :\n<OUT>\n" + candidate_output[:1500] + "\n</OUT>\n\n"
        "Note sur les 6 critères 0-2. Réponds UNIQUEMENT en JSON : {\"justesse_du_ton\": int, "
        "\"ancrage_concret\": int, \"absence_vibe_ia\": int, \"pertinence\": int, "
        "\"clarte\": int, \"concision\": int}."
    )
    data = extract_json(client.complete_sync(system, user))
    return {c: max(0, min(2, int(data[c]))) for c in CRITERES}


def grade_variante(client, candidate_output: str, case_context: str, n: int = 3) -> dict:
    runs = [_one_run(client, candidate_output, case_context) for _ in range(n)]
    agg = run_grid.score_variante(runs, CRITERES)   # agrégation déterministe (run_grid)
    agg["n_runs"] = n
    return agg


def grade_all(client, variantes: dict, n: int = 3) -> dict:
    """variantes = {case_id: {"output": str, "context": str}} -> grid_scores.json."""
    out = {}
    for cid, v in variantes.items():
        out[cid] = grade_variante(client, v["output"], v.get("context", ""), n)
    scores = {"seed": SEED, "criteres": CRITERES, "variantes": out}
    problems = lint_grid_scores(scores)  # garde-fou PII avant tout
    if problems:
        raise ValueError(f"lint PII a rejeté grid_scores : {problems}")
    return scores


class _FakeClient:
    """Juge déterministe (0 LLM) : note haut si l'output contient des marqueurs 'ancrés', bas sinon."""

    def complete_sync(self, system: str, user: str, model=None) -> str:
        out = user[user.index("<OUT>") + 5:user.index("</OUT>")].lower()
        hi = any(w in out for w in ("detail", "ton", "concret", "image", "précis", "precis"))
        s = 2 if hi else 0
        return json.dumps({c: s for c in CRITERES})


def _self_test() -> int:
    variantes = {
        "coherente": {"output": "Reprend le detail concret du commentaire et repond precisement a l'objection.", "context": "commentaire de revue, contexte technique"},
        "fragmentee": {"output": "Ok bien vu, je regarde ca.", "context": "commentaire de revue, contexte technique"},
    }
    scores = grade_all(_FakeClient(), variantes, n=3)
    a, b = scores["variantes"]["coherente"], scores["variantes"]["fragmentee"]
    sig = run_grid.significativite(a, b)
    ok = True
    try:
        assert a["total_mean"] - b["total_mean"] >= 3, (a["total_mean"], b["total_mean"])  # 6a : la grille sépare
        assert sig["delta"] >= 3
        print(f"  [OK] grille sépare cohérente({a['total_mean']}) vs fragmentée({b['total_mean']}) delta={sig['delta']}")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def _smoke() -> int:
    from llm_client import AgentSDKClient
    variantes = {
        "ancre": {"output": "Ton point sur le cache tient : j'avais rate l'invalidation au write, je corrige.", "context": "le relecteur a signale un probleme de cache"},
        "plat": {"output": "Ok, bien vu, je corrige.", "context": "le relecteur a signale un probleme de cache"},
    }
    scores = grade_all(AgentSDKClient(), variantes, n=3)
    a, b = scores["variantes"]["ancre"], scores["variantes"]["plat"]
    print(f"  ancré total={a['total_mean']} (bruit {a['bruit_intra_juge']}) vs plat total={b['total_mean']}")
    sig = run_grid.significativite(a, b)
    ok = sig["delta"] > 0
    print(f"  delta={sig['delta']} significatif={sig['delta'] > sig['bruit_intra_juge']}")
    print("=> SMOKE OK" if ok else "=> SMOKE ECHOUE (le juge ne discrimine pas ?)")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "--smoke" in argv:
        return _smoke()
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
