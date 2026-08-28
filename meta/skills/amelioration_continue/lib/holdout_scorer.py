#!/usr/bin/env python3
"""holdout_scorer.py -- LA couche de mesure (composant central, spike E3).

`regression_gate.py` d'iterer (boite noire) consomme {holdout:{cid:{avant,apres}}} -- des
scores DEJA calcules -- et se contente de moyenner les deltas + nommer les anti-patterns.
Il ne voit JAMAIS un SKILL.md. Personne ne calculait `avant`/`apres` : c'est CE module.

Absorbe au passage ce qu'un `gate_local.py` separe devait faire (appliquer le detecteur du
registre au held-out, en LECTURE SEULE) : ce module n'a jamais ete ecrit, sa fonction vit ici.
Ne le cherche pas dans l'arbo.

Scorer un cas (factuel) = RUN le skill cible sur l'input du cas PUIS appliquer un check
deterministe (ici `detectors/doublon.py`) a la sortie -> fire/no_fire -> score.
  score = 1.0 si le detecteur NE fire PAS (bon) ; 0.0 s'il fire (doublon).
  avant = score de l'ANCIEN skill ; apres = score du NOUVEAU (candidate).

NOTE HONNETE (inevitable) : pour un skill a base de prompt, calculer avant/apres EN LIVE
exige de FAIRE TOURNER le skill (LLM) sur chaque cas -> non deterministe, N runs, budgete
(MAX_GOLDEN_WALLCLOCK). En S0 seul le mode `recorded` existe (sorties held-out figees dans les
fixtures) : deterministe, 0 LLM. Le mode `live` (suite capability) est DIFFERE apres S0.

Cote JUGEMENT : rien a scorer ici -- iterer re-mesure deja le held-out via son propre
regression_gate/grille ; la chaine LIT le resultat, ne re-score pas (cf. archi §2.4bis).

CLI :
  python holdout_scorer.py <fixtures/s1_doublon>   # affiche le dict {holdout:{cid:{avant,apres}}}
  python holdout_scorer.py --prove                 # bout-en-bout : dict -> regression_gate reel
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from detectors import doublon  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
S1_FIXTURES = SKILL_ROOT / "evals" / "fixtures" / "s1_doublon"


def resolve_iterer_path() -> Path:
    """ITERER_PATH (env) sinon le sibling `meta/skills/iterer-sur-retours`."""
    env = os.environ.get("ITERER_PATH")
    if env:
        return Path(env)
    return SKILL_ROOT.parent / "iterer-sur-retours"


# --- Scoring deterministe (mode recorded) -----------------------------------

def _score_output(draft: str, sent_messages: list[str]) -> float:
    """1.0 si le detecteur NE fire PAS (bon), 0.0 s'il fire (doublon)."""
    return 0.0 if doublon.fires(draft, sent_messages) else 1.0


def score_case_recorded(case: dict) -> dict:
    """{avant, apres} pour un cas held-out, a partir de ses sorties enregistrees."""
    sent = case["input"]["sent_by_user"]
    rec = case["recorded"]
    return {"avant": _score_output(rec["avant"], sent),
            "apres": _score_output(rec["apres"], sent)}


def score_live(skill: str, case_input: dict) -> float:
    """Mode LIVE : ferait tourner le skill (LLM) sur l'input du cas. DIFFERE apres S0."""
    raise NotImplementedError(
        "mode live (LLM budgete, MAX_GOLDEN_WALLCLOCK) differe apres S0 : "
        "en S0 seul le mode recorded (sorties figees) est prouve. cf. note honnete data_model §2."
    )


def load_holdout_dir(path: str | Path) -> list[dict]:
    """Charge les cas held-out (`held_out/*.json`) tries par nom (deterministe)."""
    path = Path(path)
    d = path if path.name == "held_out" else path / "held_out"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def build_holdout(cases: list[dict], mode: str = "recorded") -> dict:
    """Produit exactement {holdout:{cid:{avant,apres}}} -- l'entree de regression_gate."""
    if mode == "recorded":
        return {"holdout": {c["cid"]: score_case_recorded(c) for c in cases}}
    if mode == "live":
        raise NotImplementedError(
            "mode live differe apres S0 (cf. score_live). En S0 : mode=recorded uniquement."
        )
    raise ValueError(f"mode inconnu : {mode!r}")


# --- Preuve bout-en-bout : le dict passe dans le VRAI regression_gate --------

def feed_regression_gate(holdout_dict: dict, iterer_path: str | Path | None = None) -> dict:
    """Lance le vrai `regression_gate.py` d'iterer (subprocess, cwd=ITERER_PATH, boite noire)
    sur le dict, et retourne son `regression_report.json`. Prouve la consommabilite."""
    iterer_path = Path(iterer_path) if iterer_path else resolve_iterer_path()
    gate = iterer_path / "scripts" / "regression_gate.py"
    if not gate.exists():
        raise SystemExit(f"regression_gate introuvable : {gate} (configurer ITERER_PATH ?)")

    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump(holdout_dict, tmp, ensure_ascii=False)
        tmp.close()
        proc = subprocess.run(
            [sys.executable, str(gate), tmp.name],
            cwd=str(iterer_path), capture_output=True, text=True,
        )
    finally:
        os.unlink(tmp.name)

    report_path = iterer_path / ".iter" / "regression_report.json"
    if not report_path.exists():
        raise SystemExit(
            f"regression_gate n'a pas produit de report (exit={proc.returncode}) : {proc.stderr}"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["_exit_code"] = proc.returncode  # 0 = ship, 3 = refus (cf. CLI iterer)
    return report


def _prove() -> int:
    cases = load_holdout_dir(S1_FIXTURES)
    d = build_holdout(cases)
    print("=== holdout_scorer sur S1 (mode recorded) ===")
    print(json.dumps(d, ensure_ascii=False, indent=2))
    print("\n=== feed -> regression_gate reel (boite noire iterer) ===")
    report = feed_regression_gate(d)
    print(f"  delta_net={report['delta_net_holdout']:+}  "
          f"reg_suite={report['regression_suite']}  ship={report['ship']}  "
          f"exit={report['_exit_code']}")
    ok = report["ship"] is True and report["regression_suite"] == 1.0
    print("\n=> PREUVE OK (dict consommable + ship)" if ok else "\n=> PREUVE ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--prove" in argv:
        return _prove()
    args = [a for a in argv if not a.startswith("-")]
    target = Path(args[0]) if args else S1_FIXTURES
    d = build_holdout(load_holdout_dir(target))
    print(json.dumps(d, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
