#!/usr/bin/env python3
"""iterer_adapter.py -- normalise les artefacts RÉELS d'iterer -> ce que run_chain consomme.

Basé sur `references/iterer_artifacts.md` (shapes vérifiées en LANÇANT iterer). iterer est une
BOÎTE NOIRE : on lit ses artefacts, jamais ses internals, jamais d'import de son code.

Ce que run_chain (_branch_prose) a besoin de savoir :
  - classification.json (route par retour, champ `type`)            -> passthrough
  - auto_improver_call.json (contrat)                                -> passthrough
  - case_inputs / source_sessions (pour golden_sealed du muscle)     -> read_case_data (2 shapes)
  - rates / diagnosis                                                -> None (iterer ne les produit
        pas ; le muscle mine/diagnostique. Dérivation depuis collected/ = bounded, PII à scruber.)

Le SEUL point non verrouillé (cf. doc) : d'où viennent input/source_session_id des test_case_ids
quand `generated_evals.json` est au format RÉEL `{critical_checks}` (et non `{cases}`). Tant que ce
mapping n'est pas confirmé sur 1 run demo-revue, on lève `ItererShapeError` (jamais de devinette).
"""
from __future__ import annotations

import json
from pathlib import Path


class ItererShapeError(RuntimeError):
    """Un artefact iterer a une shape non encore réconciliée (cf. references/iterer_artifacts.md)."""


def _read_json(iter_dir: Path, name: str) -> dict:
    return json.loads((Path(iter_dir) / name).read_text(encoding="utf-8"))


def read_classification(iter_dir: Path) -> dict:
    return _read_json(iter_dir, "classification.json")


def read_contract(iter_dir: Path) -> dict:
    return _read_json(iter_dir, "auto_improver_call.json")


def read_case_data(iter_dir: Path, contract: dict) -> tuple[dict, dict]:
    """Retourne (case_inputs, source_sessions) pour les test_case_ids du contrat.

    Gère 2 shapes de `evals_file` :
      - `{"cases": {cid: {"input": ..., "source_session_id": ...}}}` (nos fixtures / format cible)
        -> résolution directe ;
      - `{"critical_checks": [...]}` (format RÉEL iterer observé) -> mapping input/sid NON verrouillé
        -> ItererShapeError explicite (à résoudre sur 1 run demo-revue, cf. doc).
    """
    evals_file = contract.get("evals_file", "generated_evals.json")
    data = _read_json(iter_dir, evals_file)
    test_ids = contract.get("test_case_ids", [])

    if isinstance(data.get("cases"), dict):
        cases = data["cases"]
        missing = [c for c in test_ids if c not in cases]
        if missing:
            raise ItererShapeError(f"cases manquants dans {evals_file} : {missing}")
        case_inputs = {c: cases[c]["input"] for c in test_ids}
        source_sessions = {c: cases[c]["source_session_id"] for c in test_ids}
        return case_inputs, source_sessions

    if "critical_checks" in data:
        raise ItererShapeError(
            f"{evals_file} est au format RÉEL iterer `{{critical_checks}}` : il ne porte NI `input` "
            "NI `source_session_id` par cas. Mapping à verrouiller sur 1 run iterer demo-revue "
            "(source probable : evals du skill cible + collected/_manifest_<skill>.json). "
            "Cf. references/iterer_artifacts.md."
        )

    raise ItererShapeError(f"shape inconnue pour {evals_file} : clés {sorted(data)[:6]}")


def read_rates(iter_dir: Path, skill: str | None = None) -> list | None:
    """iterer ne produit pas de `rates.json`. Défaut None => le muscle mine lui-même (retouche B).
    (Dérivation depuis collected/<skill>_*.json = bounded, exige un scrub PII — non fait ici.)"""
    p = Path(iter_dir) / "rates.json"
    return _read_json(iter_dir, "rates.json")["rates"] if p.exists() else None


def read_diagnosis(iter_dir: Path) -> dict | None:
    """iterer ne diagnostique pas. Défaut None => le muscle diagnostique (retouche B l'autorise)."""
    p = Path(iter_dir) / "diagnosis.json"
    return _read_json(iter_dir, "diagnosis.json") if p.exists() else None


def read_pass(iter_dir: Path) -> dict:
    """Vue normalisée d'une passe iterer (lève ItererShapeError si case_data non réconciliable)."""
    contract = read_contract(iter_dir)
    case_inputs, source_sessions = read_case_data(iter_dir, contract)
    return {
        "classification": read_classification(iter_dir),
        "contract": contract,
        "case_inputs": case_inputs,
        "source_sessions": source_sessions,
        "rates": read_rates(iter_dir),
        "diagnosis": read_diagnosis(iter_dir),
    }
