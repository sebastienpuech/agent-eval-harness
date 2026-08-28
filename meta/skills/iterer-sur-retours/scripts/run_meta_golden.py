#!/usr/bin/env python3
"""run_meta_golden.py -- suite du META-golden-set (signal de succes du skill lui-meme).

Deux suites (spec 10bis) :
  - CAPABILITY : le skill produit-il les artefacts attendus ? (assertions binaires vs expected.json)
  - REGRESSION : une regression PLANTEE (whack-a-mole) est-elle bien attrapee ? (>=1)

A 2 cas (tableur, jugement) c'est de la NON-REGRESSION BINAIRE, pas une mesure de generalisation
(seuil n>=5). Sortie facon fitness auto-improver v2 : {capability_pass_rate, regression_pass_rate}.

CLI : python run_meta_golden.py     (exit 0 si capability==1.0 ET regression==1.0)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows cp1252 -> UTF-8
except Exception:  # noqa: BLE001
    pass

import run_pipeline

SKILL_ROOT = Path(__file__).resolve().parent.parent
ITER = SKILL_ROOT / ".iter"
EVALS = SKILL_ROOT / "evals"


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def capability_checks(expected_tableur: dict) -> list[tuple]:
    res = []

    def chk(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    classif = _load(ITER / "classification.json")
    chk("fork_factuel",
        classif["regime"] == expected_tableur["regime_attendu"]
        and classif["part_oracle_mecanique"] >= expected_tableur["part_oracle_min"],
        f"regime={classif['regime']} part={classif['part_oracle_mecanique']}")

    items = classif["items"]
    fams_ok = all(it["famille"] in {"A", "B", "C", "D"} for it in items)
    complete = len(items) == classif["n_retours_normalises"]
    chk("classification_complete", fams_ok and complete,
        f"n_items={len(items)}=={classif['n_retours_normalises']}, familles_in_ABCD={fams_ok}")

    # types_attendus : A>=5, B>=1, C>=1
    fam_counts = {}
    for it in items:
        fam_counts[it["famille"]] = fam_counts.get(it["famille"], 0) + 1
    ta = expected_tableur["types_attendus"]
    types_ok = all(fam_counts.get(k, 0) >= int(v.lstrip(">=")) for k, v in ta.items())
    chk("types_attendus", types_ok, f"{fam_counts} vs {ta}")

    registry = _read_yaml(SKILL_ROOT / "signal" / "registry.yaml")
    holdout = set(registry.get("holdout", []))
    exclure = set(expected_tableur["holdout_doit_exclure"])
    chk("holdout_exclut_retours", not (holdout & exclure),
        f"inter(holdout={sorted(holdout)}, exclure={sorted(exclure)}) == vide")
    chk("holdout_3_porteurs", len(holdout) == 3, f"{sorted(holdout)}")

    detlog = _load(ITER / "detector_log.json")
    etats = {e["etat"] for e in detlog["entries"]}
    chk("anti_silence_emis", "non_detecte" in etats and "detecte" in etats, f"etats={etats}")

    contract = _load(ITER / "auto_improver_call.json")
    zero_patch = (ITER / "auto_improver_call.json").exists() \
        and not (set(contract["test_case_ids"]) & holdout)
    chk("g2_contrat_0_patch_code",
        zero_patch and contract.get("skill_path") is not None,
        f"held-out exclu des test_cases, statut={contract.get('delegation_status')}")

    return res


def regression_checks() -> list[tuple]:
    res = []
    # Planted 1 : whack-a-mole -> DOIT etre refuse + nomme.
    run_pipeline.run(clean=False)
    rep = _load(ITER / "regression_report.json")
    caught = (rep["ship"] is False) and any(a["type"] == "whack_a_mole" for a in rep["anti_patterns"]) \
        and bool(rep["cas_regresses_error_analysis"])
    res.append(("whack_a_mole_attrape", caught,
                f"ship={rep['ship']} regresses={rep['cas_regresses_error_analysis']}"))
    # Planted 2 (controle) : clean -> DOIT ship (sinon la gate est cassee dans l'autre sens).
    run_pipeline.run(clean=True)
    rep2 = _load(ITER / "regression_report.json")
    res.append(("clean_ship", rep2["ship"] is True, f"ship={rep2['ship']}"))
    return res


def judgment_checks(expected_jugement: dict) -> list[tuple]:
    """Suite JUGEMENT (V1.1 / DoD §12 point 5). Machinerie prouvee sur fixtures ;
    calibration reelle NON_ANCREE tant que l'utilisateur n'a pas note >=8 cas jugement."""
    import correlate_taste
    import fork as fork_mod
    import run_grid
    res = []

    def chk(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    jugement = fork_mod.compute_fork(_load(EVALS / "fixtures" / "jugement_classified.json"))
    chk("fork_jugement", jugement["regime"] == expected_jugement["regime_attendu"],
        f"regime={jugement['regime']}")

    fx = _load(EVALS / "fixtures" / "grid_replays.json")
    gs = run_grid.build_grid_scores(fx)
    gap = round(gs["variantes"]["coherente"]["total_mean"]
                - gs["variantes"]["fragmentee"]["total_mean"], 3)
    chk("grid_6a_discrimine", gap >= 3, f"coherente-fragmentee={gap} (>=3)")

    gate = run_grid.judgment_gate(gs["variantes"]["holdout_avant"],
                                  gs["variantes"]["holdout_apres_whack"], n_holdout=3)
    chk("grid_6b_refuse_holdout",
        gate["ship"] is False and bool(gate["anti_patterns"]),
        f"ship={gate['ship']}")

    from lint_pii import lint_grid_scores
    chk("lint_anti_pii", not lint_grid_scores(gs), "justif sans verbatim")

    notes = _load(EVALS / "fixtures" / "taste_notes.json")
    cal_ok = correlate_taste.calibrate(notes["aligned"])["grid_calibrated"]
    cal_none = correlate_taste.calibrate([])
    chk("correlation_mesuree", cal_ok and not cal_none["grid_calibrated"]
        and cal_none["statut"] == "NON_ANCRE",
        "aligned calibre ; sans notes -> NON_ANCRE (cas jugement reel en attente)")

    chk("reduction_et_exemples_documentes",
        (SKILL_ROOT / "references" / "signal-jugement.md").exists()
        and (SKILL_ROOT / "agents" / "juge-par-grille.md").exists(),
        "principe+exemples contrastes + reduction de regles")
    return res


def posture_checks() -> list[tuple]:
    """Suite POSTURE (voie cold-review). 0-LLM via _FakeClient. Prouve PA/PB/PC."""
    import surface_judge, posture_gate
    fx = _load(EVALS / "fixtures" / "posture_replays.json")
    fc = surface_judge._FakeClient()
    res = []

    def chk(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    warr = surface_judge.grade_all_situations(fc, fx["warrante"], n=3)["variantes"]
    temo = surface_judge.grade_all_situations(fc, fx["temoin"], n=3)["variantes"]
    gap = round(warr["patched"]["total_mean"] - warr["baseline"]["total_mean"], 3)
    chk("posture_PA_discrimine", gap >= 3, f"patched-baseline={gap} (>=3)")

    g_ok = posture_gate.posture_gate(warr["baseline"], warr["patched"],
                                     temo["baseline"], temo["patched"], n_holdout=3)
    chk("posture_PB_bien_dose_ship", g_ok["ship"] is True, f"ship={g_ok['ship']}")

    g_bad = posture_gate.posture_gate(warr["baseline"], warr["overwiden"],
                                      temo["baseline"], temo["overwiden"], n_holdout=3)
    chk("posture_PC_overwiden_refuse",
        g_bad["ship"] is False and any(a["type"] == "sur_elargissement" for a in g_bad["anti_patterns"]),
        f"ship={g_bad['ship']}")
    return res


def fork_aware_checks() -> list[tuple]:
    """Suite FORK-AWARE (2e lentille cold-review). 0-LLM via _FakeClient. FA1/FA2/FA3."""
    import revue_fork_aware
    fx = _load(EVALS / "fixtures" / "fork_aware_replays.json")
    fc = revue_fork_aware._FakeClient()
    res = []

    def chk(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    r = revue_fork_aware.reviser_fork_aware(fc, "jugement", fx["skill_md"])
    chk("fork_FA1_fire_jugement",
        r["fire"] is True and r["candidat"]["type"] == "regle_a_exemple", f"fire={r['fire']}")
    chk("fork_FA2_pas_assert_determin",
        r["candidat"] is not None and r["candidat"]["regle_citee"] != "§2",
        f"regle={r['candidat'] and r['candidat']['regle_citee']}")
    r2 = revue_fork_aware.reviser_fork_aware(fc, "factuel", fx["skill_md"])
    chk("fork_FA3_inactif_factuel", r2["fire"] is False and r2["candidat"] is None, f"fire={r2['fire']}")
    return res


def _read_yaml(p: Path):
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def main() -> int:
    # Produire les artefacts (whack-a-mole pour exercer le refus).
    run_pipeline.run(clean=False)
    expected = _load(EVALS / "expected.json")["tableur"]

    cap = capability_checks(expected)
    jug = judgment_checks(_load(EVALS / "expected.json")["jugement"])
    pos = posture_checks()
    fka = fork_aware_checks()
    reg = regression_checks()

    print("=== CAPABILITY (cas tableur, regime factuel) ===")
    for name, ok, detail in cap:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<28} {detail}")
    print("=== CAPABILITY (cas jugement, regime jugement V1.1) ===")
    for name, ok, detail in jug:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<28} {detail}")
    print("=== CAPABILITY (posture, cold-review) ===")
    for name, ok, detail in pos:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<28} {detail}")
    print("=== CAPABILITY (fork-aware, cold-review) ===")
    for name, ok, detail in fka:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<28} {detail}")
    print("=== REGRESSION (plantee) ===")
    for name, ok, detail in reg:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<28} {detail}")

    allcap = cap + jug + pos + fka
    cap_rate = sum(1 for _, ok, _ in allcap if ok) / len(allcap)
    reg_rate = sum(1 for _, ok, _ in reg if ok) / len(reg)
    print("-" * 60)
    print(f"capability_pass_rate = {cap_rate:.2f}  regression_pass_rate = {reg_rate:.2f}")
    ok = cap_rate == 1.0 and reg_rate == 1.0
    print("=> META-GOLDEN OK" if ok else "=> META-GOLDEN ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
