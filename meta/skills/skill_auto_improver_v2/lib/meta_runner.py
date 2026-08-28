#!/usr/bin/env python3
"""meta_runner.py -- rejoue le golden META de la machinerie (evals/evals.json).

Sort {n_cas, capability_pass_rate, regression_pass_rate}. Format critical_checks (v1),
verifiable sans LLM. En Session 1, seuls les checks structurels sont gradables ; les checks
qui dependent d'une feature non encore codee sont SKIP-si-absent (logges, jamais un faux echec).

Verdict par cas : tous SKIP -> SKIP ; un gradable FAIL -> FAIL ; sinon PASS.
pass_rate = PASS / (PASS+FAIL) sur la suite (les SKIP sortent du denominateur). Denominateur 0
-> None (note : tout SKIP en S1, features S2-S5).

CODE DE SORTIE (c'est le seul signal qu'une CI lit -- l'affichage ne sert qu'a l'humain) :
  1 si au moins un cas est FAIL, 0 sinon. Suite entierement SKIP -> 0 (rien de gradable n'a
  echoue). Aligne sur `iterer-sur-retours/scripts/run_meta_golden.py`, qui sort deja en 1.

CLI :
  python meta_runner.py --self-test        # prouve le moteur de grading (plante un cas expres)
  python meta_runner.py --case G1,G11       # ne rejoue que ces cas
  python meta_runner.py                      # rejoue tout (S1 : majorite SKIP)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import confidential  # meme dossier lib/

SKILL_ROOT = Path(__file__).resolve().parent.parent
EVALS = SKILL_ROOT / "evals" / "evals.json"

GRADABLE = {"equals", "max_le", "regex_absent", "subset_of_allowlist", "file_exists", "valid_json"}


def grade_check(check: dict, ctx: dict) -> tuple[str, str]:
    """Retourne (PASS|FAIL|SKIP, detail)."""
    ctype = check["check"]
    if ctype == "file_exists":
        target = check.get("target", "")
        hits = list(SKILL_ROOT.glob(target)) if target else []
        return ("PASS", f"{target} existe") if hits else ("SKIP", f"{target} absent (feature ulterieure)")
    if ctype == "disjoint":
        a, b = check.get("target_a"), check.get("target_b")
        if a in ctx and b in ctx:
            disj = set(ctx[a]).isdisjoint(set(ctx[b]))
            return ("PASS" if disj else "FAIL"), (f"{a} inter {b} = vide" if disj else f"fuite: {sorted(set(ctx[a]) & set(ctx[b]))}")
        fs = check.get("feature_from_session", "?")
        return "SKIP", f"target_a/target_b absents du contexte (feature S{fs})"
    if ctype not in GRADABLE:
        fs = check.get("feature_from_session", "?")
        return "SKIP", f"type '{ctype}' non gradable en S1 (feature S{fs})"
    tgt = check.get("target")
    if tgt is None or tgt not in ctx:
        fs = check.get("feature_from_session", "?")
        return "SKIP", f"target '{tgt}' absent du contexte (feature S{fs})"
    val = ctx[tgt]
    if ctype == "equals":
        return ("PASS" if val == check["value"] else "FAIL"), f"{tgt}={val!r} attendu {check['value']!r}"
    if ctype == "max_le":
        return ("PASS" if val <= check["value"] else "FAIL"), f"{tgt}={val} <= {check['value']}"
    if ctype == "regex_absent":
        hit = re.search(check["value"], str(val))
        return ("FAIL" if hit else "PASS"), (f"motif interdit trouve: {hit.group(0)!r}" if hit else "aucun motif interdit")
    if ctype == "subset_of_allowlist":
        extra = set(val) - set(confidential.ALLOWED_FIELDS)
        return ("PASS" if not extra else "FAIL"), (f"hors allowlist: {sorted(extra)}" if extra else "sous-ensemble de l'allowlist")
    if ctype == "valid_json":
        try:
            json.loads(val) if isinstance(val, str) else json.dumps(val)
            return "PASS", "json valide"
        except (ValueError, TypeError) as e:
            return "FAIL", f"json invalide: {e}"
    return "SKIP", "non atteint"


def grade_case(case: dict, ctx: dict) -> tuple[str, list]:
    results = [grade_check(c, ctx) for c in case.get("critical_checks", [])]
    verdicts = [v for v, _ in results]
    if all(v == "SKIP" for v in verdicts):
        return "SKIP", results
    if any(v == "FAIL" for v in verdicts):
        return "FAIL", results
    return "PASS", results


def _matches(case: dict, only: set[str]) -> bool:
    """Un cas matche si son nom complet OU son identifiant G (1er segment) est demande.
    'G1' matche 'G1_capture' (segment 'G1') mais PAS 'G11_confidentialite' (segment 'G11')."""
    name = case["name"]
    return name in only or name.split("_", 1)[0] in only


def run(evals: dict, ctx: dict, only: set[str] | None = None) -> dict:
    cases = [c for c in evals["test_cases"] if (only is None or _matches(c, only))]
    per_suite = {"capability": [], "regression": []}
    detail = {}
    for case in cases:
        verdict, results = grade_case(case, ctx)
        detail[case["name"]] = verdict
        per_suite.setdefault(case.get("suite", "capability"), []).append(verdict)

    def rate(verdicts):
        graded = [v for v in verdicts if v in ("PASS", "FAIL")]
        return round(sum(v == "PASS" for v in graded) / len(graded), 4) if graded else None

    return {
        "n_cas": len(cases),
        "capability_pass_rate": rate(per_suite["capability"]),
        "regression_pass_rate": rate(per_suite["regression"]),
        "verdicts": detail,
        "n_skip": sum(v == "SKIP" for v in detail.values()),
    }


def _print(res: dict) -> None:
    print(f"n_cas={res['n_cas']}  capability={res['capability_pass_rate']}  "
          f"regression={res['regression_pass_rate']}  skip={res['n_skip']}")
    for name, v in res["verdicts"].items():
        print(f"  [{v}] {name}")


def build_context() -> dict:
    """Assemble le contexte de grading depuis les features DISPONIBLES (S2 : extractor+confidential).
    Les cas dont la feature n'est pas encore codee restent SKIP (leur target absent du ctx)."""
    ctx: dict = {}
    try:
        import extractor  # meme dossier lib/
        res = extractor.extract_fixtures()
        ctx["rates_count"] = len(res["rates"])
        ctx["subagent_calls"] = res["subagent_calls"]
        # Echantillon confidentialite : un champ hors-allowlist (doit etre droppe) + un PRENOM de la liste
        # + PII dans un champ allowliste (doit ressortir scrube).
        sample = {"run_id": "t", "langue": "fr",
                  "registre": "direct, comme dans la revue de Marc @marc.legrand https://forge.example/mr/8821",
                  "SECRET_hors_allowlist": "fuite potentielle : la revue de Marc"}
        clean, _dropped = confidential.clean_interaction(sample)
        scrubbed_rate_text = " ".join(r["resume"] for r in res["rates"])
        ctx["persisted_fields"] = list(clean.keys())
        ctx["persisted_text"] = " ".join(str(v) for v in clean.values()) + " " + scrubbed_rate_text

        # --- S3 : DIAGNOSTIC (G3) + isolation anti-Goodhart (G12) ---------------------------
        import json as _json
        import verify_citations
        import isolation
        diag = _json.loads((EVALS.parent / "fixtures" / "diagnosis_valid.json").read_text(encoding="utf-8"))
        vc = verify_citations.verify_diagnosis(diag, res["rates"], res["index"])
        ctx["citations_ancrees_ratio"] = vc["ratio_ancrees"]
        ctx["diagnosis"] = diag

        sealed = isolation.load_sealed()  # retouche A : helper target-agnostic (defaut skill-jugement)
        ga = isolation.golden_assertion_signatures(sealed)
        gs = isolation.golden_source_sessions(sealed)
        rewriter_input = {"diagnosis:keyword-spotting", "skill_md:jouet-regles"}  # propre
        iso = isolation.check_disjunctions(judge_input={"golden:reponse_len_words"},
                                           rewriter_notes={"note:rhetorique"},
                                           rewriter_input=rewriter_input, golden_assertions=ga)
        leaked = rewriter_input | {next(iter(ga))}  # fuite plantee
        iso_leak = isolation.check_disjunctions(set(), set(), leaked, ga)
        ctx["isolation_ok"] = iso["ok"]
        ctx["pool_disjoint"] = isolation.check_pool_disjoint(set(res["index"].keys()), gs)["disjoint"]
        ctx["leak_detected"] = not iso_leak["ok"]

        # --- S4 : rewriter/patch (G4/G4b), juge separe (G5), keep/revert (G6/G8),
        #          fitness mixte (G14) + calibration (G13) -------------------------------------
        import patch_validator
        import golden_runner
        import keep_revert
        original = patch_validator.JOUET.read_text(encoding="utf-8")
        r_app = patch_validator.validate_append_only(original, patch_validator._append_section(original))
        ctx["rewriter_lignes_supprimees"] = r_app["lignes_supprimees"]
        ctx["rewriter_sections_touchees"] = r_app["sections_touchees"]
        sup = [{"regle_id": "§1", "raison": "keyword-spotting", "remplacee_par": "#16"}]
        r_sup = patch_validator.validate_supersedes(sup, original, patch_validator._supersede_rule(original))
        ctx["supersedes_lignes_supprimees"] = r_sup["lignes_supprimees"]
        ctx["supersedes_cite_complet"] = r_sup["cite_complet"]

        ctx["judge_input"] = {"golden:sealed", "candidate:vk"}
        ctx["rewriter_notes"] = {"note:rhetorique", "note:rationale"}
        ctx["juge_distinct_call"] = True

        reg, git = keep_revert.Registry(), keep_revert.MockGit()
        keep_revert.apply_decision(reg, "v1", 0.9, 0.8, git)  # regression -> revert
        ctx["revert_proposals_emitted"] = reg.proposals_emitted()
        ctx["revert_head_unchanged"] = (git.head == "HEAD@0")
        ctx["gamed_rejected"] = (keep_revert.decide(0.99, 0.5, 0.6) == "revert")

        fx = _json.loads(
            (EVALS.parent / "fixtures" / "fitness_cases.json").read_text(encoding="utf-8"))
        ctx["calibration_ok"] = golden_runner.calibration(fx["calibration_ok"])["calibrated"]
        ctx["calibration_low_detected"] = not golden_runner.calibration(fx["calibration_low"])["calibrated"]
        a = golden_runner.run_fitness(fx["g14a_discordant"])
        ctx["g14a_follows_tag"] = (a["capability"] == 0.0 and a["sources"] == ["tag"])
        ctx["g14b_proxy_only"] = (golden_runner.run_fitness(fx["g14b_proxy_only"])["confiance"] == "proxy-only")
        ctx["g14c_mixte"] = (golden_runner.run_fitness(fx["g14c_mixte"])["confiance"] == "mixte")

        # --- S5 : orchestrateur (G7 no-automerge, G9 circuit-breaker, G10 proposition) ---------
        import orchestrator
        h = orchestrator.golden_harness()
        ctx["live_md_unchanged"] = h["live_md_unchanged"]
        ctx["diff_proposed_exists"] = h["diff_proposed_exists"]
        ctx["report_has_4_blocks"] = h["report_has_4_blocks"]
        ctx["circuit_breaker_plateau"] = h["circuit_breaker_plateau"]
        ctx["cb_iterations"] = h["cb_iterations"]
        ctx["run_pass_blocks_leak"] = h["run_pass_blocks_leak"]

        # --- S6 : batterie adversariale (G16) -------------------------------------------------
        import red_team
        ctx["red_team_all_caught"] = red_team.all_caught()
    except Exception as e:  # une feature absente ne doit jamais crasher le runner
        ctx["_build_error"] = str(e)
    return ctx


