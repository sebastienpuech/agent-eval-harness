"""Tests de l'orchestrateur run_chain (E1->E4) — regression 0-LLM via RecordedBrain + mock agents.

Couvre les 3 vérifs S3 : jugement -> muscle ∅ ; prose S1 -> proposition canonique + held-out mesuré +
veto ship_effectif ; fuite golden -> isolation-violation, 0 proposition. + LOCK + invariant spy.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import config as _config  # noqa: E402
import run_chain  # noqa: E402
import spy  # noqa: E402

FIX = SKILL_ROOT / "evals" / "fixtures"


def _setup(tmp_path, which):
    iter_dir = tmp_path / "iter"
    shutil.copytree(FIX / "iter_runs" / which, iter_dir)
    live = tmp_path / "SKILL.md"
    shutil.copy(FIX / "live_jouet" / "SKILL.md", live)
    return iter_dir, live, _config.load_config()


def _run(tmp_path, which, **over):
    iter_dir, live, cfg = _setup(tmp_path, which)
    kwargs = dict(config=cfg, brain=run_chain.RecordedBrain(iter_dir), live_path=live,
                  proposals_root=tmp_path / "prop", runs_dir=tmp_path / "runs",
                  interactions_path=tmp_path / "int.jsonl")
    kwargs.update(over)
    return run_chain.run_chain("demo-revue", **kwargs), tmp_path, live


def test_jugement_muscle_absent(tmp_path):
    res, tp, live = _run(tmp_path, "jugement", run_id="ac_j")
    assert res["muscle_invoked"] is False
    assert res["routage"] == "jugement"
    assert res["statut"] == "propose" and res["ship"] is True
    cand = (tp / "prop" / "demo-revue" / "date" / "candidate" / "SKILL.md").read_text(encoding="utf-8")
    assert "Profondeur alignee" in cand           # patch iterer APPLIQUÉ (append)
    assert cand.startswith("---")                  # append-only : original conservé
    assert live.read_text(encoding="utf-8").startswith("---")  # live JAMAIS écrit


def test_prose_s1_proposition_canonique_et_veto(tmp_path):
    sent = []
    res, tp, live = _run(tmp_path, "prose_s1", run_id="ac_p", telegram=sent.append)
    assert res["muscle_invoked"] is True
    assert res["routage"] == "prose"
    assert res["statut"] == "propose" and res["ship"] is True
    verdict = json.loads((tp / "prop" / "demo-revue" / "date" / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["muscle_keep"] and verdict["chain_ship"] and verdict["ship_effectif"] is True
    assert verdict["delta_net_holdout"] > 0 and verdict["regression_suite"] == 1.0   # held-out mesuré
    assert len(sent) == 1 and "ac_p" in sent[0]
    assert re.search("rebase|invalidation du cache", sent[0]) is None             # 0 verbatim du fil


def test_fuite_golden_isolation_violation_zero_proposition(tmp_path):
    sent = []
    res, tp, live = _run(tmp_path, "fuite_golden", run_id="ac_f", telegram=sent.append)
    assert res["statut"] == "isolation-violation"
    assert res["proposals_emitted"] == 0 and res["ship"] is False
    assert sent == []                                          # 0 push
    assert not (tp / "prop" / "demo-revue").exists()          # 0 proposition
    assert live.read_text(encoding="utf-8").startswith("---")  # live inchangé


def test_verrou_best_effort_deuxieme_passe(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "demo-revue.lock").write_text(
        json.dumps({"skill": "demo-revue", "ts": time.time(), "pid": 1, "type": "pass"}),
        encoding="utf-8")
    res, _, _ = _run(tmp_path, "jugement", runs_dir=runs)
    assert res["statut"] == "verrou"                           # passe en cours -> refus, 0 écriture


def test_erreur_dune_etape_donne_statut_erreur(tmp_path):
    """archi §3.1 : une étape qui plante -> statut erreur (jamais de crash), lock relâché."""
    class BoomBrain:
        def run(self, skill):
            raise RuntimeError("boom E1")
    res = run_chain.run_chain("demo-revue", config=_config.load_config(), brain=BoomBrain(),
                              live_path=tmp_path / "x", proposals_root=tmp_path / "p",
                              runs_dir=tmp_path / "r", interactions_path=tmp_path / "i.jsonl")
    assert res["statut"] == "erreur" and "boom E1" in res["erreur"]
    assert not (tmp_path / "r" / "demo-revue.lock").exists()   # lock relâché malgré l'erreur


def test_cli_refuse_skill_absent_du_registre():
    """Le bot lance `run_chain.py --skill X` : un skill hors registre est refusé (exit 2), 0 effet."""
    assert run_chain.main(["--skill", "zzz_inexistant"]) == 2


def test_invariant_spy_run_chain_source():
    """HARN-202 : run_chain n'utilise JAMAIS `from muscle import run_pass` (import-module only)."""
    src = (SKILL_ROOT / "lib" / "run_chain.py").read_text(encoding="utf-8")
    assert spy.assert_no_forbidden_rebind(src, ["run_pass"]) == []


def test_route_sur_vraie_classification_iterer():
    """Régression : iterer RÉEL émet le champ `type` (pas `type_itere`). route() doit le lire.
    Fixture = sortie réelle du pipeline iterer, MIXTE (7 contrainte_dure, 2 regle_detecteur,
    2 bloque_input_externe, 1 jugement) -> prouve le routage par retour sur du vrai."""
    real = json.loads((FIX / "iterer_real_sample" / "classification.json").read_text(encoding="utf-8"))
    r = run_chain.route(real)
    types = {i["type_itere"] for i in r["items"]}
    assert types == {"contrainte_dure", "regle_detecteur", "bloque_input_externe", "jugement"}  # champ `type` lu
    by_type = {i["type_itere"]: i["remede_route"] for i in r["items"]}
    assert by_type["contrainte_dure"] == "prose_muscle" and by_type["jugement"] == "jugement_iterer"
    assert by_type["bloque_input_externe"] == "mis_de_cote"
    assert r["branche"] == "prose"          # priorité prose > jugement (des retours factuels existent)


def test_prose_s1_pilotee_par_real_agents_fake_client(tmp_path):
    """Les agents LLM RÉELS (interface RealAgents, backend fake déterministe) pilotent le muscle
    jusqu'à une proposition — prouve la compatibilité drop-in du moteur IA câblé (point 1)."""
    import bridge
    llm_agents = bridge.import_muscle("llm_agents")
    real_agents = llm_agents.RealAgents(client=llm_agents._FakeClient())
    res, tp, live = _run(tmp_path, "prose_s1", run_id="ac_ra", agents=real_agents)
    assert res["muscle_invoked"] is True and res["statut"] == "propose" and res["ship"] is True
    # rewrite + judge ont bien été appelés via l'interface RealAgents (diagnose court-circuité = injecté)
    assert real_agents.calls >= 2
    cand = (tp / "prop" / "demo-revue" / "date" / "candidate.md").read_text(encoding="utf-8")
    assert "anti-redite" in cand                      # le garde-fou rédigé par le rewriter est présent
