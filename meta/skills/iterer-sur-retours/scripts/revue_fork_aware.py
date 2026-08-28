#!/usr/bin/env python3
"""revue_fork_aware.py -- 2e lentille de la voie cold-review (sœur de revue_posture).

Sur un skill de JUGEMENT, repère à froid une règle MÉCANIQUE qui fige un jugement en case-à-cocher
et produit un candidat « règle → principe + exemple » (même forme de candidat que les autres),
hand-off iterer pour la mesure (grade_grille). FORK-AWARE : inactif si regime != jugement (en
factuel une règle-détecteur est un atout, pas un défaut). Agent LLM injectable (_FakeClient 0-LLM).
"""
from __future__ import annotations
import json
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = SKILL_ROOT / "agents"

# Marqueurs de règle MÉCANIQUE qui fige un jugement (case-à-cocher). Heuristique 0-LLM du fake.
_MARQUEURS_MECANIQUES = ("toujours poser", "systematiquement", "cite un fragment exact",
                         "insere une metaphore", "insère une métaphore")
# Marqueurs d'assert DÉTERMINISTE vérifiable : NE JAMAIS flaguer (checke une vérité, pas un goût).
_MARQUEURS_DETERMINISTES = ("nb de caracteres", "max ", "relances", "char_check", "format")


def extract_json(text: str) -> dict:
    start = text.find("{")
    depth = 0
    for i in range(start, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return json.loads(text[start:i + 1])
    raise ValueError("JSON non équilibré")


def reviser_fork_aware(client, regime: str, skill_md: str) -> dict:
    system = (AGENTS_DIR / "lentille-fork-aware.md").read_text(encoding="utf-8")
    user = ("regime=" + regime + "\n\nSKILL.md du skill cible :\n" + skill_md[:4000]
            + "\n\nApplique la lentille fork-aware. JSON uniquement.")
    return extract_json(client.complete_sync(system, user))


class _FakeClient:
    """0-LLM : fire seulement si regime=jugement ET une règle mécanique (hors assert déterministe)."""
    def complete_sync(self, system: str, user: str, model=None) -> str:
        low = user.lower()
        regime_jugement = "regime=jugement" in low
        # une ligne mécanique qui n'est PAS un assert déterministe
        mecanique = any(m in low for m in _MARQUEURS_MECANIQUES)
        fire = regime_jugement and mecanique
        candidat = None
        if fire:
            candidat = {"type": "regle_a_exemple", "regle_citee": "§1",
                        "principe_propose": "Poser une question SEULEMENT si elle débloque vraiment la revue (pourquoi + quand PAS), pas par règle mécanique.",
                        "exemple_contraste": {"mauvais": "question rituelle collée à la fin de chaque réponse",
                                              "bon": "une seule question, et seulement si elle ouvre ; sinon rien"},
                        "handoff": "iterer-sur-retours"}
        return json.dumps({"fire": fire, "candidat": candidat})


def _self_test() -> int:
    skill_md = ("# skill jouet (jugement)\n## Regles\n"
                "- §1 : toujours poser une question a la fin.\n"
                "- §2 : max 3 relances (assert deterministe).\n")
    ok = True
    # (a) régime jugement + règle mécanique -> fire + candidat cite §1 (pas §2 déterministe).
    r = reviser_fork_aware(_FakeClient(), "jugement", skill_md)
    ok &= (r["fire"] is True and r["candidat"]["type"] == "regle_a_exemple"
           and r["candidat"]["regle_citee"] == "§1" and r["candidat"]["handoff"] == "iterer-sur-retours")
    print(f"  jugement : fire={r['fire']} regle={r.get('candidat') and r['candidat']['regle_citee']}")
    # (b) fork-aware : même SKILL.md en régime FACTUEL -> ne fire PAS.
    r2 = reviser_fork_aware(_FakeClient(), "factuel", skill_md)
    ok &= (r2["fire"] is False and r2["candidat"] is None)
    print(f"  factuel  : fire={r2['fire']} (fork-aware : inactif attendu)")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv):
    if "--self-test" in argv:
        return _self_test()
    print(__doc__)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
