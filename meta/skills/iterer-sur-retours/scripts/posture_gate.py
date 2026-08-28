#!/usr/bin/env python3
"""posture_gate.py -- gate de la voie posture. Ship ⟺ gain significatif sur les situations
warrantées ∧ pas de régression sur le témoin (should-not-fire : le fix ne doit pas sur-élargir
là où rester focalisé était juste). Réutilise run_grid.significativite.
"""
from __future__ import annotations
import run_grid


def posture_gate(warr_baseline, warr_patched, temoin_baseline, temoin_patched, n_holdout) -> dict:
    gain = run_grid.significativite(warr_patched, warr_baseline)          # patched - baseline (warranté)
    reg = run_grid.significativite(temoin_patched, temoin_baseline)        # patched - baseline (témoin)
    gain_ok = gain["verdict"] == "significatif" and gain["delta"] > 0
    temoin_regresse = reg["verdict"] == "significatif" and reg["delta"] < 0
    ap = []
    if temoin_regresse:
        ap.append({"type": "sur_elargissement",
                   "evidence": f"témoin régresse de {reg['delta']:+} (surface hors-sol)",
                   "sur_generalisation": "le fix élargit là où rester focalisé était juste -> refuser."})
        ship = False
    elif not gain_ok:
        ship = None if gain["verdict"] == "INDECIS" else False
    else:
        ship = True
    return {"signal": "juge_surface", "gain_warrante": gain["delta"],
            "regression_temoin": reg["delta"], "advisory_sous_15": n_holdout < 15,
            "ship": ship, "anti_patterns": ap}


def _self_test() -> int:
    hi = {"total_mean": 5.0, "bruit_intra_juge": 0.2}
    lo = {"total_mean": 1.0, "bruit_intra_juge": 0.2}
    ok = True
    # (a) fix bien dosé : gain warranté + témoin stable -> ship.
    g = posture_gate(warr_baseline=lo, warr_patched=hi, temoin_baseline=hi, temoin_patched=hi, n_holdout=3)
    ok &= (g["ship"] is True)
    print(f"  bien dosé : ship={g['ship']} (attendu True)")
    # (b) sur-élargissement : gain warranté MAIS témoin régresse -> refus + anti-pattern nommé.
    g2 = posture_gate(warr_baseline=lo, warr_patched=hi, temoin_baseline=hi, temoin_patched=lo, n_holdout=3)
    ok &= (g2["ship"] is False and any(a["type"] == "sur_elargissement" for a in g2["anti_patterns"]))
    print(f"  sur-élargissement : ship={g2['ship']} anti={[a['type'] for a in g2['anti_patterns']]} (attendu False + sur_elargissement)")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv):
    if "--self-test" in argv:
        return _self_test()
    print(__doc__); return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
