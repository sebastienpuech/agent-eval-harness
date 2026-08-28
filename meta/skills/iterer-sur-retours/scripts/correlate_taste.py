#!/usr/bin/env python3
"""correlate_taste.py -- ancrage du juge : Spearman juge<->gout (patch SIM-005 / spec 10ter).

NON bloquant pour le RUN, BLOQUANT pour la CALIBRATION de la grille : un delta de grille ne
justifie un ship que si rho(juge, gout) >= 0.6 sur >= 8 cas held-out reels. Sinon signal
jugement **NON_ANCRE** (delta indicatif, gate exige validation humaine).

Spearman implemente a la main (rangs moyens + Pearson) -- pas de dependance scipy.

CLI : python correlate_taste.py --golden        # aligned (>=0.6) vs misaligned (<0.6)
      python correlate_taste.py <pairs.json>    # {pairs:[{grid_total,taste}]}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
ITER = SKILL_ROOT / ".iter"
FIXTURES = SKILL_ROOT / "evals" / "fixtures"
SEUIL = 0.6
N_MIN = 8


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # rang moyen (1-based) pour les ex-aequo
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((x - mb) ** 2 for x in b) ** 0.5
    if va == 0 or vb == 0:
        return 0.0
    return cov / (va * vb)


def spearman(pairs: list[dict]) -> float:
    g = [p["grid_total"] for p in pairs]
    t = [p["taste"] for p in pairs]
    return round(_pearson(_rank(g), _rank(t)), 3)


def calibrate(pairs: list[dict]) -> dict:
    n = len(pairs)
    if n < N_MIN:
        return {"n_cas": n, "rho_spearman": None, "seuil": SEUIL,
                "grid_calibrated": False, "statut": "NON_ANCRE",
                "raison": f"n={n} < {N_MIN} cas notes -> calibration impossible (advisory)."}
    rho = spearman(pairs)
    calibrated = rho >= SEUIL
    return {"n_cas": n, "rho_spearman": rho, "seuil": SEUIL,
            "grid_calibrated": calibrated,
            "statut": "ANCRE" if calibrated else "NON_ANCRE",
            "raison": ("rho >= seuil -> grille ancree, delta calibrable"
                       if calibrated else
                       "rho < seuil -> signal jugement NON_ANCRE, gate exige validation humaine")}


def _golden() -> int:
    ok = True
    notes = json.loads((FIXTURES / "taste_notes.json").read_text(encoding="utf-8"))
    aligned = calibrate(notes["aligned"])
    mis = calibrate(notes["misaligned"])
    print(f"aligned    : rho={aligned['rho_spearman']} grid_calibrated={aligned['grid_calibrated']} "
          f"({aligned['statut']})")
    print(f"misaligned : rho={mis['rho_spearman']} grid_calibrated={mis['grid_calibrated']} "
          f"({mis['statut']})")
    ITER.mkdir(exist_ok=True)
    (ITER / "calibration.json").write_text(json.dumps(aligned, ensure_ascii=False, indent=2), encoding="utf-8")

    if not (aligned["grid_calibrated"] and aligned["rho_spearman"] >= 0.6):
        ok = False; print("  [FAIL] aligned aurait du calibrer (rho>=0.6)")
    else:
        print("  [OK] aligned : rho>=0.6 -> grid_calibrated")
    if mis["grid_calibrated"]:
        ok = False; print("  [FAIL] misaligned n'aurait PAS du calibrer")
    else:
        print("  [OK] misaligned : rho<0.6 -> NON_ANCRE")

    # Real-notes guard : sans notes (n<8) -> NON_ANCRE.
    empty = calibrate([])
    print(f"sans notes : statut={empty['statut']} grid_calibrated={empty['grid_calibrated']}")
    if empty["grid_calibrated"] or empty["statut"] != "NON_ANCRE":
        ok = False; print("  [FAIL] absence de notes aurait du etre NON_ANCRE")
    else:
        print("  [OK] sans notes reelles -> NON_ANCRE (cas jugement reel : en attente des notes de l'utilisateur)")

    print("\n=> CORRELATE GOLDEN OK" if ok else "\n=> CORRELATE GOLDEN ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--golden" in sys.argv:
        sys.exit(_golden())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__); sys.exit(0)
    data = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    print(json.dumps(calibrate(data["pairs"]), ensure_ascii=False, indent=2))
