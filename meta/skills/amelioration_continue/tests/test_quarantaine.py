"""Tests de la quarantaine (S6) : 2 erreurs consécutives -> cron skippe ; manuel override."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import quarantaine  # noqa: E402
import run_chain  # noqa: E402


def _write_interactions(path, records):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


def test_deux_erreurs_consecutives_quarantine(tmp_path):
    inter = tmp_path / "i.jsonl"
    _write_interactions(inter, [{"skill": "s", "statut": "propose"},
                                {"skill": "s", "statut": "erreur"},
                                {"skill": "s", "statut": "erreur"}])
    assert quarantaine.is_quarantined(inter, "s") is True


def test_une_erreur_ne_quarantine_pas(tmp_path):
    inter = tmp_path / "i.jsonl"
    _write_interactions(inter, [{"skill": "s", "statut": "erreur"},
                                {"skill": "s", "statut": "propose"}])
    assert quarantaine.is_quarantined(inter, "s") is False


def test_autre_skill_non_affecte(tmp_path):
    inter = tmp_path / "i.jsonl"
    _write_interactions(inter, [{"skill": "s", "statut": "erreur"}, {"skill": "s", "statut": "erreur"},
                                {"skill": "autre", "statut": "propose"}])
    assert quarantaine.is_quarantined(inter, "autre") is False


def test_cron_skippe_un_skill_en_quarantaine(tmp_path):
    inter = tmp_path / "i.jsonl"
    _write_interactions(inter, [{"skill": "demo-revue", "statut": "erreur"},
                                {"skill": "demo-revue", "statut": "erreur"}])
    res = run_chain.run_chain("demo-revue", brain=run_chain.RecordedBrain(tmp_path),  # brain jamais appelé
                              live_path=tmp_path / "x", proposals_root=tmp_path / "p",
                              runs_dir=tmp_path / "r", interactions_path=inter, trigger="cron")
    assert res["statut"] == "quarantaine"
    assert not (tmp_path / "r" / "demo-revue.lock").exists()   # aucun lock pris (skip avant)


def test_manuel_bypasse_la_quarantaine(tmp_path):
    """Un déclenchement manuel tourne malgré la quarantaine (l'humain décide de réessayer)."""
    inter = tmp_path / "i.jsonl"
    _write_interactions(inter, [{"skill": "demo-revue", "statut": "erreur"},
                                {"skill": "demo-revue", "statut": "erreur"}])

    class BoomBrain:
        def run(self, skill):
            raise RuntimeError("boom")  # prouve qu'on est ENTRÉ dans la passe (pas skippé)
    res = run_chain.run_chain("demo-revue", brain=BoomBrain(), live_path=tmp_path / "x",
                              proposals_root=tmp_path / "p", runs_dir=tmp_path / "r",
                              interactions_path=inter, trigger="manuel")
    assert res["statut"] == "erreur"   # entré puis erreur -> PAS "quarantaine" (bypass confirmé)
