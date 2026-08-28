#!/usr/bin/env python3
"""grade_chain.py -- runner du golden de la CHAINE (spec §10bis/§10ter). 0 LLM en regression.

Deux suites :
  - regression (S4-S12) : rejoue les artefacts ENREGISTRES (evals/fixtures/recorded/<scenario>/),
    applique des checks binaires. Deterministe, < 2 min, a CHAQUE commit.
  - capability (S1-S3) : sous-skills REELS (Opus), N=3, >=2/3. DIFFERE tant que run_chain n'existe
    pas (arrive en S3). Quand il existera : monkeypatch du spy AVANT import run_chain (HARN-101).

Anti-gaming : les flags critiques (muscle_invoked, telegram_messages_sent, muscle_max_iter,
regression_gate_ran) sont derives d'un spy_calls.jsonl, jamais de l'auto-declaration de la chaine.
Le check `detector_fires` est COMPORTEMENTAL : il execute le detecteur-script sur des fixtures gelees.

CLI :
  python grade_chain.py --suite regression   # rejoue la regression (defaut)
  python grade_chain.py --mvp                # gate MVP {S1,S4,S7,S11}
  python grade_chain.py --suite capability   # leve ChainNotBuilt tant que run_chain absent
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spy  # noqa: E402
from detectors import doublon  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
EVALS = SKILL_ROOT / "evals"
EVALS_JSON = EVALS / "evals.json"

MVP_BLOCKING = {"S1_doublon", "S4_fuite_golden", "S7_silence", "S11_injection"}
SPIED_CALLABLES = ["run_pass"]  # callables du muscle instrumentes par le spy


class ChainNotBuilt(RuntimeError):
    """run_chain.py n'existe pas encore (capability live indisponible avant Session 3)."""


def load_evals() -> dict:
    return json.loads(EVALS_JSON.read_text(encoding="utf-8"))


def _get_case(name: str) -> dict:
    for tc in load_evals()["test_cases"]:
        if tc["name"] == name:
            return tc
    raise KeyError(name)


# --- Resolution des artefacts recorded ---------------------------------------

def _load_recorded(tc: dict) -> tuple[dict, dict]:
    """Retourne (artifacts, spy_flags) pour un scenario recorded."""
    rec_dir = EVALS / tc["recorded"]
    artifacts = json.loads((rec_dir / "artifacts.json").read_text(encoding="utf-8"))
    spy_flags = spy.derive_flags(rec_dir / "spy_calls.jsonl")
    return artifacts, spy_flags


# --- Evaluation d'un check ---------------------------------------------------

def _detector_fires(check: dict) -> bool:
    """Comportemental : execute doublon.py sur une fixture gelee. `on` relatif a evals/."""
    on_path = EVALS / check["on"]
    draft = on_path.read_text(encoding="utf-8")
    meta = json.loads((on_path.parent / "meta.json").read_text(encoding="utf-8"))
    fired = doublon.fires(draft, meta["sent_by_user"])
    return fired == check["value"]


def _eval_check(check: dict, artifacts: dict, spy_flags: dict) -> dict:
    kind = check["check"]
    ok = False
    detail = ""
    try:
        if kind == "detector_fires":
            ok = _detector_fires(check)
            detail = f"on={check['on']} attendu fire={check['value']}"
        elif kind == "equals":
            ok = artifacts.get(check["target"]) == check["value"]
            detail = f"{check['target']}={artifacts.get(check['target'])!r} == {check['value']!r}"
        elif kind == "contains":
            hay = artifacts.get(check["target"], "")
            ok = check["value"] in hay
            detail = f"{check['value']!r} in {check['target']}"
        elif kind == "regex_absent":
            hay = artifacts.get(check["target"], "") or ""
            ok = re.search(check["value"], hay) is None
            detail = f"/{check['value']}/ absent de {check['target']}"
        elif kind == "spy_equals":
            ok = spy_flags.get(check["target"]) == check["value"]
            detail = f"spy.{check['target']}={spy_flags.get(check['target'])!r} == {check['value']!r}"
        elif kind == "disjoint":
            a = set(artifacts.get(check["target_a"], []) or [])
            b = set(artifacts.get(check["target_b"], []) or [])
            ok = a.isdisjoint(b)
            detail = f"{check['target_a']} ∩ {check['target_b']} == ∅"
        else:
            detail = f"check inconnu: {kind}"
    except Exception as e:  # un check qui plante = echec explicite, jamais un pass silencieux
        ok, detail = False, f"ERREUR {kind}: {e}"
    return {"check": kind, "ok": ok, "detail": detail}


