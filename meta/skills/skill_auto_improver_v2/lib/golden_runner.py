#!/usr/bin/env python3
"""golden_runner.py -- fitness mixte (§9 tranchee) + calibration du proxy (G13).

§9 FIGEE : sur un cas TAGGE (tag reel accepte/rejete), le tag ecrase le proxy (poids 1.0). Le
proxy n'est actif QUE sur les cas non tagges, et seulement s'il est CALIBRE.

G13 (calibration) : sur les cas taggues, `agreement = accord(proxy_binaire, tag)`. Si < 0.75, le
proxy est `non-calibre`, son poids tombe a 0 -> la passe se rabat sur les tags reels seuls (et
`signal-insuffisant` si < 2 tags).

G14 (fitness mixte, 3 cas) : (a) tag+proxy discordant -> score suit le tag ; (b) sans tag -> score
= proxy + flag `proxy-only` ; (c) mix -> confiance `mixte`.

CLI :
  python golden_runner.py --self-test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
FITNESS = SKILL_ROOT / "evals" / "fixtures" / "fitness_cases.json"

MIN_TAGS = 2
CALIBRATION_THRESHOLD = 0.75


def score_case(real_tag: str | None, proxy_verdict: float | None) -> tuple[float, str]:
    """Score d'un cas + source. Tag reel (poids 1.0) ecrase le proxy."""
    if real_tag is not None:
        return (1.0 if real_tag == "accepte" else 0.0), "tag"
    return (proxy_verdict if proxy_verdict is not None else 0.0), "proxy"


def calibration(tagged: list[dict]) -> dict:
    """agreement(proxy_binaire, tag) sur les cas taggues -> {agreement, calibrated}."""
    if not tagged:
        return {"agreement": None, "calibrated": False}
    agree = sum(1 for t in tagged if t["proxy_bin"] == t["tag"]) / len(tagged)
    return {"agreement": round(agree, 4), "calibrated": agree >= CALIBRATION_THRESHOLD}


def run_fitness(cases: list[dict], proxy_calibrated: bool = True) -> dict:
    """Score capability mixte. Si proxy non calibre, les cas non taggues sont ignores."""
    scores, sources = [], []
    for c in cases:
        if not proxy_calibrated and c.get("real_tag") is None:
            sources.append("proxy-ignore")
            continue
        s, src = score_case(c.get("real_tag"), c.get("proxy_verdict"))
        scores.append(s)
        sources.append(src)

    n_tags = sum(1 for c in cases if c.get("real_tag") is not None)
    if not proxy_calibrated and n_tags < MIN_TAGS:
        return {"capability": None, "statut": "signal-insuffisant",
                "confiance": "tags-insuffisants", "sources": sources}

    used = [s for s in sources if s in ("tag", "proxy")]
    if used and all(s == "proxy" for s in used):
        confiance = "proxy-only"
    elif used and all(s == "tag" for s in used):
        confiance = "tags-only"
    else:
        confiance = "mixte"
    capability = round(sum(scores) / len(scores), 4) if scores else None
    regression = round(sum(1 for c in cases if c.get("regression_pass", True)) / len(cases), 4)
    return {"capability": capability, "regression_pass_rate": regression,
            "confiance": confiance, "sources": sources, "statut": "ok"}


def _self_test() -> int:
    ok = True
    fx = json.loads(FITNESS.read_text(encoding="utf-8"))

    a = run_fitness(fx["g14a_discordant"])
    try:
        assert a["capability"] == 0.0 and a["sources"] == ["tag"], a
        print("  [OK] G14a : tag+proxy discordant -> score suit le tag (0.0)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] G14a : {e}")

    b = run_fitness(fx["g14b_proxy_only"])
    try:
        assert b["confiance"] == "proxy-only" and b["capability"] == 0.7, b
        print("  [OK] G14b : sans tag -> proxy-only, capability=0.7")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] G14b : {e}")

    c = run_fitness(fx["g14c_mixte"])
    try:
        assert c["confiance"] == "mixte", c
        print("  [OK] G14c : mix tag+proxy -> confiance mixte")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] G14c : {e}")

    cal = calibration(fx["calibration_ok"])
    cal_low = calibration(fx["calibration_low"])
    try:
        assert cal["calibrated"] and cal["agreement"] >= 0.75, cal
        assert not cal_low["calibrated"] and cal_low["agreement"] < 0.75, cal_low
        print(f"  [OK] G13 : agreement {cal['agreement']} calibre / {cal_low['agreement']} non-calibre")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] G13 : {e}")

    # Rabattement : proxy non calibre + < 2 tags -> signal-insuffisant.
    r = run_fitness(fx["g14b_proxy_only"], proxy_calibrated=False)
    try:
        assert r["statut"] == "signal-insuffisant", r
        print("  [OK] proxy non calibre + <2 tags -> signal-insuffisant")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] rabattement : {e}")

    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
    sys.exit(0)
