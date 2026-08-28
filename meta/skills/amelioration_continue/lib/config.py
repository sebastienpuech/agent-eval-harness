#!/usr/bin/env python3
"""config.py -- resolution des chemins (ITERER_PATH/MUSCLE_PATH/SKILLS_ROOT) + registre des skills.

`config.json` (gitignore, non commite) ou variables d'env fournissent les 3 racines. Defauts =
siblings dans meta/skills/. `references/skills_registry.json` (VERSIONNE) mappe nom de skill ->
chemin absolu du SKILL.md live ; `ameliore <skill>` REFUSE tout skill absent du registre (jamais
d'ecriture sur un chemin devine, archi §7).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_JSON = SKILL_ROOT / "config.json"
DOTENV = SKILL_ROOT / ".env"
# Registre : externalisé. Le registre qui liste les vraies cibles vit HORS de ce dépôt ; on le
# branche via AMELIORE_REGISTRY (env/.env), qui pointe vers son chemin absolu. Défaut = l'exemple
# NEUTRE versionné ci-dessous (le moteur publiable ne contient aucune cible réelle).
REGISTRY_EXAMPLE = SKILL_ROOT / "references" / "skills_registry.example.json"


def _defaults() -> dict:
    meta_skills = SKILL_ROOT.parent  # .../meta/skills
    return {
        "ITERER_PATH": str(meta_skills / "iterer-sur-retours"),
        "MUSCLE_PATH": str(meta_skills / "skill_auto_improver_v2"),
        "SKILLS_ROOT": str(meta_skills.parent.parent),  # racine des skills
    }


def load_config() -> dict:
    cfg = _defaults()
    if CONFIG_JSON.exists():
        cfg.update(json.loads(CONFIG_JSON.read_text(encoding="utf-8")))
    for key in ("ITERER_PATH", "MUSCLE_PATH", "SKILLS_ROOT"):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


def load_dotenv() -> None:
    """Charge les clés AMELIORE_*/racines du .env dans os.environ (opérationnel : bot/CLI).
    Best-effort, idempotent ; ne réécrit pas une variable déjà présente."""
    if not DOTENV.exists():
        return
    for line in DOTENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


def registry_path() -> Path:
    """Registre RÉEL via AMELIORE_REGISTRY (env/.env) ; sinon l'exemple neutre versionné."""
    p = os.environ.get("AMELIORE_REGISTRY")
    return Path(p) if p else REGISTRY_EXAMPLE


def load_registry() -> dict:
    path = registry_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_live_path(skill: str, registry: dict | None = None, config: dict | None = None) -> Path:
    """Chemin absolu du SKILL.md live d'un skill via le registre. Refuse proprement si absent."""
    registry = registry if registry is not None else load_registry()
    if skill not in registry or not isinstance(registry.get(skill), dict):
        raise KeyError(
            f"skill '{skill}' absent du registre ({registry_path().name}) -> refus (jamais de chemin devine)."
        )
    entry = registry[skill]
    if "live_path" in entry:  # chemin absolu explicite (override)
        return Path(entry["live_path"])
    skills_root = Path((config or load_config())["SKILLS_ROOT"])
    return skills_root / entry["live_path_rel"]
