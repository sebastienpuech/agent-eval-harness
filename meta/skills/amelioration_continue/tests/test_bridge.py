"""Tests du bridge : contrat iterer -> invocation muscle (soudures #1-3).

Prouve : golden_sealed VALIDE (target_runner.validate_schema du muscle), desambiguisation sid#k,
held-out absent + assertion dure, clamp max_iter 5->3, et que les kwargs pilotent VRAIMENT le
muscle SANS re-mining ni re-diagnostic (retouche B).
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import bridge  # noqa: E402


def _contract(**over):
    c = {
        "skill_path": "/abs/demo/skills/demo-revue",
        "evals_file": "generated_evals.json",
        "test_case_ids": ["C21", "C32"],
        "holdout_case_ids": ["C67", "C41", "C75"],
        "regles_a_detecteur": [{"id": "doublon", "detecteur": "doublon.py",
                                "attendu_par_cas": {"C21": "fire", "C32": "fire"}}],
        "max_iter": 5,
        "delegation_status": "VERIFIE_V2",
    }
    c.update(over)
    return c


def _inputs():
    return {"C21": "fil + draft candidat A", "C32": "fil + draft candidat B"}


def _sources():
    return {"C21": "2026-07-07T10:00", "C32": "2026-07-07T10:00"}  # MEME sid -> test sid#k


# --- Garde-fous du contrat ---

def test_delegation_non_verifiee_refuse():
    import pytest
    with pytest.raises(bridge.BridgeError):
        bridge.validate_contract(_contract(delegation_status="EN_ATTENTE"))


def test_test_inter_holdout_non_vide_refuse():
    import pytest
    with pytest.raises(bridge.BridgeError):
        bridge.validate_contract(_contract(test_case_ids=["C21", "C67"]))


# --- golden_sealed ---

def test_golden_sealed_valide_par_target_runner_du_muscle():
    sealed = bridge.build_golden_sealed(_contract(), _inputs(), _sources())
    tr = bridge.import_muscle("target_runner")
    problems = tr.validate_schema(sealed["cases"])
    assert problems == [], problems
    assert sealed["skill"] == "demo-revue"


def test_sid_desambiguisation_kk():
    sealed = bridge.build_golden_sealed(_contract(), _inputs(), _sources())
    sids = [c["source_session_id"] for c in sealed["cases"]]
    assert sids == ["2026-07-07T10:00#0", "2026-07-07T10:00#1"]  # sid partage -> unicite garantie
    assert len(set(sids)) == len(sids)


def test_holdout_absent_du_golden_sealed():
    sealed = bridge.build_golden_sealed(_contract(), _inputs(), _sources())
    ids = {c["id"] for c in sealed["cases"]}
    assert ids.isdisjoint(set(_contract()["holdout_case_ids"]))


# --- clamp + assertion held-out ---

def test_clamp_max_iter_5_vers_3():
    assert bridge.clamp_max_iter(_contract(max_iter=5)) == 3
    assert bridge.clamp_max_iter(_contract(max_iter=2)) == 2  # pas de sur-clamp


def test_assert_no_holdout_leak_detecte_une_fuite():
    import pytest
    payload = {"golden_sealed": {"cases": [{"id": "C67"}]}}  # held-out injecte
    with pytest.raises(AssertionError):
        bridge.assert_no_holdout_leak(payload, ["C67"])


def test_assert_no_holdout_leak_ok_sans_fuite():
    payload = {"golden_sealed": {"cases": [{"id": "C21"}]}, "rates": []}
    bridge.assert_no_holdout_leak(payload, ["C67"])  # ne leve pas


# --- Bout-en-bout : les kwargs pilotent le muscle SANS re-mining/re-diagnostic (retouche B) ---

def test_prepare_muscle_call_pilote_run_pass_sans_rediagnostiquer(tmp_path):
    rates = [{"skill": "demo-revue", "signal": "doublon", "resume": "r"}]
    diagnosis = {"failure_modes": [{"nom": "amnesie-de-fil"}]}
    call = bridge.prepare_muscle_call(_contract(), _inputs(), _sources(),
                                      rates=rates, diagnosis=diagnosis)
    assert call["max_iter"] == 3
    assert call["diagnosis"] is diagnosis and call["rates"] is rates

    orchestrator = bridge.import_muscle("orchestrator")
    keep_revert = bridge.import_muscle("keep_revert")

    class SpyAgents(orchestrator._MockAgents):
        def __init__(self):
            super().__init__([{"capability": 0.8, "regression": 1.0}])
            self.diagnose_called = False
        def diagnose(self, rates, skill_md):
            self.diagnose_called = True
            return super().diagnose(rates, skill_md)

    live = tmp_path / "SKILL.md"
    live.write_text("# jouet\n\n## Regles\n- une regle\n", encoding="utf-8")
    spy = SpyAgents()
    res = orchestrator.run_pass(
        call["skill"], live, spy, keep_revert.MockGit(), tmp_path / "prop", "d",
        max_iter=call["max_iter"], rates=call["rates"], diagnosis=call["diagnosis"],
    )
    assert spy.diagnose_called is False, "diagnosis injecte -> agents.diagnose NE doit PAS etre appele"
    assert res["live_unchanged"] is True
