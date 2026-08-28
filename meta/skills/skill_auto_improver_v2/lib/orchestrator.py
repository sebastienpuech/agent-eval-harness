#!/usr/bin/env python3
"""orchestrator.py -- pilote la passe par skill (writer unique, circuit-breaker).

Boucle (archi §2.1/§3, patch PRAG-004 max_iter=3) :
  CAPTURE -> DIAGNOSTIC -> [ REWRITER -> valide append-only -> JUGE -> keep/revert ] x k -> PROPOSITION
  - writer UNIQUE : ecritures serialisees (boucle Python, pas de parallelisme).
  - max_iter = 3 ; ARRET a 3 reverts consecutifs (plateau).
  - N'ECRIT JAMAIS sur le skill LIVE : seulement proposals/ (sandbox). Le live = apply_proposal.py.
  - Les sous-agents (diagnostic/rewriter/juge) sont INJECTES -> mockables en test, LLM reels en S6.

CLI :
  python orchestrator.py --self-test
"""
from __future__ import annotations

import difflib
import json
import sys
import tempfile
from pathlib import Path

import extractor
import isolation
import keep_revert
import patch_validator
import propose

SKILL_ROOT = Path(__file__).resolve().parent.parent
MAX_ITER = 3
MAX_CONSECUTIVE_REVERTS = 3


def _unified_diff(original: str, candidate: str) -> str:
    return "".join(difflib.unified_diff(original.splitlines(keepends=True),
                                        candidate.splitlines(keepends=True),
                                        fromfile="live", tofile="candidate"))


def run_pass(skill: str, live_path: Path, agents, git, base_dir: Path, date: str,
             max_iter: int = MAX_ITER, golden_sealed: dict | None = None,
             rates: list | None = None, diagnosis: dict | None = None,
             fixture_source=None) -> dict:
    """Une passe. Retourne un resume. N'ECRIT jamais sur live_path (invariant G7).

    GATE ISOLATION (patch red-team #1) : si `golden_sealed` est fourni, on verifie que le contexte
    REELLEMENT passe au rewriter (diagnosis + baseline) ne contient aucun jeton du golden. Fuite ->
    passe AVORTEE (statut isolation-violation), rien n'est propose. C'est un garde-fou runtime, pas
    un test unitaire sur des litteraux.

    Retouche B (ac-session-2, injection depuis iterer via le bridge d'amelioration_continue) :
      - `fixture_source` : source de fixtures parametrable (defaut = extract_fixtures() EN DUR) ;
      - `rates` : ratES deja mines par iterer -> pas de re-mining ;
      - `diagnosis` : diagnostic deja produit par iterer -> COURT-CIRCUITE agents.diagnose().
    Appelee sans ces params, le comportement est IDENTIQUE (gate 16/16 vert)."""
    original = live_path.read_text(encoding="utf-8")
    if fixture_source is not None:
        cap = fixture_source()
    elif rates is not None:
        cap = {"rates": rates}
    else:
        cap = extractor.extract_fixtures()      # defaut en dur, inchange
    if diagnosis is None:                        # court-circuit si diagnostic injecte
        diagnosis = agents.diagnose(cap["rates"], original)

    if golden_sealed is not None:
        rewriter_ctx = json.dumps(diagnosis, ensure_ascii=False) + "\n" + original
        ok, leaked = isolation.assert_no_golden_leak(rewriter_ctx, golden_sealed)
        if not ok:
            return {"skill": skill, "iterations": 0, "statut": "isolation-violation",
                    "proposals_emitted": 0, "consecutive_reverts": 0,
                    "subagent_calls": agents.calls, "live_unchanged": True, "golden_leak": leaked}

    reg = keep_revert.Registry()
    baseline, best_candidate = original, None
    consecutive_reverts = iterations = 0

    for k in range(1, max_iter + 1):
        iterations = k
        cand = agents.rewrite(diagnosis, baseline)
        candidate_md = cand["candidate"]
        av = patch_validator.validate_append_only(baseline, candidate_md)
        deprec = patch_validator.has_uncontrolled_deprecation(baseline, candidate_md, cand.get("supersedes", []))
        if not av["ok"] or deprec:  # suppression / >1 section / neutralisation hors canal supersedes
            git.revert(f"v{k}")
            reg.add(f"v{k}", "revert", 0.0, 0.0)
            consecutive_reverts += 1
        else:
            verdict = agents.judge(candidate_md, baseline)
            dec = keep_revert.apply_decision(reg, f"v{k}", verdict["capability"], verdict["regression"], git)
            if dec == "keep":
                consecutive_reverts = 0
                baseline, best_candidate = candidate_md, candidate_md
            else:
                consecutive_reverts += 1
        if consecutive_reverts >= MAX_CONSECUTIVE_REVERTS:
            break

    best = reg.best()
    statut, proposals_emitted = ("propose", 1) if best else ("plateau", 0)
    if best:
        propose.write_proposal(
            skill, date,
            quoi="Patch append-only cible (voir proposition.diff).",
            pourquoi=f"{len(cap['rates'])} rates mines.",
            delta_golden=f"capability={best['capability']}, regression={best['regression']}.",
            diff_text=_unified_diff(original, best_candidate),
            candidate_md=best_candidate,
            verdict={"capability_pass_rate": best["capability"], "regression_pass_rate": best["regression"],
                     "decision": "keep", "variante_id": best["variante_id"]},
            base_dir=base_dir,
        )

    return {"skill": skill, "iterations": iterations, "statut": statut,
            "proposals_emitted": proposals_emitted, "consecutive_reverts": consecutive_reverts,
            "subagent_calls": agents.calls, "live_unchanged": live_path.read_text(encoding="utf-8") == original}