# --- Grading d'un scenario / d'une suite -------------------------------------

def grade_scenario(name: str) -> dict:
    tc = _get_case(name)
    if tc.get("pending_feature"):
        return {"name": name, "status": "skip",
                "reason": f"feature non construite : {tc.get('feature', '?')}", "checks": []}
    artifacts, spy_flags = _load_recorded(tc)
    checks = [_eval_check(c, artifacts, spy_flags) for c in tc["critical_checks"]]
    status = "pass" if all(c["ok"] for c in checks) else "fail"
    return {"name": name, "status": status, "blocking": tc.get("blocking", False),
            "checks": checks}


def grade_suite(suite: str) -> list[dict]:
    ev = load_evals()
    names = ev["suites"].get(suite, [])
    return [grade_scenario(n) for n in names]


def mvp_gate() -> tuple[bool, list[dict]]:
    results = [grade_scenario(n) for n in sorted(MVP_BLOCKING)]
    ok = all(r["status"] == "pass" for r in results)
    return ok, results


# --- Capability live (differe : run_chain absent avant S3) -------------------

def capability_run(name: str):
    """Rejoue un scenario capability EN LIVE. Invariant HARN-101 : monkeypatch le spy AVANT
    d'importer run_chain. Tant que run_chain n'existe pas -> ChainNotBuilt (pas un crash)."""
    run_chain_path = SKILL_ROOT / "lib" / "run_chain.py"
    if not run_chain_path.exists():
        raise ChainNotBuilt(
            "lib/run_chain.py absent (orchestrateur construit en Session 3). "
            "La suite capability live sera activee a partir de S3/S5."
        )
    # Gardien anti-rebind AVANT tout import de la chaine (HARN-202).
    for mod_file in (run_chain_path, SKILL_ROOT / "lib" / "bridge.py"):
        if mod_file.exists():
            viols = spy.assert_module_file_safe(mod_file, SPIED_CALLABLES)
            if viols:
                raise RuntimeError(f"invariant spy viole dans {mod_file.name} : {viols}")
    raise ChainNotBuilt("capability live sera cablee avec run_chain (S3+).")  # pragma: no cover


# --- CLI ---------------------------------------------------------------------

def _print(results: list[dict]) -> None:
    for r in results:
        mark = {"pass": "OK  ", "fail": "FAIL", "skip": "skip"}[r["status"]]
        blk = " [MVP]" if r.get("blocking") else ""
        print(f"  [{mark}] {r['name']}{blk}"
              + (f"  ({r.get('reason')})" if r["status"] == "skip" else ""))
        if r["status"] == "fail":
            for c in r["checks"]:
                if not c["ok"]:
                    print(f"         - {c['check']}: {c['detail']}")


def main(argv: list[str]) -> int:
    if "--mvp" in argv:
        ok, results = mvp_gate()
        print("=== GATE MVP {S1,S4,S7,S11} ===")
        _print(results)
        print("\n=> MVP VERT" if ok else "\n=> MVP ROUGE")
        return 0 if ok else 1

    suite = "regression"
    if "--suite" in argv:
        suite = argv[argv.index("--suite") + 1]
    if suite == "capability":
        try:
            capability_run("S1_doublon")
        except ChainNotBuilt as e:
            print(f"[capability] indisponible : {e}")
            return 0
    results = grade_suite(suite)
    print(f"=== SUITE {suite} ===")
    _print(results)
    fails = [r for r in results if r["status"] == "fail"]
    print(f"\n=> {suite}: {sum(1 for r in results if r['status']=='pass')} pass, "
          f"{sum(1 for r in results if r['status']=='skip')} skip, {len(fails)} fail")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
