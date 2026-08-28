"""Tests de la rigueur proportionnelle : gros patch -> revue renforcée + plan."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import patch_plan  # noqa: E402

BASE = "---\nname: demo\ndescription: x.\n---\n\n# demo\n\n## Regles\n- r.\n"


def test_petit_patch_pas_de_plan():
    after = BASE.rstrip() + "\n\n## Micro\n- une ligne.\n"
    assert patch_plan.needs_plan(BASE, after) is False


def test_gros_patch_par_taille():
    after = BASE.rstrip() + "\n\n## Principe\n" + ("x " * 500) + "\n"   # ~1000 car
    assert patch_plan.needs_plan(BASE, after) is True
    plan = patch_plan.build_plan(BASE, after)
    assert plan["revue_renforcee"] is True and plan["chars_added"] > 800
    assert "resume" in plan and plan["texte_ajoute"]


def test_gros_patch_par_sections():
    after = BASE.rstrip() + "\n\n## S1\n- a.\n\n## S2\n- b.\n"                # 2 sections ajoutées
    assert patch_plan.needs_plan(BASE, after) is True


def test_build_plan_avec_client_llm():
    class FakeClient:
        def complete_sync(self, system, user, model=None):
            return '{"resume":"R","modifie_pourquoi":"MP","risques":"RQ","decomposition":"D"}'
    after = BASE.rstrip() + "\n\n## Gros\n" + ("y " * 500) + "\n"
    plan = patch_plan.build_plan(BASE, after, client=FakeClient())
    assert plan["resume"] == "R" and plan["risques"] == "RQ" and plan["revue_renforcee"] is True


def test_run_chain_flag_revue_renforcee_sur_gros_patch(tmp_path, monkeypatch):
    """Bout-en-bout : un patch jugement volumineux -> summary.revue_renforcee=True + plan dans le verdict."""
    import json
    import shutil
    import run_chain
    import config as _config
    FIX = SKILL_ROOT / "evals" / "fixtures"
    iter_dir = tmp_path / "iter"
    shutil.copytree(FIX / "iter_runs" / "jugement", iter_dir)
    # gonfler le patch jugement pour dépasser le seuil
    pj = json.loads((iter_dir / "patch_jugement.json").read_text(encoding="utf-8"))
    pj["principe"] = "POURQUOI " + ("bla " * 400)
    (iter_dir / "patch_jugement.json").write_text(json.dumps(pj, ensure_ascii=False), encoding="utf-8")
    live = tmp_path / "SKILL.md"
    shutil.copy(FIX / "live_jouet" / "SKILL.md", live)
    res = run_chain.run_chain("demo-revue", config=_config.load_config(),
                              brain=run_chain.RecordedBrain(iter_dir), live_path=live,
                              proposals_root=tmp_path / "p", runs_dir=tmp_path / "r",
                              interactions_path=tmp_path / "i.jsonl")
    assert res["statut"] == "propose" and res["revue_renforcee"] is True
    verdict = json.loads((tmp_path / "p" / "demo-revue" / "date" / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["plan"]["revue_renforcee"] is True and verdict["plan"]["chars_added"] > 800
