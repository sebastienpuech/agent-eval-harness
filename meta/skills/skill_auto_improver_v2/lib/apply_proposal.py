#!/usr/bin/env python3
"""apply_proposal.py -- applique (ou archive) une proposition. SEUL ecrivain du skill LIVE.

Human-in-the-loop (regle de fer 1) : la passe nocturne n'ecrit JAMAIS sur un skill live. Ce script
SEPARE est declenche par un « oui » explicite de l'utilisateur :
  - `oui`         -> copie candidate.md sur le SKILL.md live + git commit. (seule ecriture live)
  - `non <raison>`-> archive la proposition + append dans memory/proposed_fixes.md (audit only,
                     patch PRAG-005 : pas de re-injection auto au MVP).

On applique `candidate.md` (SKILL.md patche complet), pas le diff : robuste, pas de dependance a
`patch`. Le diff reste pour la lecture humaine.

CLI :
  python apply_proposal.py <skill> <date> oui
  python apply_proposal.py <skill> <date> non "raison courte"
  python apply_proposal.py --self-test
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = SKILL_ROOT / "proposals"
PROPOSED_FIXES = SKILL_ROOT / "memory" / "proposed_fixes.md"


class MockGit:
    def __init__(self) -> None:
        self.commits: list[str] = []

    def commit_file(self, path: Path, message: str) -> str:
        sha = f"sha-{len(self.commits) + 1}"
        self.commits.append(message)
        return sha


def apply(skill: str, date: str, decision: str, live_path: Path, git,
          base_dir: Path = PROPOSALS, proposed_fixes: Path = PROPOSED_FIXES) -> dict:
    d = base_dir / skill / date
    candidate = d / "candidate.md"
    if not candidate.exists():
        raise SystemExit(f"proposition introuvable : {candidate}")

    verdict = decision.strip().lower()
    if verdict == "oui":
        live_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")  # SEULE ecriture live
        sha = git.commit_file(live_path, f"[{skill}] apply proposal {date} (valide par l'utilisateur)")
        return {"action": "applied", "commit": sha, "live_path": str(live_path)}

    raison = decision[3:].strip() if decision.lower().startswith("non") else decision
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    proposed_fixes.parent.mkdir(exist_ok=True)
    with proposed_fixes.open("a", encoding="utf-8") as f:
        f.write(f"- {ts} · **{skill}** · proposition {date} · **REFUSE** : {raison or '(sans raison)'}\n")
    return {"action": "archived", "raison": raison}


def _self_test() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "proposals"
        (base / "skill-jouet" / "d1").mkdir(parents=True)
        (base / "skill-jouet" / "d1" / "candidate.md").write_text("# NOUVEAU\n", encoding="utf-8")
        live = Path(tmp) / "live_SKILL.md"
        live.write_text("# ANCIEN\n", encoding="utf-8")
        pf = Path(tmp) / "proposed_fixes.md"

        # « oui » -> applique + commit ; seule ecriture live.
        git = MockGit()
        r1 = apply("skill-jouet", "d1", "oui", live, git, base_dir=base, proposed_fixes=pf)
        try:
            assert r1["action"] == "applied" and live.read_text(encoding="utf-8") == "# NOUVEAU\n", r1
            assert len(git.commits) == 1, git.commits
            print("  [OK] oui -> candidate applique sur le live + 1 commit")
        except AssertionError as e:
            ok = False
            print(f"  [FAIL] oui : {e}")

        # « non raison » -> live inchange + proposed_fixes appende.
        live.write_text("# ANCIEN\n", encoding="utf-8")
        r2 = apply("skill-jouet", "d1", 'non trop risque', live, MockGit(), base_dir=base, proposed_fixes=pf)
        try:
            assert r2["action"] == "archived" and live.read_text(encoding="utf-8") == "# ANCIEN\n", r2
            assert "REFUSE" in pf.read_text(encoding="utf-8") and "trop risque" in pf.read_text(encoding="utf-8"), pf.read_text()
            print("  [OK] non -> live inchange + proposed_fixes.md appende (audit)")
        except AssertionError as e:
            ok = False
            print(f"  [FAIL] non : {e}")

    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if len(argv) < 3:
        print(__doc__)
        return 0
    skill, date, decision = argv[0], argv[1], " ".join(argv[2:])
    # live_path reel : a resoudre depuis le repo des skills (S6). Ici on refuse sans chemin explicite.
    raise SystemExit("apply live : passer le chemin du SKILL.md cible (cablage S6). Utilise --self-test pour la logique.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
