#!/usr/bin/env python3
"""propose.py -- ecrit la proposition matinale (patch handoff SIM-005).

Une passe qui a un `best` ecrit `proposals/<skill>/<date>/` :
  - report.md         : rapport matinal en 4 BLOCS (quoi / a cause de quels rates / delta golden / valider)
  - proposition.diff  : le diff lisible (unified)
  - candidate.md      : le SKILL.md patche COMPLET (artefact applique par apply_proposal.py)
  - verdict.json      : le verdict du juge
Et appende une ligne dans `proposals/_A_VALIDER.md` (canal de notification que l'utilisateur lit le matin).

AUCUNE ecriture sur le skill live ici (sandbox proposals/ uniquement). L'application live est
un outil SEPARE : apply_proposal.py, declenche par un « oui » explicite.

CLI :
  python propose.py --self-test
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = SKILL_ROOT / "proposals"

# Les 4 blocs obligatoires du rapport matinal (G10).
BLOCS = ["## Quoi", "## A cause de quels rates", "## Delta golden", "## Valider"]


def write_proposal(skill: str, date: str, quoi: str, pourquoi: str, delta_golden: str,
                   diff_text: str, candidate_md: str, verdict: dict,
                   base_dir: Path = PROPOSALS) -> Path:
    d = base_dir / skill / date
    d.mkdir(parents=True, exist_ok=True)
    report = (
        f"# Proposition -- {skill} ({date})\n\n"
        f"## Quoi\n{quoi}\n\n"
        f"## A cause de quels rates\n{pourquoi}\n\n"
        f"## Delta golden\n{delta_golden}\n\n"
        f"## Valider\nReponds `oui` pour appliquer, `non <raison>` pour archiver.\n"
        f"`python lib/apply_proposal.py {skill} {date} oui`\n"
    )
    (d / "report.md").write_text(report, encoding="utf-8")
    (d / "proposition.diff").write_text(diff_text, encoding="utf-8")
    (d / "candidate.md").write_text(candidate_md, encoding="utf-8")
    (d / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")

    av = base_dir / "_A_VALIDER.md"
    if not av.exists():
        av.write_text("# Propositions a valider\n\n", encoding="utf-8")
    with av.open("a", encoding="utf-8") as f:
        f.write(f"- [ ] **{skill}** {date} -- {quoi} "
                f"(`python lib/apply_proposal.py {skill} {date} oui`)\n")
    return d


def report_has_4_blocs(report_text: str) -> bool:
    return all(b in report_text for b in BLOCS)


def _self_test() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        d = write_proposal(
            "skill-jouet", "test-date",
            quoi="Deprecie §1 (keyword-spotting) + appende regle de fidelite au sens (#16).",
            pourquoi="2 rates minees : la reponse rate l'intention du changement / proposition generique rejetee.",
            delta_golden="+0.10 capability, regression 100%.",
            diff_text="--- a\n+++ b\n@@\n+regle #16\n",
            candidate_md="# skill\n\n## Regles\n- #16\n",
            verdict={"capability_pass_rate": 0.8, "regression_pass_rate": 1.0, "decision": "keep"},
            base_dir=Path(tmp),
        )
        report = (d / "report.md").read_text(encoding="utf-8")
        try:
            assert report_has_4_blocs(report), "report.md doit contenir les 4 blocs"
            assert (d / "proposition.diff").exists() and (d / "candidate.md").exists(), "diff+candidate ecrits"
            av_txt = (Path(tmp) / "_A_VALIDER.md").read_text(encoding="utf-8")
            assert av_txt.count("- [ ]") == 1 and "skill-jouet" in av_txt, "_A_VALIDER : 1 ligne de checklist"
            print("  [OK] report 4 blocs + diff + candidate + _A_VALIDER")
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
