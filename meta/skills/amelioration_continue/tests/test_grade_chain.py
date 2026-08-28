"""Tests du runner golden grade_chain (0 LLM, regression sur artefacts recorded)."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import grade_chain  # noqa: E402


def test_S4_fuite_golden_pass():
    res = grade_chain.grade_scenario("S4_fuite_golden")
    assert res["status"] == "pass", res


def test_S7_silence_pass_via_spy():
    res = grade_chain.grade_scenario("S7_silence")
    assert res["status"] == "pass", res


def test_S11_injection_pass():
    res = grade_chain.grade_scenario("S11_injection")
    assert res["status"] == "pass", res


def test_S1_detector_fires_comportemental():
    res = grade_chain.grade_scenario("S1_doublon")
    assert res["status"] == "pass", res
    # les 2 checks detector_fires ont bien tourne (live sur les fixtures gelees)
    fired = [c for c in res["checks"] if c["check"] == "detector_fires"]
    assert len(fired) == 2 and all(c["ok"] for c in fired)


def test_pending_feature_est_skip_pas_fail():
    res = grade_chain.grade_scenario("S2_factuel")
    assert res["status"] == "skip", res


def test_regression_suite_verte_sans_LLM():
    report = grade_chain.grade_suite("regression")
    # aucun echec ; les non-construits sont skip
    fails = [r for r in report if r["status"] == "fail"]
    assert fails == [], fails
    assert any(r["status"] == "pass" for r in report)


def test_mvp_gate_vert():
    ok, results = grade_chain.mvp_gate()
    # {S1,S4,S7,S11} tous verts
    assert ok, [r for r in results if r["status"] != "pass"]
    assert {r["name"] for r in results} == {"S1_doublon", "S4_fuite_golden",
                                            "S7_silence", "S11_injection"}


def test_capability_run_absent_avant_S3():
    # run_chain n'existe pas encore -> capability live doit lever proprement, pas planter le grader
    import pytest
    with pytest.raises(grade_chain.ChainNotBuilt):
        grade_chain.capability_run("S1_doublon")
