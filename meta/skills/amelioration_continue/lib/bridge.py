#!/usr/bin/env python3
"""bridge.py -- soudure iterer -> muscle (soudures #1-3, archi §2.3, data_model §2).

Traduit le contrat `auto_improver_call.json` d'iterer en une invocation reelle de
`skill_auto_improver_v2.run_pass` :
  1. construit le `golden_sealed` du muscle (VRAI schema : id, input, assertions[], source,
     source_session_id -- input+source_session_id OBLIGATOIRES sinon target_runner.validate_schema
     rejette). Sert l'ISOLATION (assert_no_golden_leak), pas le scoring. Held-out ABSENT par
     construction. Desambiguisation `sid#k` (SIM-201 : plusieurs rates d'une session partagent le sid).
  2. injecte les rates/diagnostic d'iterer (retouche B -> pas de re-mining/re-diagnostic).
  3. clampe max_iter 5->3 (loggue le clamp).
Garde-fous : `delegation_status == VERIFIE_V2`, `test_case_ids ∩ holdout_case_ids == ∅`, et
ASSERTION DURE `payload_muscle ∩ holdout_ids == ∅` avant tout appel (double digue a la frontiere).

Le bridge n'appelle PAS le muscle : il PREPARE l'appel (kwargs). C'est run_chain (S3) qui invoque.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

CLAMP_MAX_ITER = 3


class BridgeError(RuntimeError):
    """Contrat iterer invalide (delegation non verifiee, test∩holdout non vide, schema muscle KO)."""


# --- Acces au muscle (imports Python, cf. archi §5) --------------------------

def resolve_muscle_path() -> Path:
    """MUSCLE_PATH (env) sinon le sibling `meta/skills/skill_auto_improver_v2`."""
    env = os.environ.get("MUSCLE_PATH")
    if env:
        return Path(env)
    return SKILL_ROOT.parent / "skill_auto_improver_v2"


def import_muscle(module_name: str):
    """Importe un module du muscle (target_runner, orchestrator, keep_revert, ...) en l'ayant
    sur sys.path. Le muscle s'importe par ses noms de modules courts (lib/ ajoute au path)."""
    lib = resolve_muscle_path() / "lib"
    if not lib.exists():
        raise BridgeError(f"muscle introuvable : {lib} (configurer MUSCLE_PATH ?)")
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    return importlib.import_module(module_name)


# --- Garde-fous du contrat ---------------------------------------------------

def validate_contract(contract: dict) -> None:
    if contract.get("delegation_status") != "VERIFIE_V2":
        raise BridgeError(
            f"delegation_status={contract.get('delegation_status')!r} != VERIFIE_V2 -> stop propre")
    test_ids = set(contract.get("test_case_ids", []))
    holdout_ids = set(contract.get("holdout_case_ids", []))
    inter = test_ids & holdout_ids
    if inter:
        raise BridgeError(f"test_case_ids ∩ holdout_case_ids != ∅ : {sorted(inter)}")
    for regle in contract.get("regles_a_detecteur", []):
        leaked = set(regle.get("attendu_par_cas", {})) & holdout_ids
        if leaked:
            raise BridgeError(f"held-out dans attendu_par_cas : {sorted(leaked)}")


# --- Soudure #1 : golden_sealed ----------------------------------------------

def build_golden_sealed(contract: dict, case_inputs: dict, source_sessions: dict,
                        assertions_by_case: dict | None = None, sealed_at: str = "unknown") -> dict:
    """Construit un `golden_sealed` VALIDE (schema muscle). Held-out exclu (double digue).
    `case_inputs[cid]` et `source_sessions[cid]` sont OBLIGATOIRES (sinon validate_schema rejette)."""
    validate_contract(contract)
    skill = Path(contract["skill_path"]).name
    holdout = set(contract.get("holdout_case_ids", []))
    assertions_by_case = assertions_by_case or {}

    cases = []
    seen_sid: dict[str, int] = {}
    for cid in contract["test_case_ids"]:
        if cid in holdout:  # assertion dure (double digue) -- ne devrait jamais arriver post-validate
            raise BridgeError(f"held-out {cid} present dans test_case_ids")
        if cid not in case_inputs:
            raise BridgeError(f"input manquant pour le cas {cid} (obligatoire)")
        if cid not in source_sessions:
            raise BridgeError(f"source_session_id manquant pour le cas {cid} (obligatoire)")
        sid = source_sessions[cid]
        k = seen_sid.get(sid, 0)          # SIM-201 : desambiguisation sid#k
        seen_sid[sid] = k + 1
        cases.append({
            "id": cid,
            "input": case_inputs[cid],
            "assertions": assertions_by_case.get(cid) or [{"check": "profondeur_alignee", "op": "pass"}],
            "source": "contrat_iterer",
            "source_session_id": f"{sid}#{k}",
        })
    sealed = {"skill": skill, "cases": cases, "sealed_at": sealed_at}

    # Validation contre le VRAI schema du muscle (fail-closed).
    problems = import_muscle("target_runner").validate_schema(cases)
    if problems:
        raise BridgeError(f"golden_sealed invalide (schema muscle) : {problems}")
    return sealed


# --- Soudure #3 : clamp ------------------------------------------------------

def clamp_max_iter(contract: dict, log=None) -> int:
    raw = int(contract.get("max_iter", 5))
    clamped = min(raw, CLAMP_MAX_ITER)
    if clamped != raw and log is not None:
        log(f"[bridge] clamp max_iter {raw}->{clamped}")
    return clamped


# --- Assertion dure held-out (double digue a la frontiere) -------------------

def assert_no_holdout_leak(payload: dict, holdout_ids) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    toks = set(re.findall(r"[A-Za-z0-9_]+", text))
    leaked = toks & set(holdout_ids)
    assert not leaked, f"held-out fuite dans le payload muscle : {sorted(leaked)}"


# --- Assemblage : kwargs prets pour run_pass ---------------------------------

def prepare_muscle_call(contract: dict, case_inputs: dict, source_sessions: dict,
                        rates: list, diagnosis: dict,
                        assertions_by_case: dict | None = None, log=None) -> dict:
    """Retourne les kwargs de `muscle.run_pass` : skill, golden_sealed, rates, diagnosis, max_iter
    (clampe). ASSERTION DURE held-out AVANT de rendre les kwargs (aucun appel muscle ici)."""
    sealed = build_golden_sealed(contract, case_inputs, source_sessions, assertions_by_case)
    max_iter = clamp_max_iter(contract, log=log)
    holdout_ids = contract.get("holdout_case_ids", [])
    payload = {"golden_sealed": sealed, "rates": rates, "diagnosis": diagnosis}
    assert_no_holdout_leak(payload, holdout_ids)
    return {
        "skill": sealed["skill"],
        "golden_sealed": sealed,
        "rates": rates,
        "diagnosis": diagnosis,
        "max_iter": max_iter,
        "fixture_source": None,
    }


if __name__ == "__main__":
    print(__doc__)
