#!/usr/bin/env python3
"""isolation.py -- frontiere anti-Goodhart : DEUX disjonctions (patch ARCH-002).

Ce fichier s'appelait `judge_io.py` au plan initial -- c'est le meme module, renomme, il n'y a
rien d'autre a trouver sous l'ancien nom. Il n'isolait alors que les notes du rewriter du juge.
La vraie frontiere en a DEUX :
  (1) judge_input inter rewriter_notes == vide   -- le juge ne voit pas la rhetorique du rewriter
  (2) rewriter_input inter golden_assertions == vide -- le rewriter ne voit pas les assertions du
      golden (sinon il apprend a repondre au test -> le juge "gele" devient du theatre)

Le rewriter ne recoit que diagnosis.json + SKILL.md courant. JAMAIS sealed.json ni les logs runner.

Holdout (spec 10bis) : POOL-DIAGNOSTIC (rewriter) et POOL-EVAL (juge/golden) viennent de sessions
DISJOINTES. `check_pool_disjoint` verifie set(sessions_rewriter) inter set(sessions_golden) = vide.
(ASCII volontaire : ce docstring est IMPRIME par `print(__doc__)` ci-dessous, et les symboles
mathematiques crashent la console Windows en cp1252 -- meme correctif que pour les prints.)

G12 = golden_leak (une fuite golden dans le contexte rewriter -> disjonction 2 ROUGE, run avorte)
      + holdout (pools disjoints).

CLI :
  python isolation.py --self-test   # clean OK, fuite golden -> ROUGE, pools disjoints
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Retouche A (target-agnostic, ac-session-2) : source UNIQUE du skill cible + resolution du golden.
# Defaut = skill-jugement -> le golden META du muscle reste identique (gate 16/16). Le muscle peut
# desormais cibler N'IMPORTE quel skill en passant `skill=` (utilise par la chaine amelioration_continue).
DEFAULT_TARGET_SKILL = "skill-jugement"


def sealed_path(skill: str = DEFAULT_TARGET_SKILL, skill_root: Path = SKILL_ROOT) -> Path:
    """Chemin du golden CIBLE scelle d'un skill (target-agnostic)."""
    return skill_root / "evals" / "cible" / skill / "sealed.json"


def load_sealed(skill: str = DEFAULT_TARGET_SKILL, skill_root: Path = SKILL_ROOT) -> dict:
    return json.loads(sealed_path(skill, skill_root).read_text(encoding="utf-8"))


SEALED = sealed_path()  # back-compat (self-tests) ; derive du helper


def check_disjunctions(judge_input, rewriter_notes, rewriter_input, golden_assertions) -> dict:
    ji, rn = set(judge_input), set(rewriter_notes)
    ri, ga = set(rewriter_input), set(golden_assertions)
    d1, d2 = ji.isdisjoint(rn), ri.isdisjoint(ga)
    return {"d1_judge_vs_rewriter_notes": d1, "d2_rewriter_vs_golden": d2,
            "ok": d1 and d2, "fuite_d1": sorted(ji & rn), "fuite_d2": sorted(ri & ga)}


def check_pool_disjoint(rewriter_sessions, golden_sessions) -> dict:
    rs, gs = set(rewriter_sessions), set(golden_sessions)
    return {"disjoint": rs.isdisjoint(gs), "intersection": sorted(rs & gs)}


def golden_assertion_signatures(sealed: dict) -> set[str]:
    """Signatures d'assertion du golden cible (ce que le rewriter ne doit JAMAIS voir)."""
    return {f"{a['check']}{a.get('op', '')}{a.get('value', '')}"
            for c in sealed.get("cases", []) for a in c.get("assertions", [])}


def golden_source_sessions(sealed: dict) -> set[str]:
    return {c["source_session_id"] for c in sealed.get("cases", []) if "source_session_id" in c}


def golden_leak_tokens(sealed: dict) -> set[str]:
    """Jetons du golden que le contexte rewriter ne doit JAMAIS contenir : noms de checks +
    signatures d'assertion (ex. 'reponse_len_words', 'reponse_len_words<=12')."""
    toks: set[str] = set()
    for c in sealed.get("cases", []):
        for a in c.get("assertions", []):
            if a.get("check"):
                toks.add(a["check"])
            toks.add(f"{a.get('check', '')}{a.get('op', '')}{a.get('value', '')}")
    return {t for t in toks if t}


def assert_no_golden_leak(rewriter_context_text: str, sealed: dict) -> tuple[bool, list[str]]:
    """GATE RUNTIME (patch red-team #1) : verifie que le contexte REEL passe au rewriter ne
    contient aucun jeton du golden. Retourne (ok, jetons_fuites). Fail-closed."""
    leaked = sorted(t for t in golden_leak_tokens(sealed) if t in rewriter_context_text)
    return (not leaked), leaked


def _self_test() -> int:
    ok = True
    sealed = json.loads(SEALED.read_text(encoding="utf-8"))
    ga = golden_assertion_signatures(sealed)
    gs = golden_source_sessions(sealed)

    # Contexte rewriter PROPRE : diagnosis + skill_md, disjoint du golden.
    rewriter_input = {"diagnosis:keyword-spotting", "skill_md:jouet-regles"}
    clean = check_disjunctions(judge_input={"golden:reponse_len_words"}, rewriter_notes={"note:rhetorique"},
                               rewriter_input=rewriter_input, golden_assertions=ga)
    try:
        assert clean["ok"], f"contexte propre doit passer les 2 disjonctions ({clean})"
        print("  [OK] contexte propre : d1 et d2 verts")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    # Fuite : on injecte une assertion du golden dans le contexte rewriter -> disjonction 2 ROUGE.
    leaked = rewriter_input | {next(iter(ga))}
    leak = check_disjunctions(set(), set(), leaked, ga)
    try:
        assert not leak["ok"] and not leak["d2_rewriter_vs_golden"], "une fuite golden doit passer au ROUGE"
        assert leak["fuite_d2"], "la fuite doit etre nommee"
        print(f"  [OK] fuite golden injectee -> ROUGE (d2), fuite={leak['fuite_d2']}")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    # Holdout : sessions rewriter (fixt-sj-*) disjointes des sessions golden (proxy-sj-*).
    rewriter_sessions = {"fixt-sj-rate-01", "fixt-sj-rate-02", "fixt-sj-ok-01"}
    pool = check_pool_disjoint(rewriter_sessions, gs)
    try:
        assert pool["disjoint"], f"pools rewriter/golden doivent etre disjoints ({pool})"
        print(f"  [OK] holdout : {len(rewriter_sessions)} sessions rewriter inter {len(gs)} golden = vide")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
    sys.exit(0)
