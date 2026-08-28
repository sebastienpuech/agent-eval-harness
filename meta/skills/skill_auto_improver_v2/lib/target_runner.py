#!/usr/bin/env python3
"""target_runner.py -- rejoue le golden CIBLE d'un skill (evals/cible/<skill>/sealed.json).

Sort {n_cas, n_tags_reels, capability_pass_rate, regression_pass_rate} OU 'signal-insuffisant'.

Seuil signal-insuffisant (spec / sessions_cc tache 6) : n_cas < 6 OU n_tags_reels < 2 -> la passe
NE PROPOSE PAS (fitness proxy non fiable). C'est l'etat MVP attendu tant que le skill cible n'a pas de
tags reels (verdicts.md vide). La notation capability/regression du skill (via le juge gele) arrive
en Session 4 ; en S1, on valide le set scelle et on applique le gate.

Invariants de schema verifies (patch v1.1) : chaque cas porte id, input, assertions[],
source, source_session_id (ce dernier pour le holdout G12).

CLI :
  python target_runner.py skill-jugement     # rejoue le set scelle du skill
  python target_runner.py --self-test         # prouve le gate (set suffisant vs insuffisant)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
CIBLE_DIR = SKILL_ROOT / "evals" / "cible"

MIN_CAS = 6
MIN_TAGS = 2

REQUIRED_FIELDS = ("id", "input", "assertions", "source", "source_session_id")


def validate_schema(cases: list[dict]) -> list[str]:
    """Retourne la liste des violations de schema (vide = conforme)."""
    problems = []
    seen_sid = set()
    for c in cases:
        missing = [f for f in REQUIRED_FIELDS if f not in c]
        if missing:
            problems.append(f"{c.get('id', '?')} : champs manquants {missing}")
        sid = c.get("source_session_id")
        if sid in seen_sid:
            problems.append(f"{c.get('id', '?')} : source_session_id duplique ({sid})")
        seen_sid.add(sid)
        if not c.get("assertions"):
            problems.append(f"{c.get('id', '?')} : assertions vides")
    return problems


def evaluate(sealed: dict) -> dict:
    cases = sealed.get("cases", [])
    n_cas = len(cases)
    n_tags = sum(1 for c in cases if c.get("real_tags"))
    problems = validate_schema(cases)
    insuffisant = n_cas < MIN_CAS or n_tags < MIN_TAGS
    res = {
        "skill": sealed.get("skill"),
        "n_cas": n_cas,
        "n_tags_reels": n_tags,
        "schema_problems": problems,
    }
    if insuffisant:
        raison = []
        if n_cas < MIN_CAS:
            raison.append(f"n_cas={n_cas} < {MIN_CAS}")
        if n_tags < MIN_TAGS:
            raison.append(f"n_tags_reels={n_tags} < {MIN_TAGS}")
        res["statut"] = "signal-insuffisant"
        res["raison"] = " ET ".join(raison)
        res["capability_pass_rate"] = None
        res["regression_pass_rate"] = None
    else:
        # Notation reelle du skill = juge gele (Session 4). En S1 : structure OK, scoring differe.
        res["statut"] = "pret-a-noter"
        res["capability_pass_rate"] = None  # calcule par le juge gele en S4
        res["regression_pass_rate"] = None
    return res


def _load(skill: str) -> dict:
    path = CIBLE_DIR / skill / "sealed.json"
    if not path.exists():
        raise SystemExit(f"golden CIBLE absent : {path.relative_to(SKILL_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def _print(res: dict) -> None:
    print(f"skill={res['skill']}  n_cas={res['n_cas']}  n_tags_reels={res['n_tags_reels']}  "
          f"statut={res['statut']}")
    if res.get("raison"):
        print(f"  raison : {res['raison']} -> la passe NE PROPOSE PAS (attendu au MVP).")
    if res["schema_problems"]:
        for p in res["schema_problems"]:
            print(f"  [SCHEMA] {p}")
    else:
        print("  schema : conforme (id/input/assertions/source/source_session_id, sid uniques).")


def _self_test() -> int:
    ok = True
    suffisant = {"skill": "x", "cases": [
        {"id": f"C{i}", "input": {}, "assertions": [{"check": "x"}], "source": "tag_reel",
         "real_tags": [{"verdict": "rejete"}] if i < 2 else [],
         "source_session_id": f"s{i}"} for i in range(6)]}
    r1 = evaluate(suffisant)
    try:
        assert r1["statut"] == "pret-a-noter", f"6 cas + 2 tags -> devrait passer le gate ({r1['statut']})"
        assert not r1["schema_problems"], r1["schema_problems"]
        print("  [OK] 6 cas / 2 tags -> pret-a-noter")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")
    insuffisant = {"skill": "x", "cases": [
        {"id": f"C{i}", "input": {}, "assertions": [{"check": "x"}], "source": "proxy_redteam",
         "real_tags": [], "source_session_id": f"s{i}"} for i in range(10)]}
    r2 = evaluate(insuffisant)
    try:
        assert r2["statut"] == "signal-insuffisant", "10 cas / 0 tag -> signal-insuffisant"
        assert "n_tags_reels=0 < 2" in r2["raison"], r2["raison"]
        print("  [OK] 10 cas / 0 tag -> signal-insuffisant (le gate refuse)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    skills = [a for a in argv if not a.startswith("-")]
    if not skills:
        print(__doc__)
        return 0
    res = evaluate(_load(skills[0]))
    _print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
