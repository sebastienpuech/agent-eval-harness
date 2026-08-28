#!/usr/bin/env python3
"""regression_gate.py -- E1/E2/E3 : delta net held-out + gate + anti-patterns.

Regle : on ne livre PAS un changement qui regresse le net held-out. On ne fait pas confiance
au delta sans LIRE les traces des cas regresses (error-analysis, archi 8).

Entree : fixture {signal, holdout: {case_id: {avant, apres}}}.
  delta_net = moyenne(apres - avant) sur le held-out
  regression_suite = fraction des cas ou apres >= avant
  ship = (delta_net >= 0) ET (regression_suite == 1.0)
  sinon -> refus + anti-pattern whack_a_mole nomme + cas regresses (error-analysis) conserves.

Cote JUGEMENT (V1.1) : delta significatif seulement si |delta| > bruit_intra_juge, sinon
INDECIS -> escalade humaine (non couvert par cette fixture factuelle).

CLI :
  python regression_gate.py <fixture.json>
  python regression_gate.py --golden      # clean -> ship ; whack-a-mole -> refus
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = SKILL_ROOT / "evals" / "fixtures"
ITER = SKILL_ROOT / ".iter"


def evaluate(fixture: dict) -> dict:
    holdout = fixture.get("holdout", {})
    if not holdout:
        raise SystemExit("held-out vide -> rien a mesurer (corpus non monte ?).")
    deltas = {cid: round(v["apres"] - v["avant"], 4) for cid, v in holdout.items()}
    delta_net = round(sum(deltas.values()) / len(deltas), 4)
    regressed = sorted([cid for cid, d in deltas.items() if d < 0])
    regression_suite = round(sum(1 for d in deltas.values() if d >= 0) / len(deltas), 4)
    ship = (delta_net >= 0) and (regression_suite == 1.0)

    anti_patterns = []
    if not ship and regressed:
        anti_patterns.append({
            "type": "whack_a_mole",
            "evidence": f"net {delta_net:+} sur held-out ; cas regresses : {regressed}",
            "sur_generalisation": (
                f"le fix generalise a tort : il regresse {regressed} (held-out sanctuarise). "
                "Refuser + rendre ces cas permanents (chaque echec -> un test de plus)."
            ),
        })

    return {
        "signal": fixture.get("signal", "matrice_deterministe"),
        "delta_net_holdout": delta_net,
        "deltas_par_cas": deltas,
        "regression_suite": regression_suite,
        "ship": ship,
        "cas_regresses_error_analysis": regressed,
        "anti_patterns": anti_patterns,
    }


def _print(report: dict) -> None:
    print(f"  signal={report['signal']}  delta_net={report['delta_net_holdout']:+}  "
          f"reg_suite={report['regression_suite']}  ship={report['ship']}")
    if report["anti_patterns"]:
        for ap in report["anti_patterns"]:
            print(f"  [ANTI-PATTERN] {ap['type']} : {ap['evidence']}")
            print(f"                 sur-generalisation : {ap['sur_generalisation']}")
    if report["cas_regresses_error_analysis"]:
        print(f"  [ERROR-ANALYSIS] lire les traces de : {report['cas_regresses_error_analysis']}")


def _golden() -> int:
    ok = True
    print("=== CLEAN (attendu ship=true) ===")
    clean = evaluate(json.loads((FIXTURES / "regression_clean.json").read_text(encoding="utf-8")))
    _print(clean)
    if clean["ship"] is not True:
        ok = False; print("  [FAIL] clean aurait du ship")

    print("\n=== WHACK-A-MOLE (attendu ship=false + anti-pattern) ===")
    whack = evaluate(json.loads((FIXTURES / "regression_whack_a_mole.json").read_text(encoding="utf-8")))
    _print(whack)
    if whack["ship"] is not False:
        ok = False; print("  [FAIL] whack aurait du etre refuse")
    if not any(a["type"] == "whack_a_mole" for a in whack["anti_patterns"]):
        ok = False; print("  [FAIL] anti-pattern whack_a_mole non nomme")
    if "C67" not in whack["cas_regresses_error_analysis"]:
        ok = False; print("  [FAIL] cas regresse non conserve pour error-analysis")

    print("\n=> GOLDEN OK" if ok else "\n=> GOLDEN ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--golden" in sys.argv:
        sys.exit(_golden())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__); sys.exit(0)
    rep = evaluate(json.loads(Path(args[0]).read_text(encoding="utf-8")))
    ITER.mkdir(exist_ok=True)
    (ITER / "regression_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    _print(rep)
    sys.exit(0 if rep["ship"] else 3)
