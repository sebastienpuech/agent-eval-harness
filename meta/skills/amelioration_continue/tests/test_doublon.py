"""Tests du detecteur doublon (instrument de mesure de S1).

Le detecteur repond a UNE question deterministe : « le draft repete-t-il une reponse
deja postee par l'utilisateur dans le fil de revue ? ». Zero LLM. C'est la cible du check golden
`detector_fires` (data_model §4) et le check applique par holdout_scorer (§2).
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

from detectors import doublon  # noqa: E402

FIXTURES = SKILL_ROOT / "evals" / "fixtures" / "s1_doublon"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _sent_messages() -> list[str]:
    import json
    meta = json.loads(_read("meta.json"))
    return meta["sent_by_user"]


# --- Comportement fondateur (S1) : fire sur le doublon, pas sur le propre ---

def test_fire_sur_draft_doublon():
    assert doublon.fires(_read("draft_doublon.md"), _sent_messages()) is True


def test_no_fire_sur_draft_propre():
    assert doublon.fires(_read("draft_propre.md"), _sent_messages()) is False


# --- Determinisme et robustesse ---

def test_identique_fire():
    sent = ["Ta remarque sur le cache est bien vue"]
    assert doublon.fires("Ta remarque sur le cache est bien vue", sent) is True


def test_insensible_casse_accents_ponctuation():
    sent = ["Merci pour la relecture du patch !"]
    # meme reponse, casse/accents/ponctuation differents -> doit fire
    assert doublon.fires("merci pour la relecture du patch", sent) is True


def test_liste_vide_ne_fire_jamais():
    assert doublon.fires("un draft quelconque", []) is False


def test_message_distinct_ne_fire_pas():
    sent = ["Ta remarque sur le cache est bien vue"]
    assert doublon.fires("Tu preferes qu'on scinde la PR en deux", sent) is False


def test_detect_rapporte_index_et_score():
    sent = ["message A distinct", "Ta remarque sur le cache est bien vue"]
    res = doublon.detect("Ta remarque sur le cache est bien vue", sent)
    assert res["fired"] is True
    assert res["matched_idx"] == 1
    assert res["score"] >= doublon.DEFAULT_THRESHOLD


def test_determinisme_repetable():
    sent = _sent_messages()
    draft = _read("draft_doublon.md")
    assert doublon.detect(draft, sent) == doublon.detect(draft, sent)
