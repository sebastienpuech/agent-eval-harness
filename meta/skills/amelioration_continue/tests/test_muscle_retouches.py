"""Verifie les retouches A/B du muscle depuis la chaine (sans dupliquer le golden 16/16 du muscle,
qui reste son propre gate). Retouche A = target-agnostic : assert_no_golden_leak couvre un golden
CIBLE arbitraire (pas seulement jugement)."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import bridge  # noqa: E402


def test_retouche_A_isolation_couvre_un_golden_arbitraire():
    isolation = bridge.import_muscle("isolation")
    # golden CIBLE arbitraire (PAS jugement) : un skill quelconque avec ses propres checks.
    sealed = {"skill": "skill-demo-cible", "cases": [
        {"id": "c1", "input": "x", "source": "contrat_iterer", "source_session_id": "s#0",
         "assertions": [{"check": "duree_coherente", "op": "<=", "value": 42}]}]}

    # contexte rewriter PROPRE (aucun jeton du golden) -> pas de fuite.
    ok, leaked = isolation.assert_no_golden_leak("diagnosis: amnesie-de-fil\n# SKILL propre", sealed)
    assert ok and leaked == []

    # contexte qui laisse fuiter un check du golden arbitraire -> DETECTE (fail-closed).
    ok2, leaked2 = isolation.assert_no_golden_leak(
        "le rewriter voit duree_coherente du golden", sealed)
    assert ok2 is False and "duree_coherente" in leaked2


def test_retouche_A_sealed_path_target_agnostic():
    isolation = bridge.import_muscle("isolation")
    assert isolation.DEFAULT_TARGET_SKILL == "skill-jugement"  # defaut inchange (gate 16/16)
    p = isolation.sealed_path("un-autre-skill")
    assert p.name == "sealed.json" and "un-autre-skill" in str(p)


def test_retouche_B_signature_run_pass_a_les_nouveaux_params():
    import inspect
    orchestrator = bridge.import_muscle("orchestrator")
    params = inspect.signature(orchestrator.run_pass).parameters
    for p in ("rates", "diagnosis", "fixture_source"):
        assert p in params, f"retouche B : run_pass doit exposer {p}"
