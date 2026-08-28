#!/usr/bin/env python3
"""target_golden.py -- gate de non-régression GÉNÉRAL : le GOLDEN du skill cible, avant vs après patch.

Le veto E3 (held-out + 1 instrument) mesure la DIMENSION ciblée sur un ÉCHANTILLON. Insuffisant :
un patch peut améliorer sa cible et casser une AUTRE capacité. Ce gate exécute le golden COMPLET du
skill cible sur (live actuel) puis (candidate patché) et REFUSE toute proposition qui régresse.

Contrat `golden_cmd` (dans skills_registry.json, par skill) : une liste d'arguments avec le
placeholder `{skill_md}` ; la commande évalue le skill sur le SKILL.md fourni et imprime sur stdout
un JSON contenant `pass_rate` (0..1). Ex. ["python", "tests/run_golden.py", "{skill_md}"].

Skill SANS golden_cmd -> non vérifiable : on ne bloque pas en silence, on PROPOSE avec le drapeau
`non_regression_verifiee=false` (l'humain sait qu'il valide sans filet automatique).
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path


def golden_cmd_for(skill: str, registry: dict) -> list | None:
    return (registry.get(skill) or {}).get("golden_cmd")


def _run_golden(cmd_template: list, skill_md_path: Path, cwd: Path, timeout: int = 900) -> float | None:
    cmd = [str(a).replace("{skill_md}", str(skill_md_path)) for a in cmd_template]
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    m = re.search(r'"pass_rate"\s*:\s*([0-9]*\.?[0-9]+)', proc.stdout or "")
    return float(m.group(1)) if m else None


def check_no_regression(skill: str, live_path, candidate_text: str, registry: dict,
                        cwd, epsilon: float = 1e-9) -> dict:
    """Retourne {verifiable, regression, rate_before, rate_after, reason}. regression=True -> REFUS."""
    cmd = golden_cmd_for(skill, registry)
    if not cmd:
        return {"verifiable": False, "regression": False,
                "reason": "aucun golden_cmd dans le registre -> non-régression NON vérifiée"}
    before = _run_golden(cmd, Path(live_path), Path(cwd))
    tmp_dir = Path(tempfile.mkdtemp())
    tmp = tmp_dir / "SKILL.md"
    tmp.write_text(candidate_text, encoding="utf-8")
    after = _run_golden(cmd, tmp, Path(cwd))
    if before is None or after is None:
        return {"verifiable": False, "regression": False, "rate_before": before, "rate_after": after,
                "reason": "le golden n'a pas renvoyé de pass_rate exploitable"}
    regression = after < before - epsilon
    return {"verifiable": True, "regression": regression, "rate_before": round(before, 4),
            "rate_after": round(after, 4),
            "reason": f"golden cible {before}->{after}" + (" (REGRESSION)" if regression else " (OK)")}
