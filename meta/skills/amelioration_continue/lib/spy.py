#!/usr/bin/env python3
"""spy.py -- observation NON-GAMABLE des flags critiques de la chaine (HARN-001/HARN-101/HARN-202).

Les flags critiques (`muscle_invoked`, `regression_gate_ran`, `muscle_max_iter`,
`telegram_messages_sent`) ne sont JAMAIS lus dans l'auto-declaration de `run_chain.py` : ils sont
observes via un spy que le RUNNER (`grade_chain.py`) injecte, hors de portee de la chaine.

Invariant d'injection (HARN-101/HARN-202) : le muscle etant importe in-process, on l'instrumente
par IMPORT-MODULE (`import muscle_orchestrator; muscle_orchestrator.run_pass = wrapped`), et le
runner monkeypatche AVANT d'importer `run_chain`. Un module qui ferait `from muscle_orchestrator
import run_pass` capturerait une reference locale que le patch ne verrait pas -> `assert_no_forbidden_rebind`
detecte ce contournement (test-gardien S13-spy).
"""
from __future__ import annotations

import ast
import functools
import json
from pathlib import Path


# --- Spy live : install / uninstall / derive ---------------------------------

def install(module, attr: str, log_path, capture: tuple[str, ...] = ()):
    """Enveloppe `module.attr` pour logguer chaque appel dans `log_path` (JSONL append).
    Retourne l'original (a repasser a `uninstall`). Le comportement est preserve."""
    original = getattr(module, attr)
    log_path = Path(log_path)

    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        entry = {"call": attr}
        for name in capture:
            if name in kwargs:
                entry[name] = kwargs[name]
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return original(*args, **kwargs)

    setattr(module, attr, wrapper)
    return original


def uninstall(module, attr: str, original) -> None:
    setattr(module, attr, original)


def _load_calls(source) -> list[dict]:
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return list(source)


def derive_flags(source) -> dict:
    """Derive les flags critiques depuis un `spy_calls.jsonl` (chemin) ou une liste de dicts."""
    calls = _load_calls(source)
    run_pass_calls = [c for c in calls if c.get("call") == "run_pass"]
    return {
        "muscle_invoked": len(run_pass_calls) > 0,
        "muscle_max_iter": run_pass_calls[0].get("max_iter") if run_pass_calls else None,
        "regression_gate_ran": any(c.get("call") == "regression_gate" for c in calls),
        "telegram_messages_sent": sum(1 for c in calls if c.get("call") == "telegram_send"),
    }


# --- Gardien anti-rebind (S13-spy) -------------------------------------------

def assert_no_forbidden_rebind(source_text: str, spied_names: list[str]) -> list[str]:
    """Retourne la liste des violations : tout `from <mod> import <spied>` (avec ou sans alias)
    capture une reference locale non-patchable. Vide = conforme (import-module only)."""
    violations: list[str] = []
    tree = ast.parse(source_text)
    spied = set(spied_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in spied:
                    mod = node.module or "?"
                    as_part = f" as {alias.asname}" if alias.asname else ""
                    violations.append(
                        f"from {mod} import {alias.name}{as_part} : rebind non-patchable "
                        f"du callable spie '{alias.name}' (utiliser 'import {mod}' + '{mod}.{alias.name}')"
                    )
    return violations


def assert_module_file_safe(path, spied_names: list[str]) -> list[str]:
    """Meme gardien, applique au source d'un fichier (utilise par grade_chain avant capability)."""
    return assert_no_forbidden_rebind(Path(path).read_text(encoding="utf-8"), spied_names)
