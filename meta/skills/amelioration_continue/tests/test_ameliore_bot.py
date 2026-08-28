"""Tests du bot (logique pure, sans python-telegram-bot). Couvre les vérifs S4 :
oui -> applique + commit + decision.jsonl ; non -> live inchangé + proposed_fixes ;
oui nu + >=2 pending -> refus + liste ; passe en cours -> refus 0 écriture ; skill inconnu -> refus."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))
sys.path.insert(0, str(SKILL_ROOT / "bot"))

import ameliore_bot as bot  # noqa: E402
import normalize_proposal  # noqa: E402
import notify  # noqa: E402


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


# SKILL.md avec frontmatter (le gate exige frontmatter intact + append-only).
LIVE = ("---\nname: demo-revue\ndescription: jugement de revue.\n---\n\n"
        "# demo-revue\n\n## Regles de fer\n- une regle existante.\n")


def _append(extra: str = "## Nouveau principe\n- ajout append-only.") -> str:
    return LIVE.rstrip() + "\n\n" + extra + "\n"


def _make_prop(proposals_root, skill, run_id, candidate=None, date="date"):
    candidate = candidate if candidate is not None else _append()
    normalize_proposal.normalize(
        "patch_prose_muscle", skill=skill, date=date, run_id=run_id, proposals_root=proposals_root,
        quoi="Garde-fou anti-redite.", pourquoi="1 rate mine.", delta="held-out 3/3 stable.",
        verdict={"ship_effectif": True}, candidate_md=candidate, diff_text="--- diff ---")


def test_oui_gate_vert_applique_commit_push_decision(tmp_path):
    pr = tmp_path / "proposals"
    _make_prop(pr, "demo-revue", "ac_1", candidate=_append("## Garde-fou anti-redite\n- relire le fil."))
    live = tmp_path / "live.md"
    live.write_text(LIVE, encoding="utf-8")
    git = MockGit()
    out = bot.handle_oui("ac_1", None, proposals_root=pr, decision_path=tmp_path / "dec.jsonl",
                         runs_dir=tmp_path / "runs", git=git, live_path=live)
    assert "Appliqu" in out
    assert "anti-redite" in live.read_text(encoding="utf-8")        # candidate append appliqué
    assert len(git.commits) == 1 and git.pushed is True            # commit + PUSH
    dec = bot.read_decisions(tmp_path / "dec.jsonl")
    assert dec["ac_1"]["decision"] == "oui" and dec["ac_1"]["applied"] is True
    assert bot.list_pending(pr, tmp_path / "dec.jsonl") == []


def test_oui_gate_rouge_refuse_rien_applique(tmp_path):
    """Un candidate qui casse le frontmatter -> gate rouge -> live inchangé, 0 commit, reste en attente."""
    pr = tmp_path / "proposals"
    bad = "---\nname: demo-revue\ndescription: DESCRIPTION MODIFIEE.\n---\n\n# demo-revue\n## X\n"
    _make_prop(pr, "demo-revue", "ac_bad", candidate=bad)
    live = tmp_path / "live.md"
    live.write_text(LIVE, encoding="utf-8")
    git = MockGit()
    out = bot.handle_oui("ac_bad", None, proposals_root=pr, decision_path=tmp_path / "dec.jsonl",
                         runs_dir=tmp_path / "runs", git=git, live_path=live)
    assert "gate" in out.lower() and git.commits == [] and git.pushed is False
    assert live.read_text(encoding="utf-8") == LIVE                # live INCHANGÉ
    assert bot.read_decisions(tmp_path / "dec.jsonl") == {}        # pas de décision -> reste en attente


def test_non_live_inchange_et_proposed_fixes(tmp_path):
    pr = tmp_path / "proposals"
    _make_prop(pr, "demo-revue", "ac_2")
    live = tmp_path / "live.md"
    live.write_text("# ANCIEN\n", encoding="utf-8")
    pf = tmp_path / "proposed_fixes.md"
    out = bot.handle_non("ac_2", "trop risque", proposals_root=pr, decision_path=tmp_path / "dec.jsonl",
                         git=MockGit(), live_path=live, proposed_fixes=pf)
    assert "Refuse" in out
    assert live.read_text(encoding="utf-8") == "# ANCIEN\n"          # live INCHANGÉ
    assert "REFUSE" in pf.read_text(encoding="utf-8") and "trop risque" in pf.read_text(encoding="utf-8")
    dec = bot.read_decisions(tmp_path / "dec.jsonl")
    assert dec["ac_2"]["decision"] == "non" and dec["ac_2"]["applied"] is False


def test_oui_nu_deux_pending_refuse_et_liste(tmp_path):
    pr = tmp_path / "proposals"
    _make_prop(pr, "demo-revue", "ac_a")
    _make_prop(pr, "skill-jugement", "ac_b")
    live = tmp_path / "live.md"
    live.write_text("# ANCIEN\n", encoding="utf-8")
    out = bot.handle_oui(None, None, proposals_root=pr, decision_path=tmp_path / "dec.jsonl",
                         runs_dir=tmp_path / "runs", git=MockGit(), live_path=live)
    assert "ac_a" in out and "ac_b" in out                          # liste renvoyée
    assert bot.read_decisions(tmp_path / "dec.jsonl") == {}          # RIEN appliqué
    assert live.read_text(encoding="utf-8") == "# ANCIEN\n"


def test_oui_sous_passe_en_cours_refuse(tmp_path):
    pr = tmp_path / "proposals"
    _make_prop(pr, "demo-revue", "ac_l")
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "demo-revue.lock").write_text(
        json.dumps({"skill": "demo-revue", "ts": time.time(), "pid": 1, "type": "pass"}),
        encoding="utf-8")
    live = tmp_path / "live.md"
    live.write_text("# ANCIEN\n", encoding="utf-8")
    out = bot.handle_oui("ac_l", None, proposals_root=pr, decision_path=tmp_path / "dec.jsonl",
                         runs_dir=runs, git=MockGit(), live_path=live)
    assert "Passe en cours" in out
    assert live.read_text(encoding="utf-8") == "# ANCIEN\n"          # 0 écriture
    assert bot.read_decisions(tmp_path / "dec.jsonl") == {}


def test_ameliore_refuse_inconnu_et_lance_connu(tmp_path):
    registry = {"demo-revue": {"live_path_rel": "x"}}
    assert "inconnu" in bot.handle_ameliore("zzz", registry=registry, config={}, runs_dir=tmp_path / "runs")
    calls = []
    out = bot.handle_ameliore("demo-revue", registry=registry, config={}, runs_dir=tmp_path / "runs",
                              launcher=lambda s, c: calls.append(s))
    assert calls == ["demo-revue"] and "lancee" in out


def test_pending_lecture_seule(tmp_path):
    pr = tmp_path / "proposals"
    _make_prop(pr, "demo-revue", "ac_p")
    out = bot.handle_pending(pr, tmp_path / "dec.jsonl")
    assert "ac_p" in out and "demo-revue" in out


def test_notify_push_lint_failclose(tmp_path):
    import pytest
    t = notify.MockTransport()
    prop = {"skill": "demo-revue", "run_id": "ac_x", "quoi": "garde-fou", "pourquoi": "1 rate", "delta": "ok"}
    notify.push(prop, t, "ac_x")
    assert len(t.sent) == 1 and "ac_x" in t.sent[0]
    with pytest.raises(ValueError):                                 # PII -> 0 envoi
        notify.push({"skill": "s", "run_id": "r", "quoi": "ecris a a@b.com", "pourquoi": "", "delta": ""}, t, "r")
    assert notify.lint_pii("contient rebase", denylist=("rebase",))                # denylist verbatim
    assert len(t.sent) == 1                                          # toujours 1 (le 2e refusé)
