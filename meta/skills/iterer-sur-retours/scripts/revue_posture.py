#!/usr/bin/env python3
"""revue_posture.py -- détection d'étroitesse (voie cold-review). Depuis la mission + des
situations réelles, juge l'étroitesse et produit UN candidat de patch de POSTURE (même forme qu'un
candidat jugement). Agent LLM injectable (_FakeClient en test, 0 LLM).
"""
from __future__ import annotations
import json, re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = SKILL_ROOT / "agents"


def extract_json(text: str) -> dict:
    start = text.find("{")
    depth = 0
    for i in range(start, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return json.loads(text[start:i + 1])
    raise ValueError("JSON non équilibré")


def reviser_posture(client, mission: str, situations: list) -> dict:
    system = (AGENTS_DIR / "revue-posture.md").read_text(encoding="utf-8")
    user = ("MISSION :\n" + mission[:1000] + "\n\nSITUATIONS (JSON) :\n"
            + json.dumps([{"sid": s["sid"], "input": s["input"][:300], "reponse": s["reponse"][:300],
                           "warrantee": s["warrantee"]} for s in situations], ensure_ascii=False))
    return extract_json(client.complete_sync(system, user))


class _FakeClient:
    """0-LLM : si >=1 situation warrantée dont la réponse est courte/étroite -> étroitesse + candidat."""
    def complete_sync(self, system: str, user: str, model=None) -> str:
        data = json.loads(user[user.index("["):user.rindex("]") + 1])
        etroit = [s for s in data if s.get("warrantee") and len(s["reponse"]) < 60]
        return json.dumps({
            "etroitesse": bool(etroit),
            "preuves": [{"sid": s["sid"], "dimension_tue": "levier non soulevé"} for s in etroit[:3]],
            "candidat": {"type": "posture",
                         "principe": "Raisonner depuis la mission ; soulever les leviers pertinents non mentionnés ; quand PAS : si la situation est fermée, rester focalisé.",
                         "exemple_contraste": {"mauvais": "répond à l'input seul", "bon": "relie à la mission et soulève le levier"},
                         "garde_quand_pas": "ne pas élargir sur une question fermée/logistique"},
        })


def _self_test() -> int:
    situations = [
        {"sid": "s1", "input": "j'ai refactore le module de cache", "reponse": "ok, c'est plus propre", "warrantee": True},
        {"sid": "s2", "input": "quelle commande pour relancer ?", "reponse": "make test", "warrantee": False},
    ]
    r = reviser_posture(_FakeClient(), mission="objectif long terme Z", situations=situations)
    ok = (r["etroitesse"] is True and r["candidat"]["type"] == "posture"
          and bool(r["preuves"]) and bool(r["candidat"]["garde_quand_pas"]))
    print(f"  étroitesse={r['etroitesse']} preuves={len(r['preuves'])} candidat.type={r['candidat']['type']}")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv):
    if "--self-test" in argv:
        return _self_test()
    print(__doc__); return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