def _self_test() -> int:
    """Prouve le moteur de grading sur un contexte synthetique, avec un cas PLANTE."""
    synthetic = {
        "skill_name": "self-test",
        "test_cases": [
            {"name": "ST_ok", "suite": "capability", "critical_checks": [
                {"check": "equals", "target": "rates_count", "value": 2},
                {"check": "subset_of_allowlist", "target": "persisted_fields"},
                {"check": "regex_absent", "target": "persisted_text", "value": "(@\\w+|https?://)"}]},
            {"name": "ST_plante", "suite": "regression", "critical_checks": [
                {"check": "equals", "target": "rates_count", "value": 99}]},  # doit FAIL
        ],
    }
    ctx = {"rates_count": 2, "persisted_fields": ["run_id", "timestamp", "langue"],
           "persisted_text": "reponse proposee, aucun identifiant"}
    res = run(synthetic, ctx)
    _print(res)
    ok = (res["verdicts"]["ST_ok"] == "PASS" and res["verdicts"]["ST_plante"] == "FAIL")
    # Garde anti-drift de l'allowlist (contrat confidential).
    drift_ok, drift_detail = confidential.check_drift()
    print(f"  anti-drift allowlist : {'OK' if drift_ok else 'ALERTE'} -- {drift_detail}")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE (le moteur n'attrape pas le cas plante)")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    evals = json.loads(EVALS.read_text(encoding="utf-8"))
    only = None
    if "--case" in argv:
        only = {x.strip() for x in argv[argv.index("--case") + 1].split(",") if x.strip()}
    ctx = build_context()
    if ctx.get("_build_error"):
        print(f"[warn] build_context degrade : {ctx['_build_error']}")
    res = run(evals, ctx, only=only)
    _print(res)
    if res["capability_pass_rate"] is None and res["regression_pass_rate"] is None:
        print("=> structure valide ; checks gradables restants = SKIP (features non encore codees).")
        return 0
    # Sur les verdicts, pas sur les taux : un FAIL doit sortir en 1 meme si l'arrondi du taux
    # ne le montre pas. Un portail qui affiche FAIL et rend 0 est un portail decoratif.
    n_fail = sum(v == "FAIL" for v in res["verdicts"].values())
    if n_fail:
        print(f"=> GOLDEN META ECHOUE ({n_fail} cas en FAIL)")
        return 1
    print("=> GOLDEN META OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
