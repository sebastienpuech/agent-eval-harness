"""Tests de la couche de mesure holdout_scorer.

Preuve du spike : holdout_scorer produit {holdout:{cid:{avant,apres}}} en appliquant
le detecteur aux sorties enregistrees des cas held-out, et ce dict est CONSOMMABLE
par le vrai regression_gate.py d'iterer (boite noire, subprocess).
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import holdout_scorer  # noqa: E402

FIXTURES = SKILL_ROOT / "evals" / "fixtures" / "s1_doublon"


def test_build_holdout_structure_et_scores():
    cases = holdout_scorer.load_holdout_dir(FIXTURES)
    d = holdout_scorer.build_holdout(cases)
    assert set(d.keys()) == {"holdout"}
    ho = d["holdout"]
    # 3 cas, chacun {avant, apres} en float
    assert set(ho) == {"ho_01_reprise_taf", "ho_02_retour_pres", "ho_03_demo_stable"}
    for cid, av in ho.items():
        assert set(av.keys()) == {"avant", "apres"}
        assert isinstance(av["avant"], float) and isinstance(av["apres"], float)
    # scores attendus : les 2 doublons ANCIENS FIRE (0->1), le stable ne bouge pas (1,1)
    assert ho["ho_01_reprise_taf"] == {"avant": 0.0, "apres": 1.0}
    assert ho["ho_02_retour_pres"] == {"avant": 0.0, "apres": 1.0}
    assert ho["ho_03_demo_stable"] == {"avant": 1.0, "apres": 1.0}


def test_score_output_detecteur():
    sent = ["Ta remarque sur le cache est bien vue"]
    # doublon -> fire -> 0.0
    assert holdout_scorer._score_output(
        "Ta remarque sur le cache est bien vue", sent) == 0.0
    # neuf -> no_fire -> 1.0
    assert holdout_scorer._score_output("Du coup tu vises quoi pour la demo", sent) == 1.0


def test_mode_live_est_differe_S0():
    import pytest
    with pytest.raises(NotImplementedError):
        holdout_scorer.build_holdout([], mode="live")
    with pytest.raises(NotImplementedError):
        holdout_scorer.score_live("demo-revue", {})


def test_dict_consommable_par_regression_gate_reel():
    """Bout-en-bout : le vrai regression_gate d'iterer accepte le dict et sort un verdict."""
    cases = holdout_scorer.load_holdout_dir(FIXTURES)
    d = holdout_scorer.build_holdout(cases)
    report = holdout_scorer.feed_regression_gate(d)
    # regression_gate a bien tourne et produit son schema de sortie
    for key in ("delta_net_holdout", "regression_suite", "ship", "deltas_par_cas"):
        assert key in report
    # delta_net = (1+1+0)/3 = 0.667 ; aucune regression -> ship=true
    assert report["regression_suite"] == 1.0
    assert report["ship"] is True
    assert report["delta_net_holdout"] > 0
    assert report["_exit_code"] == 0  # 0 = ship cote CLI d'iterer
