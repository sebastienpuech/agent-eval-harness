#!/usr/bin/env python3
"""lint_pii.py -- garde-fou confidentialite sur grid_scores.json (impératif jugement).

Une justification de grille = **critere + score + raison courte**, JAMAIS une citation de
conversation. Ex. OK : `ancrage_concret=1 : metaphore generique, pas d'ancrage`.
Interdit : guillemets/citations, verbatim long, retours a la ligne.

Fonctions importables + CLI :
  python lint_pii.py .iter/grid_scores.json    # exit 0 si propre, 1 sinon
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

QUOTE_CHARS = set('"«»“”‘’`')  # " « » " " ' ' `
MAX_REASON = 120
JUSTIF_RE = re.compile(r"^(?P<crit>[a-z_]+)=(?P<score>[0-2]) : (?P<reason>.+)$")


def lint_justification(justif: str) -> tuple[bool, str]:
    if "\n" in justif:
        return False, "retour a la ligne (verbatim probable)"
    m = JUSTIF_RE.match(justif)
    if not m:
        return False, "format attendu '<critere>=<0-2> : <raison>'"
    reason = m.group("reason")
    if len(reason) > MAX_REASON:
        return False, f"raison trop longue ({len(reason)}>{MAX_REASON}) : verbatim probable"
    bad = QUOTE_CHARS & set(justif)
    if bad:
        return False, f"caractere de citation {sorted(bad)} : verbatim probable"
    return True, "ok"


def lint_grid_scores(grid_scores: dict) -> list[dict]:
    violations = []
    for variante, data in grid_scores.get("variantes", {}).items():
        for crit, justif in (data.get("justifications") or {}).items():
            ok, why = lint_justification(justif)
            if not ok:
                violations.append({"variante": variante, "critere": crit,
                                   "justif": justif[:40] + "...", "raison": why})
    return violations


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    path = Path(args[0]) if args else (Path(__file__).resolve().parent.parent / ".iter" / "grid_scores.json")
    if not path.exists():
        print(f"{path} absent -> lancer run_grid.py d'abord.")
        return 1
    gs = json.loads(path.read_text(encoding="utf-8"))
    v = lint_grid_scores(gs)
    if v:
        print(f"[FAIL] lint anti-PII : {len(v)} violation(s)")
        for x in v:
            print(f"  - {x['variante']}/{x['critere']} : {x['raison']}")
        return 1
    print("[OK] lint anti-PII : aucune violation (justif = critere+score, pas de verbatim).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
