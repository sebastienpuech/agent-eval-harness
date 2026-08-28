"""Tests du gate de non-régression GÉNÉRAL (golden du skill cible, avant/après patch)."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import target_golden  # noqa: E402

DEMO = SKILL_ROOT / "evals" / "fixtures" / "demo_golden" / "run_golden.py"
LIVE = "---\nname: demo\ndescription: skill de démo.\n---\n\n# demo\n\n## Regles\n- une regle.\n"


def _registry():
    return {"demo": {"golden_cmd": ["python", str(DEMO), "{skill_md}"]}}


def test_patch_sans_regression_passe(tmp_path):
    live = tmp_path / "SKILL.md"
    live.write_text(LIVE, encoding="utf-8")
    candidate = LIVE.rstrip() + "\n\n## Nouveau principe\n- ajout append-only.\n"  # garde ## Regles
    r = target_golden.check_no_regression("demo", live, candidate, _registry(), cwd=tmp_path)
    assert r["verifiable"] is True
    assert r["rate_before"] == 1.0 and r["rate_after"] == 1.0
    assert r["regression"] is False


def test_patch_qui_regresse_est_bloque(tmp_path):
    live = tmp_path / "SKILL.md"
    live.write_text(LIVE, encoding="utf-8")
    # candidate qui SUPPRIME la section ## Regles -> le golden cible chute 1.0 -> 0.5
    candidate = "---\nname: demo\ndescription: skill de démo.\n---\n\n# demo\n\n## Autre\n- x.\n"
    r = target_golden.check_no_regression("demo", live, candidate, _registry(), cwd=tmp_path)
    assert r["verifiable"] is True
    assert r["rate_before"] == 1.0 and r["rate_after"] == 0.5
    assert r["regression"] is True                       # REFUS


def test_skill_sans_golden_cmd_non_verifiable(tmp_path):
    live = tmp_path / "SKILL.md"
    live.write_text(LIVE, encoding="utf-8")
    r = target_golden.check_no_regression("demo-revue", live, LIVE + "\nx", {"demo-revue": {}}, cwd=tmp_path)
    assert r["verifiable"] is False and r["regression"] is False   # non bloqué, mais NON vérifié (drapeau)


def test_run_chain_REFUSE_si_golden_cible_regresse(tmp_path, monkeypatch):
    """Bout-en-bout : la passe produit un patch jugement, mais le golden du skill CIBLE régresse
    (1.0->0.5) -> run_chain REFUSE, 0 proposition. C'est le contrôle général demandé."""
    import shutil
    import run_chain
    import config as _config
    FIX = SKILL_ROOT / "evals" / "fixtures"
    iter_dir = tmp_path / "iter"
    shutil.copytree(FIX / "iter_runs" / "jugement", iter_dir)          # patch ajoute 'Profondeur alignee'
    live = tmp_path / "SKILL.md"
    shutil.copy(FIX / "live_jouet" / "SKILL.md", live)
    penal = ["python", str(FIX / "demo_golden" / "run_golden_penalise.py"), "{skill_md}"]
    monkeypatch.setattr(run_chain._config, "load_registry",
                        lambda: {"demo-revue": {"golden_cmd": penal}})
    res = run_chain.run_chain("demo-revue", config=_config.load_config(),
                              brain=run_chain.RecordedBrain(iter_dir), live_path=live,
                              proposals_root=tmp_path / "p", runs_dir=tmp_path / "r",
                              interactions_path=tmp_path / "i.jsonl")
    assert res["statut"] == "refuse" and res["proposals_emitted"] == 0
    assert res["regression_cible"]["regression"] is True
    assert res["regression_cible"]["rate_before"] == 1.0 and res["regression_cible"]["rate_after"] == 0.5
    assert not (tmp_path / "p" / "demo-revue").exists()              # AUCUNE proposition écrite
