"""Tests de l'adaptateur iterer -> run_chain. Prouve : résolution sur nos fixtures {cases} ET
erreur EXPLICITE (pas de devinette) sur la shape RÉELLE {critical_checks} d'iterer."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import iterer_adapter as ia  # noqa: E402

FIX = SKILL_ROOT / "evals" / "fixtures"


def test_case_data_resout_le_format_cases():
    iter_dir = FIX / "iter_runs" / "prose_s1"
    contract = ia.read_contract(iter_dir)
    ci, ss = ia.read_case_data(iter_dir, contract)
    assert set(ci) == {"C21", "C32"}
    assert ss["C21"] == "2026-07-07T10:00"


def test_case_data_leve_sur_shape_reelle_iterer():
    """La sortie RÉELLE d'iterer (generated_evals = {critical_checks}) n'a pas input/sid -> erreur claire."""
    import pytest
    iter_dir = FIX / "iterer_real_sample"
    contract = ia.read_contract(iter_dir)
    with pytest.raises(ia.ItererShapeError) as e:
        ia.read_case_data(iter_dir, contract)
    assert "critical_checks" in str(e.value) and "demo-revue" in str(e.value)  # message actionnable


def test_rates_diagnosis_absents_donnent_none():
    iter_dir = FIX / "iterer_real_sample"  # pas de rates.json/diagnosis.json
    assert ia.read_rates(iter_dir) is None
    assert ia.read_diagnosis(iter_dir) is None


def test_rates_present_est_lu():
    iter_dir = FIX / "iter_runs" / "prose_s1"  # a un rates.json (iterer simulé)
    rates = ia.read_rates(iter_dir)
    assert isinstance(rates, list) and rates and rates[0]["signal"] == "doublon"


def test_classification_passthrough_champ_type():
    real = ia.read_classification(FIX / "iterer_real_sample")
    assert real["items"][0]["type"] == "contrainte_dure"      # champ `type` (pas type_itere)
