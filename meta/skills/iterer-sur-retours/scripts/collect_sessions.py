#!/usr/bin/env python3
r"""collect_sessions.py -- auto-collecte des sessions ou un skill CIBLE a ete appele.

Decouvre les transcripts Cowork (local-agent-mode-sessions) ET Claude Code (.claude/projects),
filtre par NOM DE SKILL + FENETRE DE DATES (ex. J-7), et extrait les tours de conversation.

Pieges Windows geres :
  - Chemins > 260 car (MAX_PATH) : prefixe long-path \\?\ pour toute I/O.
  - Encodage : lecture utf-8 errors=replace.

CONFIDENTIALITE : ce module DECOUVRE et extrait les tours en zone JIT locale (.iter/collected/,
gitignore). Il n'imprime que des METADONNEES (nb sessions, dates, compteurs), jamais le contenu.
La neutralisation en FeedbackItem est faite par adapt_chat.py + le classificateur (LLM).

CLI :
  python collect_sessions.py --skill skill-jugement --since-days 7
  python collect_sessions.py --skill demo-revue --since-days 30 --root <chemin>
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = SKILL_ROOT / ".iter" / "collected"

COWORK_ROOT = os.path.expandvars(r"%APPDATA%\Claude\local-agent-mode-sessions")
CC_ROOT = os.path.expandvars(r"%USERPROFILE%\.claude\projects")


def _long(p: str) -> str:
    """Prefixe long-path Windows pour depasser MAX_PATH (260)."""
    ap = os.path.abspath(p)
    if os.name == "nt" and not ap.startswith("\\\\?\\"):
        return "\\\\?\\" + ap
    return ap


def _iter_transcripts(roots: list[str]):
    for root in roots:
        if not os.path.isdir(root):
            continue
        for f in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
            base = os.path.basename(f)
            # transcript principal : sous /projects/, pas audit, pas subagents
            if f"{os.sep}projects{os.sep}" not in f:
                continue
            if "subagents" in f or base == "audit.jsonl":
                continue
            yield f


def _extract_turns(path: str) -> list[dict]:
    """Retourne [{role, text, ts}] pour les tours user/assistant. Long-path safe."""
    turns = []
    try:
        with open(_long(path), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = d.get("message")
                if not isinstance(m, dict):
                    continue
                role = m.get("role")
                if role not in ("user", "assistant"):
                    continue
                c = m.get("content")
                if isinstance(c, list):
                    text = " ".join(b.get("text", "") for b in c
                                    if isinstance(b, dict) and b.get("type") == "text")
                else:
                    text = str(c or "")
                text = text.strip()
                if text:
                    turns.append({"role": role, "text": text, "ts": d.get("timestamp")})
    except (OSError, ValueError):
        return []
    return turns


def collect(skill: str, since_days: int, roots: list[str]) -> list[dict]:
    cutoff = time.time() - since_days * 86400
    sessions = []
    for f in _iter_transcripts(roots):
        try:
            mt = os.path.getmtime(_long(f))
        except OSError:
            continue
        if mt < cutoff:
            continue
        # filtre skill : mention dans le fichier (lecture bornee)
        try:
            with open(_long(f), encoding="utf-8", errors="replace") as fh:
                head = fh.read(40000)
        except OSError:
            continue
        if skill.lower() not in head.lower():
            continue
        turns = _extract_turns(f)
        if not turns:
            continue
        sessions.append({
            "session_file": f,
            "mtime": mt,
            "date": time.strftime("%Y-%m-%d", time.localtime(mt)),
            "n_turns": len(turns),
            "n_user": sum(1 for t in turns if t["role"] == "user"),
            "turns": turns,
        })
    sessions.sort(key=lambda s: s["mtime"], reverse=True)
    return sessions


def main() -> int:
    args = sys.argv[1:]
    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args else default
    skill = opt("--skill")
    if not skill:
        print("usage: collect_sessions.py --skill <nom> [--since-days N] [--root <chemin>]")
        return 1
    since = int(opt("--since-days", "7"))
    roots = [opt("--root")] if "--root" in args else [COWORK_ROOT, CC_ROOT]

    sessions = collect(skill, since, roots)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Ecrit les bundles JIT (PII locale, gitignore) ; n'imprime QUE des metadonnees.
    manifest = []
    for i, s in enumerate(sessions, 1):
        bundle = OUT_DIR / f"{skill}_{i:02d}.json"
        bundle.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
        manifest.append({"date": s["date"], "n_turns": s["n_turns"],
                         "n_user": s["n_user"], "bundle": bundle.name})
    (OUT_DIR / f"_manifest_{skill}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"skill='{skill}'  fenetre=J-{since}  -> {len(sessions)} session(s) trouvee(s)")
    for m in manifest:
        print(f"  - {m['date']}  {m['n_turns']} tours ({m['n_user']} user)  -> {m['bundle']}")
    print(f"\nBundles JIT (PII locale, gitignore) : {OUT_DIR.relative_to(SKILL_ROOT)}")
    print("Etape suivante : adapt_chat.py neutralise ces tours en FeedbackItem[] (classificateur).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
