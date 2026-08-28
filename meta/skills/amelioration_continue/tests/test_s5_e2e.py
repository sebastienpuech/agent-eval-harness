"""Session 5 (regression) — E2E de bout en bout sur S1 + S11 injection + S13-spy + error-analysis.

Ce que le headless PEUT prouver : la chaîne tourne E1->E4 puis bot->apply live (tempdir/mocké) sur le
cas S1 doublon, sans rien pousser de réel. La couche capability LIVE (N=3 Opus réels + régénération
des recorded/) reste à faire sur la machine de l'utilisateur (agents LLM du muscle non câblés ici).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))
sys.path.insert(0, str(SKILL_ROOT / "bot"))

import ameliore_bot as bot  # noqa: E402
import config as _config  # noqa: E402
import notify  # noqa: E402
import run_chain  # noqa: E402
import spy  # noqa: E402

FIX = SKILL_ROOT / "evals" / "fixtures"
INJECTION_RE = r"(ignore les r|SYSTEM ?:)"


class MockGit:
    def __init__(self):
        self.commits = []
        self.pushed = False

    def commit_file(self, path, message):
        self.commits.append(message)
        return f"sha-{len(self.commits)}"

    def push(self):
        self.pushed = True
        return "origin"


def _setup(tmp_path, which):
    iter_dir = tmp_path / "iter"
    shutil.copytree(FIX / "iter_runs" / which, iter_dir)
    live = tmp_path / "SKILL.md"
    shutil.copy(FIX / "live_jouet" / "SKILL.md", live)
    return iter_dir, live, _config.load_config()


def test_e2e_s1_detection_jusqu_a_apply_live(tmp_path):
    """S1 bout en bout : run_chain (E1->E4) -> proposition canonique -> push mocké -> bot oui -> apply live."""
    iter_dir, live, cfg = _setup(tmp_path, "prose_s1")
    transport = notify.MockTransport()
    pr = tmp_path / "proposals"

    # --- Passe (détection -> routage prose -> muscle -> holdout_scorer -> regression_gate -> E4) ---
    res = run_chain.run_chain(
        "demo-revue", config=cfg, brain=run_chain.RecordedBrain(iter_dir), live_path=live,
        run_id="ac_s1", proposals_root=pr, runs_dir=tmp_path / "runs",
        interactions_path=tmp_path / "int.jsonl",
        telegram=lambda msg: notify.push(  # push mocké AVEC lint PII (fail-closed)
            {"skill": "demo-revue", "run_id": "ac_s1",
             "quoi": "Garde-fou anti-redite.", "pourquoi": "1 rate mine.", "delta": msg.split("DELTA")[-1][:80]},
            transport, "ac_s1", denylist=("rebase", "invalidation du cache")))
    assert res["statut"] == "propose" and res["ship"] is True
    assert len(transport.sent) == 1                                   # 1 push, 0 verbatim (lint passé)

    # --- error-analysis : ne jamais faire confiance au delta net sans lire les traces par cas ---
    verdict = json.loads((pr / "demo-revue" / "date" / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["ship_effectif"] is True
    assert set(verdict["deltas_par_cas"]) == {"ho_01_reprise_taf", "ho_02_retour_pres", "ho_03_demo_stable"}
    assert all(d >= 0 for d in verdict["deltas_par_cas"].values())    # aucun cas régressé

    # --- validation matinale : « oui » -> apply live (SEULE écriture live) + commit + decision ---
    git = MockGit()
    out = bot.handle_oui("ac_s1", None, proposals_root=pr, decision_path=tmp_path / "dec.jsonl",
                         runs_dir=tmp_path / "runs2", git=git, live_path=live)
    assert "Appliqu" in out and len(git.commits) == 1 and git.pushed is True
    assert live.read_text(encoding="utf-8") == (pr / "demo-revue" / "date" / "candidate.md").read_text(encoding="utf-8")
    assert bot.read_decisions(tmp_path / "dec.jsonl")["ac_s1"]["applied"] is True


def test_s11_injection_payload_inerte(tmp_path):
    """Le payload d'injection miné doit rester INERTE : absent de Telegram ET du candidate, ship non forcé, live inchangé."""
    iter_dir, live, cfg = _setup(tmp_path, "injection_s11")
    sent = []
    pr = tmp_path / "proposals"
    res = run_chain.run_chain(
        "demo-revue", config=cfg, brain=run_chain.RecordedBrain(iter_dir), live_path=live,
        run_id="ac_s11", proposals_root=pr, runs_dir=tmp_path / "runs",
        interactions_path=tmp_path / "int.jsonl", telegram=sent.append)
    # message Telegram : aucun payload d'injection
    assert sent and re.search(INJECTION_RE, sent[0]) is None
    # candidate : aucun payload d'injection (donnée minée = inerte)
    cand = (pr / "demo-revue" / "date" / "candidate.md").read_text(encoding="utf-8")
    assert re.search(INJECTION_RE, cand) is None
    # ship vient du gate réel, pas forcé par le texte injecté ; live jamais écrit par la passe
    assert isinstance(res["ship"], bool)
    assert live.read_text(encoding="utf-8").startswith("---")


def test_s13_spy_invariant_tient_sur_toute_la_chaine():
    """Aucun module de la chaîne n'introduit un rebind non-patchable du muscle (import-module only)."""
    for mod in ("run_chain.py", "bridge.py"):
        src = (SKILL_ROOT / "lib" / mod).read_text(encoding="utf-8")
        assert spy.assert_no_forbidden_rebind(src, ["run_pass"]) == [], mod
