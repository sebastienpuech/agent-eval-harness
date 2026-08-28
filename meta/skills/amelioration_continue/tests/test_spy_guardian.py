"""S13-spy : test-gardien de l'invariant anti-rebind (HARN-202).

Le muscle est importe in-process. Un spy monkeypatche `module.attr` ; il est GAMABLE si un
module instrumente fait `from module import attr` au top-level (capture une reference locale
non-patchable). Le gardien detecte cette tentative de rebind. Prouve aussi le round-trip
install -> log -> derive_flags.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import spy  # noqa: E402


# --- Le gardien anti-rebind ---

def test_import_module_est_ok():
    source = (
        "import muscle_orchestrator\n"
        "def run(): return muscle_orchestrator.run_pass(x)\n"
    )
    violations = spy.assert_no_forbidden_rebind(source, spied_names=["run_pass"])
    assert violations == []


def test_from_import_du_callable_spie_est_detecte():
    source = (
        "from muscle_orchestrator import run_pass\n"
        "def run(): return run_pass(x)\n"
    )
    violations = spy.assert_no_forbidden_rebind(source, spied_names=["run_pass"])
    assert violations, "un from-import du callable spie doit etre DETECTE (rebind)"
    assert any("run_pass" in v for v in violations)


def test_from_import_avec_alias_est_detecte():
    source = "from muscle_orchestrator import run_pass as rp\n"
    violations = spy.assert_no_forbidden_rebind(source, spied_names=["run_pass"])
    assert violations, "un alias sur le callable spie contourne aussi le patch -> detecte"


def test_from_import_dun_autre_symbole_est_ok():
    source = "from muscle_orchestrator import MAX_ITER\n"
    violations = spy.assert_no_forbidden_rebind(source, spied_names=["run_pass"])
    assert violations == []


# --- Round-trip du spy live ---

def test_install_logue_et_derive_flags(tmp_path):
    import types
    mod = types.ModuleType("fake_muscle")
    mod.run_pass = lambda skill, max_iter=5: {"ok": skill, "iters": max_iter}
    log = tmp_path / "spy_calls.jsonl"

    original = spy.install(mod, "run_pass", log, capture=("max_iter",))
    out = mod.run_pass("demo-revue", max_iter=3)  # appel instrumente
    assert out == {"ok": "demo-revue", "iters": 3}  # comportement preserve

    flags = spy.derive_flags(log)
    assert flags["muscle_invoked"] is True
    assert flags["muscle_max_iter"] == 3

    spy.uninstall(mod, "run_pass", original)
    assert mod.run_pass is original


def test_derive_flags_silence():
    flags = spy.derive_flags([{"call": "run_pass", "max_iter": 3}])
    assert flags["telegram_messages_sent"] == 0
    assert flags["regression_gate_ran"] is False
