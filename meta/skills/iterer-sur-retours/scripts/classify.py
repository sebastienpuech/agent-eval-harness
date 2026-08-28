#!/usr/bin/env python3
"""classify.py -- CÂBLAGE LLM du classificateur (le maillon manquant d'iterer).

Prend des FeedbackItem normalisés `{id, source_ref, resume, format_origine}` (sortie de
`normalize_feedback.py`) + le SKILL.md du skill CIBLE, appelle le classificateur (Opus, prompt
`agents/classificateur.md`) par batches, et écrit `.iter/classification.json` (items classés :
famille A/B/C/D + type + regle_cible + resume NEUTRALISÉ). `fork.py` recalcule ensuite regime/part.

Le client LLM est INJECTABLE -> `_FakeClient` en test (0 LLM, déterministe), `AgentSDKClient` en prod.
Garde-fous du prompt : un type par retour, exhaustivité (count == n_items, ids uniques), 0 verbatim/PII.

CLI :
  python classify.py <items.json> --skill <SKILL.md> [--out .iter/classification.json]
  python classify.py --self-test        # fake client, déterministe
  python classify.py --smoke <SKILL.md> # 1 vraie classification Opus (3 items jouets)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = SKILL_ROOT / "agents"
ITER = SKILL_ROOT / ".iter"

TYPES = ("contrainte_dure", "regle_detecteur", "bloque_input_externe", "jugement")
TYPE_FAMILLE = {"contrainte_dure": "A", "regle_detecteur": "B",
                "bloque_input_externe": "C", "jugement": "D"}
BATCH = 25


def extract_json(text: str) -> dict:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    if start == -1:
        raise ValueError(f"aucun JSON dans la réponse LLM : {text[:200]!r}")
    depth = 0
    for i in range(start, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return json.loads(text[start:i + 1])
    raise ValueError(f"JSON non équilibré : {text[:200]!r}")


def classify_batch(client, items: list[dict], skill_md: str) -> list[dict]:
    system = (AGENTS_DIR / "classificateur.md").read_text(encoding="utf-8")
    user = (
        "SKILL.md du skill CIBLE (pour situer chaque retour) :\n" + skill_md[:6000] + "\n\n"
        "FeedbackItem à classer (bloc délimité ci-dessous) :\n<ITEMS>\n"
        + json.dumps(items, ensure_ascii=False) + "\n</ITEMS>\n\n"
        "Réponds UNIQUEMENT en JSON : {\"items\": [{\"id\": str, \"type\": "
        "\"contrainte_dure|regle_detecteur|bloque_input_externe|jugement\", \"regle_cible\": "
        "\"<id de règle du SKILL cible ou null>\", \"resume\": \"<reformulation NEUTRE, 0 verbatim/PII>\"}]}."
    )
    data = extract_json(client.complete_sync(system, user))
    out = []
    for it in data.get("items", []):
        typ = it.get("type")
        if typ not in TYPES:
            raise ValueError(f"type invalide '{typ}' pour l'item {it.get('id')}")
        out.append({"id": it["id"], "famille": TYPE_FAMILLE[typ], "type": typ,
                    "regle_cible": it.get("regle_cible"), "resume": it.get("resume", "")})
    return out


def classify_all(client, items: list[dict], skill_md: str, batch: int = BATCH) -> dict:
    classified: list[dict] = []
    for i in range(0, len(items), batch):
        classified += classify_batch(client, items[i:i + batch], skill_md)
    # Exhaustivité (garde-fou dur du prompt) : rien perdu, ids uniques.
    got, want = {c["id"] for c in classified}, {it["id"] for it in items}
    if got != want:
        raise ValueError(f"complétude violée : manquants={sorted(want - got)} extra={sorted(got - want)}")
    if len(got) != len(classified):
        raise ValueError("ids dupliqués dans la classification")
    return {"n_retours_normalises": len(classified), "items": classified,
            "familles": {f: sum(1 for c in classified if c["famille"] == f) for f in "ABCD"}}


class _FakeClient:
    """Classifieur déterministe (0 LLM) : route par mots-clés du resume. Test-only."""

    def complete_sync(self, system: str, user: str, model=None) -> str:
        items = json.loads(user[user.index("<ITEMS>") + 7:user.index("</ITEMS>")])
        out = []
        for it in items:
            r = (it.get("resume") or "").lower()
            if any(w in r for w in ("bloqué", "bloque", "externe", "hors", "input")):
                typ = "bloque_input_externe"
            elif any(w in r for w in ("détecteur", "detecteur", "colonne", "champ", "doublon", "redite")):
                typ = "regle_detecteur"
            elif any(w in r for w in ("ton", "goût", "gout", "registre", "naturel", "pertinen", "cohéren")):
                typ = "jugement"
            else:
                typ = "contrainte_dure"
            out.append({"id": it["id"], "type": typ, "regle_cible": None,
                        "resume": "reformulation neutre (test)"})
        return json.dumps({"items": out})


def _self_test() -> int:
    items = [
        {"id": "t1", "source_ref": "a", "resume": "le draft répète une réponse déjà postée (doublon)", "format_origine": "chat-transcript"},
        {"id": "t2", "source_ref": "b", "resume": "le ton de la réponse passe pour condescendant", "format_origine": "chat-transcript"},
        {"id": "t3", "source_ref": "c", "resume": "info bloquée : dépend d'un input externe", "format_origine": "chat-transcript"},
    ]
    res = classify_all(_FakeClient(), items, "# skill jouet\n")
    ok = True
    try:
        fam = {c["id"]: c["famille"] for c in res["items"]}
        assert fam == {"t1": "B", "t2": "D", "t3": "C"}, fam
        assert res["n_retours_normalises"] == 3 and res["familles"]["B"] == 1
        print("  [OK] classify (fake) : doublon->B, ton->D, bloqué->C ; exhaustivité + familles")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def _smoke(skill_md_path: str) -> int:
    from llm_client import AgentSDKClient
    items = [
        {"id": "s1", "source_ref": "x", "resume": "le skill a reproposé une réponse déjà postée dans le fil", "format_origine": "chat-transcript"},
        {"id": "s2", "source_ref": "y", "resume": "réponse détaillée sur un commentaire d'une ligne", "format_origine": "chat-transcript"},
    ]
    skill_md = Path(skill_md_path).read_text(encoding="utf-8")
    res = classify_all(AgentSDKClient(), items, skill_md)
    for c in res["items"]:
        print(f"  {c['id']} -> famille={c['famille']} type={c['type']} : {c['resume'][:60]}")
    ok = res["n_retours_normalises"] == 2 and all(c["famille"] in "ABCD" for c in res["items"])
    print("=> SMOKE OK" if ok else "=> SMOKE ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "--smoke" in argv:
        rest = [a for a in argv if a != "--smoke"]
        return _smoke(rest[0] if rest else str(SKILL_ROOT / "evals" / "fixtures" / "skill_md_jouet.md"))
    p = argparse.ArgumentParser()
    p.add_argument("items", help="JSON: liste de FeedbackItem normalisés")
    p.add_argument("--skill", required=True, help="chemin du SKILL.md cible")
    p.add_argument("--out", default=str(ITER / "classification.json"))
    args = p.parse_args(argv)
    from llm_client import AgentSDKClient
    items = json.loads(Path(args.items).read_text(encoding="utf-8"))
    skill_md = Path(args.skill).read_text(encoding="utf-8")
    res = classify_all(AgentSDKClient(), items, skill_md)
    ITER.mkdir(exist_ok=True)
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK classify : {res['n_retours_normalises']} items -> {args.out} · familles={res['familles']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