class _MockAgents:
    """Doubles deterministes : rewriter fait un append valide ; juge rend les verdicts fournis."""

    def __init__(self, judge_verdicts: list[dict]):
        self.verdicts = judge_verdicts
        self.i = self.calls = 0

    def diagnose(self, rates, skill_md):
        self.calls += 1
        return {"failure_modes": [{"nom": "keyword-spotting"}]}

    def rewrite(self, diagnosis, skill_md):
        self.calls += 1
        return {"candidate": patch_validator._append_section(skill_md), "notes": "rationale", "supersedes": []}

    def judge(self, candidate_md, baseline):
        self.calls += 1
        v = self.verdicts[min(self.i, len(self.verdicts) - 1)]
        self.i += 1
        return v


class _LeakingAgents(_MockAgents):
    """Attaque : le diagnose laisse fuiter un jeton du golden dans le contexte rewriter."""

    def __init__(self):
        super().__init__([{"capability": 0.9, "regression": 1.0}])

    def diagnose(self, rates, skill_md):
        self.calls += 1
        return {"failure_modes": [{"nom": "les reponses violent reponse_len_words du golden"}]}


def golden_harness() -> dict:
    """Assemble les valeurs G7/G9/G10 sur un skill jouet en sandbox temporaire (aucun artefact live)."""
    jouet = patch_validator.JOUET.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        # Passe KEEPABLE (juge : gain + regression 100%) -> proposition ecrite, live inchange.
        base1 = Path(tmp) / "proposals1"
        live1 = Path(tmp) / "SKILL1.md"
        live1.write_text(jouet, encoding="utf-8")
        r_ok = run_pass("skill-jouet", live1, _MockAgents([{"capability": 0.8, "regression": 1.0}]),
                        keep_revert.MockGit(), base1, "test-date", max_iter=1)
        prop_dir = base1 / "skill-jouet" / "test-date"
        diff_exists = (prop_dir / "proposition.diff").exists()
        report = (prop_dir / "report.md").read_text(encoding="utf-8") if (prop_dir / "report.md").exists() else ""

        # Passe REVERT (juge : regression cassee) x3 -> plateau, 0 proposition.
        base2 = Path(tmp) / "proposals2"
        live2 = Path(tmp) / "SKILL2.md"
        live2.write_text(jouet, encoding="utf-8")
        r_bad = run_pass("skill-jouet", live2, _MockAgents([{"capability": 0.9, "regression": 0.5}] * 3),
                         keep_revert.MockGit(), base2, "test-date", max_iter=3)

        # Passe FUITE GOLDEN (patch red-team #1) : un diagnose qui laisse fuiter un jeton du golden
        # dans le contexte rewriter -> run_pass AVORTE (gate isolation runtime, pas un litteral).
        sealed = isolation.load_sealed()  # retouche A : helper target-agnostic (defaut skill-jugement)
        base3 = Path(tmp) / "proposals3"
        live3 = Path(tmp) / "SKILL3.md"
        live3.write_text(jouet, encoding="utf-8")
        r_leak = run_pass(isolation.DEFAULT_TARGET_SKILL, live3, _LeakingAgents(), keep_revert.MockGit(),
                          base3, "test-date", max_iter=1, golden_sealed=sealed)

        return {"live_md_unchanged": r_ok["live_unchanged"], "diff_proposed_exists": diff_exists,
                "report_has_4_blocks": propose.report_has_4_blocs(report),
                "circuit_breaker_plateau": r_bad["statut"] == "plateau", "cb_iterations": r_bad["iterations"],
                "cb_proposals": r_bad["proposals_emitted"],
                "run_pass_blocks_leak": r_leak["statut"] == "isolation-violation",
                "leak_no_write": r_leak["live_unchanged"] and r_leak["proposals_emitted"] == 0}


def _self_test() -> int:
    ok = True
    h = golden_harness()
    print(f"  harness: {h}")
    try:
        assert h["live_md_unchanged"], "G7 : le SKILL.md live ne doit PAS changer pendant une passe"
        assert h["diff_proposed_exists"], "G7 : un proposition.diff doit exister"
        assert h["report_has_4_blocks"], "G10 : report.md 4 blocs"
        assert h["circuit_breaker_plateau"] and h["cb_iterations"] <= 3 and h["cb_proposals"] == 0, "G9 : plateau"
        assert h["run_pass_blocks_leak"] and h["leak_no_write"], "gate isolation runtime : fuite golden doit avorter la passe"
        print("  [OK] G7 (live inchange + diff) / G9 (plateau <=3, 0 prop) / G10 (4 blocs) / isolation runtime (fuite -> avort)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
    sys.exit(0)
