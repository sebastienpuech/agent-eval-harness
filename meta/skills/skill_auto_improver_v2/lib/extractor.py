#!/usr/bin/env python3
"""extractor.py -- CAPTURE (Session 2) : mine une liste curatee de sessions -> Rates resumes.

Perimetre MVP (spec 5 patch) : PAS d'index heuristique. On part d'une LISTE curatee de
session_ids (fichier/arg). La detection skill->session generique -> V2.

Confidentialite (regle de fer 5) : on ecrit en ROLES, jamais de texte brut ni de nom. Le resume
d'un Rate est un TEMPLATE par signal (aucune citation du transcript) + passe dans confidential.scrub
en ceinture de securite. Cf. data_model 1 (entite Rate) + references/failure_signals.md.

Robustesse read_transcript (archi patch SIM-004/HARN-006) : ne miner que les sessions `idle`
(skip `running`), timeout par lecture, et 3 budgets de passe (sessions / appels sous-agents /
wallclock). Au-dela -> statut `budget-atteint`, checkpoint, reprise au prochain trigger.

Source de transcripts abstraite :
  - FixtureSource : lit les JSON locaux de evals/fixtures/transcripts_3/ (teste par G1).
  - ProdMcpSource : adaptateur reel (MCP sessions) -- STUB, cable en Session 6. Le MCP
    `session_info.read_transcript` du plan n'existe pas tel quel dans cet env (dispo :
    ccd_session_mgmt.{list_sessions, search_session_transcripts}) -> a brancher en S6.

CLI :
  python extractor.py --fixtures      # mine les 3 fixtures -> ecrit issues.md + index.json
  python extractor.py --self-test      # G1 (2 rates) + skip running + budget-atteint
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import confidential
import isolation  # retouche A : source unique du skill cible (DEFAULT_TARGET_SKILL)

SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = SKILL_ROOT / "evals" / "fixtures" / "transcripts_3"
ISSUES_MD = SKILL_ROOT / "memory" / "issues.md"
INDEX_JSON = SKILL_ROOT / "memory" / "index.json"

# Budgets de passe (archi patch SIM-004). Volontairement bas pour un pilote mono-skill.
MAX_SESSIONS_MINED_PER_RUN = 50
MAX_SUBAGENT_CALLS_PER_RUN = 120
MAX_WALLCLOCK_SECONDS = 2700

# Lexique (references/failure_signals.md), ordre = priorite. Detection sur role=user only.
SIGNAL_PATTERNS: list[tuple[str, list[str]]] = [
    ("reformulation_manuelle", [
        r"je reformule", r"je (le )?r[ée]écris", r"je (le )?fais moi[- ]?m[êe]me",
        r"je corrige moi", r"i'?ll rewrite", r"redo it myself"]),
    ("refais", [
        r"\brefais\b", r"recommence", r"une autre (proposition|id[ée]e|version)",
        r"propose (moi )?autre chose", r"t'?as autre chose", r"try again", r"something else"]),
    ("bof_explicite", [
        r"\bbof\b", r"\bmoyen\b", r"(fait|c'est) (trop )?g[ée]n[ée]riqu",
        r"(un peu|trop|[çc]a fait) ia\b", r"pas terrible", r"\bmeh\b", r"sounds like ai"]),
    ("abandon", [
        r"laisse tomber", r"j'?abandonne", r"tant pis", r"oublie ([çc]a)", r"never mind", r"forget it"]),
]

# Resume TEMPLATE par signal (role-based, zero texte brut).
RESUME_TEMPLATES = {
    "reformulation_manuelle": "l'utilisateur reecrit lui-meme la reponse proposee (le skill a manque l'intention du changement).",
    "refais": "l'utilisateur rejette la proposition et en demande une autre.",
    "bof_explicite": "l'utilisateur juge la proposition generique/faible.",
    "abandon": "l'utilisateur abandonne la piste.",
    "tag_rejete": "resultat taggue rejete (rapproche via verdicts.md).",
}

_COMPILED = [(sig, [re.compile(p, re.IGNORECASE) for p in pats]) for sig, pats in SIGNAL_PATTERNS]


def detect_signal(messages: list[dict]) -> str | None:
    """Retourne le signal de plus haute priorite trouve dans les messages user, sinon None."""
    user_text = " \n ".join(m.get("text", "") for m in messages if m.get("role") == "user")
    for sig, regexes in _COMPILED:
        if any(r.search(user_text) for r in regexes):
            return sig
    return None


def count_distinct_signals(messages: list[dict]) -> int:
    user_text = " \n ".join(m.get("text", "") for m in messages if m.get("role") == "user")
    return sum(1 for _, regexes in _COMPILED if any(r.search(user_text) for r in regexes))


# --- Sources de transcripts --------------------------------------------------------------------

class FixtureSource:
    """Lit les transcripts JSON locaux (fixtures). Chaque fichier = {session_id, status, messages}."""

    def __init__(self, directory: Path = FIXTURES_DIR):
        self.dir = directory

    def list_sessions(self) -> list[dict]:
        out = []
        for p in sorted(self.dir.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"session_id": d["session_id"], "status": d.get("status", "idle")})
        return out

    def read_transcript(self, session_id: str) -> dict:
        for p in sorted(self.dir.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d["session_id"] == session_id:
                return d
        raise KeyError(session_id)


class ProdMcpSource:
    """Adaptateur PROD (MCP sessions) -- STUB. A cabler en Session 6.
    Le vrai mining lira ccd_session_mgmt / session_info : idle-only, read_transcript avec timeout,
    puis resume LLM anonymise. Non disponible en env non-interactif -> leve explicitement."""

    def list_sessions(self) -> list[dict]:
        raise NotImplementedError("ProdMcpSource : a cabler en Session 6 (MCP ccd_session_mgmt).")

    def read_transcript(self, session_id: str) -> dict:
        raise NotImplementedError("ProdMcpSource : a cabler en Session 6.")


# --- Extraction --------------------------------------------------------------------------------

def extract(source, session_ids: list[str] | None = None, skill: str = isolation.DEFAULT_TARGET_SKILL,
            max_sessions: int = MAX_SESSIONS_MINED_PER_RUN,
            max_subagent_calls: int = MAX_SUBAGENT_CALLS_PER_RUN) -> dict:
    """Mine la source -> {rates, mined, skipped_running, subagent_calls, statut}.
    Chaque session minee 'coute' 1 appel sous-agent (mock du resumeur ; deterministe en S2)."""
    sessions = session_ids or [s["session_id"] for s in source.list_sessions()]
    rates: list[dict] = []
    mined = skipped_running = subagent_calls = 0
    statut = "ok"
    minee_le = datetime.now(timezone.utc).isoformat(timespec="seconds")
    index: dict[str, dict] = {}

    for sid in sessions:
        if mined >= max_sessions or subagent_calls >= max_subagent_calls:
            statut = "budget-atteint"
            break
        try:
            tr = source.read_transcript(sid)
        except KeyError:
            continue
        if tr.get("status") == "running":
            skipped_running += 1
            continue  # read_transcript bloque sur running -> on skip (archi patch)
        subagent_calls += 1  # cout du resumeur (mocke en S2)
        mined += 1
        signal = detect_signal(tr.get("messages", []))
        a_rate = signal is not None
        index[sid] = {"skill_detecte": skill if a_rate else None,
                      "confiance": 0.0, "a_rate": a_rate, "minee_le": minee_le}
        if not a_rate:
            continue
        confiance = 0.9 if count_distinct_signals(tr["messages"]) >= 2 else 0.7
        resume = confidential.scrub(f"[{skill}] {RESUME_TEMPLATES[signal]}")[:280]
        index[sid]["confiance"] = confiance
        rates.append({"skill": skill, "session_id": sid, "signal": signal,
                      "resume": resume, "confiance": confiance})

    return {"rates": rates, "index": index, "mined": mined,
            "skipped_running": skipped_running, "subagent_calls": subagent_calls, "statut": statut}


def write_outputs(res: dict) -> None:
    """Append les Rates dans issues.md + fusionne index.json. Metadonnees/resumes only."""
    lines = [f"\n### Passe {datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
             f"(minees={res['mined']}, rates={len(res['rates'])}, statut={res['statut']})\n"]
    for r in res["rates"]:
        lines.append(f"- **{r['session_id']}** · signal=`{r['signal']}` · confiance={r['confiance']} "
                     f"· {r['resume']}")
    with ISSUES_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    existing = json.loads(INDEX_JSON.read_text(encoding="utf-8")) if INDEX_JSON.stat().st_size else {}
    existing.update(res["index"])
    INDEX_JSON.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_fixtures() -> dict:
    """Raccourci : mine les 3 fixtures (utilise par meta_runner.build_context / G1)."""
    return extract(FixtureSource())


def _self_test() -> int:
    ok = True
    # G1 : exactement 2 rates sur les 3 fixtures (t1 reformulation, t2 refais ; t3 propre).
    res = extract_fixtures()
    signals = sorted(r["signal"] for r in res["rates"])
    print(f"rates={len(res['rates'])} signals={signals} subagent_calls={res['subagent_calls']}")
    try:
        assert len(res["rates"]) == 2, f"attendu 2 rates, obtenu {len(res['rates'])}"
        assert signals == ["refais", "reformulation_manuelle"], signals
        # Confidentialite : aucun resume ne contient de PII (regle par construction + scrub).
        joined = " ".join(r["resume"] for r in res["rates"])
        assert not re.search(r"(@\w+|https?://)", joined), "PII dans un resume"
        print("  [OK] G1 : 2 rates (reformulation_manuelle + refais), resumes sans PII")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    # Skip running : une session running est ignoree sans bloquer.
    class _RunningSrc:
        def list_sessions(self):
            return [{"session_id": "run-1", "status": "running"}]
        def read_transcript(self, sid):
            return {"session_id": sid, "status": "running", "messages": []}
    r2 = extract(_RunningSrc())
    try:
        assert r2["skipped_running"] == 1 and r2["mined"] == 0, r2
        print("  [OK] session running skippee (0 minee, 1 skip)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    # Budget : max_sessions=1 sur 3 fixtures -> statut budget-atteint.
    r3 = extract(FixtureSource(), max_sessions=1)
    try:
        assert r3["statut"] == "budget-atteint" and r3["mined"] == 1, r3
        print("  [OK] budget-atteint respecte (mined=1, stop)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] {e}")

    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "--fixtures" in argv:
        res = extract_fixtures()
        write_outputs(res)
        print(f"[OK] {len(res['rates'])} rates ecrits (minees={res['mined']}, "
              f"subagent_calls={res['subagent_calls']}, statut={res['statut']}).")
        print(f"     -> memory/issues.md + memory/index.json")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
