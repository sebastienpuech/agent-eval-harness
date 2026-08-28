#!/usr/bin/env python3
"""surface_judge.py -- juge d'appropriation (voie cold-review, étroitesse de posture).

Note 0-2 si UNE sortie répond « à bon escient » vu la mission : soulève le levier pertinent SSI
la situation le justifie, sans sur-élargir. Frère de grade_grille : LLM ici, agrégation déterministe
déléguée à run_grid. Client injectable (_FakeClient en test, 0 LLM).
"""
from __future__ import annotations
import json, re
from pathlib import Path
import run_grid
from lint_pii import lint_grid_scores

SKILL_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = SKILL_ROOT / "agents"
CRITERES_SURFACE = ["souleve_levier_pertinent", "ancre_dans_la_situation", "reste_a_propos"]


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


def _one_run(client, output: str, context: str) -> dict:
    system = (AGENTS_DIR / "juge-surface.md").read_text(encoding="utf-8")
    user = ("Situation (sans PII) :\n" + context[:1500] + "\n\nSORTIE à noter :\n<OUT>\n"
            + output[:1500] + "\n</OUT>\n\nNote 0-2. JSON uniquement : {\"souleve_levier_pertinent\": int, "
            "\"ancre_dans_la_situation\": int, \"reste_a_propos\": int}.")
    data = extract_json(client.complete_sync(system, user))
    return {c: max(0, min(2, int(data[c]))) for c in CRITERES_SURFACE}


def grade_appropriation(client, output: str, context: str, n: int = 3) -> dict:
    runs = [_one_run(client, output, context) for _ in range(n)]
    agg = run_grid.score_variante(runs, CRITERES_SURFACE)
    agg["n_runs"] = n
    return agg


def grade_all_situations(client, variantes: dict, n: int = 3) -> dict:
    out = {sid: grade_appropriation(client, v["output"], v.get("context", ""), n)
           for sid, v in variantes.items()}
    scores = {"seed": run_grid.SEED, "criteres": CRITERES_SURFACE, "variantes": out}
    problems = lint_grid_scores(scores)
    if problems:
        raise ValueError(f"lint PII a rejeté surface scores : {problems}")
    return scores


class _FakeClient:
    """0-LLM déterministe. Note l'APPROPRIATION (haut = bon), en INVERSANT selon le contexte :
    - warranté (`levier_attendu=X`) : élargir vers X = bon ;
    - témoin (`levier_attendu=aucun`) : rester focalisé = bon, élargir = mauvais.
    Marqueurs d'élargissement : 'pense aussi'/'angle'/'vu ton objectif'/'levier'."""
    def complete_sync(self, system: str, user: str, model=None) -> str:
        ctx = user[:user.index("<OUT>")].lower()
        out = user[user.index("<OUT>") + 5:user.index("</OUT>")].lower()
        warranted = "levier_attendu=aucun" not in ctx
        elargit = any(w in out for w in ("pense aussi", "angle", "vu ton objectif", "levier"))
        ancre = any(w in out for w in ("ancre", "lie a ta situation", "concret"))
        court = len(out) < 120
        souleve = (2 if elargit else 0) if warranted else (0 if elargit else 2)
        ancre_s = (2 if ancre else (1 if elargit else 0)) if warranted else 2
        return json.dumps({
            "souleve_levier_pertinent": souleve,
            "ancre_dans_la_situation": ancre_s,
            "reste_a_propos": 2 if court else 0,
        })


def _self_test() -> int:
    # WARRANTÉ (levier attendu) : "patched" le soulève, "baseline" reste étroit.
    warr = {
        "patched":  {"output": "Vu ton objectif, pense aussi a l'angle X ici : concret et lie a ta situation.", "context": "levier_attendu=X | situation warrantee"},
        "baseline": {"output": "Ok, c'est note.", "context": "levier_attendu=X | situation warrantee"},
    }
    scores = grade_all_situations(_FakeClient(), warr, n=3)
    a, b = scores["variantes"]["patched"], scores["variantes"]["baseline"]
    ok = (a["total_mean"] - b["total_mean"]) >= 3
    print(f"  warranté : patched({a['total_mean']}) - baseline({b['total_mean']})  (>=3 attendu)")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    print(__doc__)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
