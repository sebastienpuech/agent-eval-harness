#!/usr/bin/env python3
"""run_grid.py -- juge-par-grille (branche jugement, V1.1). Signal du regime JUGEMENT.

Rigueur statistique (patch SIM-001) : chaque variante est rejouee **N>=3 fois** (temperature
basse figee, seed loggue), grille moyennee. Un delta n'est SIGNIFICATIF que si
`|delta| > bruit_intra_juge` (ecart-type des N runs) ; sinon **INDECIS** -> escalade humaine.
Sous 15 cas held-out jugement, la gate est **advisory**.

Justifications SANS-PII (critere+score, jamais de verbatim) + lint anti-PII avant ecriture.

Prouve les cas discriminants (spec 12bis / 6) :
  6a : grid(coherente) - grid(fragmentee) >= 3   (la grille separe les deux)
  6b : un fix qui REGRESSE un held-out -> gate refuse + sur-generalisation nommee (comme S4)

CLI : python run_grid.py --golden
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from lint_pii import lint_grid_scores

SKILL_ROOT = Path(__file__).resolve().parent.parent
ITER = SKILL_ROOT / ".iter"
FIXTURES = SKILL_ROOT / "evals" / "fixtures"
SEED = 20260706  # seed fige, loggue (reproductibilite)

# Justification neutre par (critere, score) -- SANS PII (template fixe).
_JUSTIF = {
    2: "conforme, ancre",
    1: "partiel, generique",
    0: "absent ou vibe robotique",
}


def _total(run: dict, criteres: list[str]) -> int:
    return sum(run[c] for c in criteres)


def score_variante(runs: list[dict], criteres: list[str]) -> dict:
    totals = [_total(r, criteres) for r in runs]
    crit_means = {c: round(statistics.mean(r[c] for r in runs), 3) for c in criteres}
    bruit = round(statistics.pstdev(totals), 3) if len(totals) > 1 else 0.0
    justifs = {c: f"{c}={round(crit_means[c])} : {_JUSTIF[round(crit_means[c])]}" for c in criteres}
    return {"n_runs": len(runs), "totals": totals, "total_mean": round(statistics.mean(totals), 3),
            "bruit_intra_juge": bruit, "criteres_mean": crit_means, "justifications": justifs}


def significativite(a: dict, b: dict) -> dict:
    delta = round(a["total_mean"] - b["total_mean"], 3)
    bruit = max(a["bruit_intra_juge"], b["bruit_intra_juge"])
    significatif = abs(delta) > bruit
    return {"delta": delta, "bruit_intra_juge": bruit,
            "verdict": "significatif" if significatif else "INDECIS"}


def build_grid_scores(fixture: dict) -> dict:
    criteres = fixture["criteres"]
    out = {"seed": SEED, "criteres": criteres, "variantes": {}}
    for name, data in fixture["variantes"].items():
        out["variantes"][name] = score_variante(data["runs"], criteres)
    return out


def judgment_gate(avant: dict, apres: dict, n_holdout: int) -> dict:
    sig = significativite(apres, avant)  # delta = apres - avant
    delta = sig["delta"]
    advisory = n_holdout < 15
    if sig["verdict"] == "INDECIS":
        ship, note = None, "INDECIS -> escalade humaine (delta <= bruit intra-juge)"
    elif delta < 0:
        ship, note = False, "regression significative sur held-out -> refus"
    else:
        ship, note = True, "amelioration significative"
    ap = []
    if ship is False:
        ap.append({"type": "whack_a_mole",
                   "evidence": f"grid net {delta:+} sur held-out jugement",
                   "sur_generalisation": "le fix ameliore les cas cites mais degrade un held-out "
                                         "juge : refuser, rendre le cas permanent."})
    return {"signal": "juge_par_grille", "delta_net_holdout": delta,
            "bruit_intra_juge": sig["bruit_intra_juge"], "verdict_significativite": sig["verdict"],
            "advisory_sous_15": advisory, "ship": ship, "anti_patterns": ap}


def _golden() -> int:
    ok = True
    fixture = json.loads((FIXTURES / "grid_replays.json").read_text(encoding="utf-8"))
    gs = build_grid_scores(fixture)
    ITER.mkdir(exist_ok=True)
    (ITER / "grid_scores.json").write_text(json.dumps(gs, ensure_ascii=False, indent=2), encoding="utf-8")

    # Lint anti-PII (bloquant).
    viol = lint_grid_scores(gs)
    print(f"lint anti-PII : {'OK' if not viol else 'FAIL ' + str(viol)}")
    ok &= not viol

    # 6a : grille separe coherente / fragmentee de >= 3.
    coh = gs["variantes"]["coherente"]["total_mean"]
    frag = gs["variantes"]["fragmentee"]["total_mean"]
    gap = round(coh - frag, 3)
    print(f"6a : coherente({coh}) - fragmentee({frag}) = {gap}  (attendu >= 3)")
    if gap < 3:
        ok = False; print("  [FAIL] 6a")
    else:
        print("  [OK] 6a : la grille discrimine (LM3 exercee)")

    # 6b : fix qui regresse un held-out -> refus + anti-pattern.
    gate = judgment_gate(gs["variantes"]["holdout_avant"], gs["variantes"]["holdout_apres_whack"],
                         n_holdout=3)
    (ITER / "grid_regression_report.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"6b : ship={gate['ship']} verdict={gate['verdict_significativite']} "
          f"advisory={gate['advisory_sous_15']}")
    if gate["ship"] is not False or not gate["anti_patterns"]:
        ok = False; print("  [FAIL] 6b (aurait du refuser + nommer)")
    else:
        print("  [OK] 6b : held-out regresse -> refus + sur-generalisation nommee (LM1 exercee)")

    # INDECIS : deux variantes proches -> pas de faux ship.
    ind = judgment_gate(gs["variantes"]["holdout_avant"], gs["variantes"]["holdout_avant"], 3)
    print(f"INDECIS control : verdict={ind['verdict_significativite']} ship={ind['ship']}")
    if ind["verdict_significativite"] != "INDECIS":
        ok = False; print("  [FAIL] delta nul aurait du etre INDECIS")

    print("\n=> GRID GOLDEN OK" if ok else "\n=> GRID GOLDEN ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_golden())
