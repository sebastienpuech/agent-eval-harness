#!/usr/bin/env python3
"""llm_agents.py -- agents LLM RÉELS du muscle (diagnosticien / rewriter / juge gelé).

Implémente l'interface `agents` consommée par `orchestrator.run_pass` (diagnose/rewrite/judge)
en appelant Opus via `llm_client` (forfait Max). Les prompts vivent dans `agents/*.md` (contrats
figés). Le client est INJECTABLE -> `_FakeClient` en test (0 LLM), `AgentSDKClient` en prod.

Isolation (règle de fer muscle) : le rewriter ne reçoit JAMAIS le golden (`sealed`) ; seul le juge
le voit. On respecte ça ici — `rewrite` ne reçoit que diagnosis+skill_md ; `judge` charge le sealed.

Sorties adaptées aux shapes que `orchestrator` consomme :
  diagnose -> {"failure_modes": [...]}
  rewrite  -> {"candidate": "<SKILL.md complet>", "notes": "<str>", "supersedes": [...]}
  judge    -> {"capability": <float 0..1>, "regression": <float 0..1>}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = SKILL_ROOT / "agents"


def extract_json(text: str) -> dict:
    """Extrait le premier objet JSON d'une réponse LLM (bloc ```json ... ``` ou {...} équilibré)."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    # sinon : premier { ... } équilibré
    start = text.find("{")
    if start == -1:
        raise ValueError(f"aucun JSON dans la réponse LLM : {text[:200]!r}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError(f"JSON non équilibré dans la réponse LLM : {text[:200]!r}")


class RealAgents:
    """Agents LLM réels. `client` injectable (AgentSDKClient en prod, _FakeClient en test)."""

    def __init__(self, client=None, sealed: dict | None = None, agents_dir: Path = AGENTS_DIR):
        if client is None:
            from llm_client import AgentSDKClient
            client = AgentSDKClient()
        self.client = client
        self.sealed = sealed              # golden vu par le JUGE uniquement (jamais le rewriter)
        self.agents_dir = Path(agents_dir)
        self.calls = 0

    def _prompt(self, name: str) -> str:
        return (self.agents_dir / f"{name}.md").read_text(encoding="utf-8")

    # --- diagnosticien (dans la chaîne : court-circuité, diagnosis injecté par iterer) ---
    def diagnose(self, rates, skill_md: str) -> dict:
        self.calls += 1
        system = self._prompt("diagnosticien")
        user = (json.dumps({"rates": rates, "skill_md": skill_md}, ensure_ascii=False)
                + "\n\nRéponds UNIQUEMENT en JSON : {\"failure_modes\": [{\"nom\": str, "
                  "\"gravite\": str, \"preuve\": [{\"session_id\": str, \"citation\": str}]}]}.")
        data = extract_json(self.client.complete_sync(system, user))
        fm = data.get("failure_modes") or data.get("payload", {}).get("failure_modes", [])
        return {"failure_modes": fm}

    # --- rewriter (GEPA) : ne voit JAMAIS le golden ---
    def rewrite(self, diagnosis: dict, skill_md: str) -> dict:
        self.calls += 1
        system = self._prompt("rewriter")
        user = (json.dumps({"diagnosis": diagnosis, "skill_md_courant": skill_md}, ensure_ascii=False)
                + "\n\nRéécris le SKILL.md en APPEND-ONLY (ajoute au plus 1 section, ne supprime rien "
                  "hors canal supersedes). Réponds UNIQUEMENT en JSON : {\"candidate\": \"<SKILL.md "
                  "COMPLET patché>\", \"notes\": \"<ton raisonnement>\", \"supersedes\": [{\"regle_id\": "
                  "str, \"raison\": str, \"remplacee_par\": str}]}.")
        data = extract_json(self.client.complete_sync(system, user))
        return {"candidate": data["candidate"], "notes": data.get("notes", ""),
                "supersedes": data.get("supersedes", [])}

    # --- juge gelé : voit le golden (sealed), pas les notes du rewriter ---
    def judge(self, candidate_md: str, baseline: str) -> dict:
        self.calls += 1
        system = self._prompt("juge_gele")
        payload = {"candidate_v_k": candidate_md, "baseline_v_k_1": baseline}
        if self.sealed is not None:
            payload["golden"] = self.sealed
        user = (json.dumps(payload, ensure_ascii=False)
                + "\n\nNote le candidat vs la baseline. Réponds UNIQUEMENT en JSON : "
                  "{\"capability_pass_rate\": <float 0..1>, \"regression_pass_rate\": <float 0..1>}.")
        data = extract_json(self.client.complete_sync(system, user))
        cap = data.get("capability_pass_rate", data.get("capability"))
        reg = data.get("regression_pass_rate", data.get("regression"))
        return {"capability": float(cap), "regression": float(reg)}


def build_real_agents(sealed: dict | None = None, model: str | None = None) -> RealAgents:
    """Fabrique les agents LLM réels (prod). `sealed` = golden pour le juge (optionnel)."""
    from llm_client import AgentSDKClient, DEFAULT_MODEL
    return RealAgents(client=AgentSDKClient(model=model or DEFAULT_MODEL), sealed=sealed)


class _FakeClient:
    """Client déterministe (0 LLM) : route par le shape demandé dans le user prompt. Test-only."""

    def __init__(self):
        self.seen: list[str] = []

    def complete_sync(self, system: str, user: str, model=None) -> str:
        self.seen.append(user)
        if "capability_pass_rate" in user:
            return '{"capability_pass_rate": 0.8, "regression_pass_rate": 1.0}'
        if '"candidate"' in user:  # rewriter : APPEND-ONLY sur la baseline (append valide)
            try:
                baseline = extract_json(user).get("skill_md_courant", "# skill\n")
            except ValueError:
                baseline = "# skill\n"
            candidate = baseline.rstrip() + "\n\n## Garde-fous\n- anti-redite : relire le fil avant de repondre."
            return json.dumps({"candidate": candidate, "notes": "raisonnement", "supersedes": []})
        return ('{"failure_modes": [{"nom": "amnesie-de-fil", "gravite": "majeur",'
                ' "preuve": [{"session_id": "s1", "citation": "resume"}]}]}')


def _self_test() -> int:
    ok = True
    a = RealAgents(client=_FakeClient())
    try:
        d = a.diagnose([{"resume": "x"}], "# skill\n")
        assert d["failure_modes"] and d["failure_modes"][0]["nom"] == "amnesie-de-fil"
        r = a.rewrite(d, "# skill\n")
        assert r["candidate"].startswith("# skill") and isinstance(r["supersedes"], list)
        v = a.judge(r["candidate"], "# skill\n")
        assert v == {"capability": 0.8, "regression": 1.0}, v
        assert a.calls == 3
        # extraction JSON robuste (prose + fence)
        assert extract_json("bla\n```json\n{\"a\": 1}\n```\nblup") == {"a": 1}
        assert extract_json('texte {"b": {"c": 2}} fin') == {"b": {"c": 2}}
        print("  [OK] diagnose/rewrite/judge (fake client) + extract_json (fence + équilibré)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")
    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def _smoke() -> int:
    """UN appel Opus réel (juge, léger) pour prouver le contrat prompt->JSON de bout en bout."""
    a = build_real_agents()
    v = a.judge("# skill\n\n## Regles\n- A\n- B (nouvelle, meilleure)\n", "# skill\n\n## Regles\n- A\n")
    print(f"  juge réel -> capability={v['capability']} regression={v['regression']}")
    ok = 0.0 <= v["capability"] <= 1.0 and 0.0 <= v["regression"] <= 1.0
    print("=> SMOKE OK" if ok else "=> SMOKE ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if "--smoke" in sys.argv:
        sys.exit(_smoke())
    sys.exit(_self_test())
