"""Tests du gate structurel + apply gaté (oui -> gate -> commit -> push)."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import apply_gate  # noqa: E402
import apply_live  # noqa: E402

SKILL = ("---\nname: demo\ndescription: un skill de démo.\n---\n\n# demo\n\n## Regles\n- une regle.\n")


class FakeGit:
    def __init__(self):
        self.commits, self.pushed = [], False

    def commit_file(self, path, message):
        self.commits.append(message)
        return "sha-1"

    def push(self):
        self.pushed = True
        return "origin/main"


def _mk(tmp_path, candidate_text):
    d = tmp_path / "proposals" / "demo" / "d"
    d.mkdir(parents=True)
    (d / "candidate.md").write_text(candidate_text, encoding="utf-8")
    live = tmp_path / "SKILL.md"
    live.write_text(SKILL, encoding="utf-8")
    return live


def test_gate_vert_applique_commit_push(tmp_path):
    live = _mk(tmp_path, SKILL.rstrip() + "\n\n## Nouveau principe\n- ajout append-only.\n")
    git = FakeGit()
    res = apply_live.apply_with_gate("demo", "d", proposals_root=tmp_path / "proposals",
                                     live_path=live, git=git, push=True)
    assert res["ok"] and res["action"] == "applied"
    assert git.commits and git.pushed is True                 # commit + push
    assert "Nouveau principe" in live.read_text(encoding="utf-8")
    assert all(c["ok"] for c in res["gate"]["checks"])


def test_gate_rouge_frontmatter_modifie_refuse(tmp_path):
    # candidate qui CHANGE le frontmatter (description) -> triggering cassé -> refus, 0 écriture
    bad = SKILL.replace("un skill de démo.", "AUTRE description") + "\n## X\n"
    live = _mk(tmp_path, bad)
    git = FakeGit()
    res = apply_live.apply_with_gate("demo", "d", proposals_root=tmp_path / "proposals",
                                     live_path=live, git=git)
    assert res["ok"] is False and res["action"] == "refuse-gate"
    assert git.commits == [] and git.pushed is False          # RIEN commité/poussé
    assert live.read_text(encoding="utf-8") == SKILL          # live INCHANGÉ


def test_gate_rouge_suppression_refuse(tmp_path):
    bad = "---\nname: demo\ndescription: un skill de démo.\n---\n\n# demo\n"  # a supprimé ## Regles
    live = _mk(tmp_path, bad)
    git = FakeGit()
    res = apply_live.apply_with_gate("demo", "d", proposals_root=tmp_path / "proposals",
                                     live_path=live, git=git)
    assert res["ok"] is False                                 # suppression détectée (non append-only)
    assert live.read_text(encoding="utf-8") == SKILL


def test_gate_check_direct():
    ok = apply_gate.check(SKILL, SKILL.rstrip() + "\n\n## Ajout\n- x\n")
    assert ok["ok"] is True
