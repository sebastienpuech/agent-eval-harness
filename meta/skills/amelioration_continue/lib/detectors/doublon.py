#!/usr/bin/env python3
"""doublon.py -- detecteur DETERMINISTE d'amnesie de fil (cas fondateur S1).

Question : « le draft repete-t-il une reponse DEJA POSTEE par l'utilisateur dans le fil de revue ? »
Reponse binaire, ZERO LLM. C'est :
  - l'instrument de mesure de holdout_scorer.py (score = no_fire) ;
  - la cible du check golden `detector_fires` (data_model §4), teste sur des drafts FIGES.

Ancre a un raté réel et courant des assistants de rédaction : sur un fil de revue un peu long,
le skill re-propose une reponse quasi identique a une reponse deja postee. Le detecteur compare
le draft a chaque reponse deja postee, apres normalisation, et FIRE si la similarite depasse un seuil.

C'est le pendant FACTUEL du fork : ici il existe un oracle mecanique (deux textes se ressemblent
ou non), donc on met un garde-fou deterministe -- pas un juge de gout.

Determinisme : normalisation (minuscules, accents/ponctuation retires, espaces compactes) +
similarite = max(Jaccard de tokens, plus long n-gramme contigu commun / longueur draft).
Aucune dependance externe, aucun etat, aucun tirage aleatoire.

CLI :
  python doublon.py <draft.(md|txt)> <reponse_postee_1> [<reponse_postee_2> ...]
  python doublon.py --self-test   # prouve : FIRE sur un quasi-doublon, pas sur une reponse distincte
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = SKILL_ROOT / "evals" / "fixtures" / "s1_doublon"

# Seuils : cales pour separer un quasi-doublon (>= 0.6) d'une reponse neuve (< 0.15).
DEFAULT_THRESHOLD = 0.55
NGRAM_THRESHOLD = 0.6


def normalize(text: str) -> str:
    """minuscules, sans accents, sans ponctuation, espaces compactes."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    cleaned = []
    for ch in text:
        cleaned.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(cleaned).split())


def _tokens(text: str) -> list[str]:
    return normalize(text).split()


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _longest_common_ngram_ratio(a: list[str], b: list[str]) -> float:
    """Longueur (en tokens) du plus long segment CONTIGU commun / longueur de `a`."""
    if not a or not b:
        return 0.0
    best = 0
    # DP classique du plus long sous-tableau commun.
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best / len(a)


def similarity(draft: str, sent: str) -> float:
    da, sa = _tokens(draft), _tokens(sent)
    return max(_jaccard(da, sa), _longest_common_ngram_ratio(da, sa))


def detect(draft: str, sent_messages: list[str],
           threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Retourne {fired, matched_idx, score, threshold}. Deterministe."""
    best_idx, best_score = -1, 0.0
    for idx, msg in enumerate(sent_messages):
        score = similarity(draft, msg)
        if score > best_score:
            best_idx, best_score = idx, score
    fired = best_score >= threshold
    return {
        "fired": fired,
        "matched_idx": best_idx if fired else None,
        "score": round(best_score, 4),
        "threshold": threshold,
    }


def fires(draft: str, sent_messages: list[str],
          threshold: float = DEFAULT_THRESHOLD) -> bool:
    return detect(draft, sent_messages, threshold)["fired"]


def _golden() -> int:
    import json
    meta = json.loads((FIXTURES / "meta.json").read_text(encoding="utf-8"))
    sent = meta["sent_by_user"]
    ok = True

    doublon = (FIXTURES / "draft_doublon.md").read_text(encoding="utf-8")
    res_d = detect(doublon, sent)
    print(f"draft_doublon : fired={res_d['fired']} score={res_d['score']} (attendu fire)")
    if res_d["fired"] is not True:
        ok = False
        print("  [FAIL] devrait FIRE sur le doublon")

    propre = (FIXTURES / "draft_propre.md").read_text(encoding="utf-8")
    res_p = detect(propre, sent)
    print(f"draft_propre  : fired={res_p['fired']} score={res_p['score']} (attendu no_fire)")
    if res_p["fired"] is not False:
        ok = False
        print("  [FAIL] ne devrait PAS fire sur le propre")

    print("\n=> GOLDEN OK" if ok else "\n=> GOLDEN ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--golden" in argv:
        return _golden()
    args = [a for a in argv if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 0
    draft_arg = args[0]
    p = Path(draft_arg)
    draft = p.read_text(encoding="utf-8") if p.exists() else draft_arg
    sent = args[1:]
    res = detect(draft, sent)
    print(f"fired={res['fired']} matched_idx={res['matched_idx']} score={res['score']}")
    return 0 if res["fired"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
