#!/usr/bin/env python3
"""ameliore_bot.py -- bot Telegram dedie (poste de pilotage). SEULE ecriture live sur « oui ».

Commandes (archi §2.6) :
  ameliore <skill>  -> LANCE run_chain en subprocess DETACHE (apres check LOCK). Refuse si skill
                       absent du registre. La queue = journal d'audit, pas une file lue par un tiers.
  status / pending  -> LECTURE SEULE des proposition.json etat==en_attente (derive de decision.jsonl).
  oui [run_id] / reply-to -> correle, acquiert le LOCK apply, applique (apply_proposal du muscle =
                       SEULE ecriture live) -> commit -> decision.jsonl. « oui » nu + >=2 pending ->
                       rien applique, liste renvoyee. Passe en cours -> refus, 0 ecriture.
  non <raison>      -> archive + proposed_fixes.md + decision.jsonl. Live inchange.

decision.jsonl = SOURCE DE VERITE de la decision (ecrite par le SEUL bot, append-only, ARCH-006).
Toute logique est PURE/testable (transport + git + launcher injectables) ; le cablage ptb est en bas.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "lib"))

import apply_live  # noqa: E402
import bridge  # noqa: E402
import config as _config  # noqa: E402
import run_chain  # noqa: E402

PROPOSALS = SKILL_ROOT / "proposals"
DECISION_JSONL = SKILL_ROOT / "memory" / "decision.jsonl"
PROPOSED_FIXES = SKILL_ROOT / "memory" / "proposed_fixes.md"


# --- decision.jsonl : source de verite (derive etat) -------------------------

def read_decisions(decision_path: Path) -> dict:
    p = Path(decision_path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["run_id"]] = rec
    return out


def write_decision(decision_path: Path, record: dict) -> None:
    Path(decision_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(decision_path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_pending(proposals_root: Path, decision_path: Path) -> list[dict]:
    """Propositions etat==en_attente = celles sans decision dans decision.jsonl (source unique)."""
    decided = read_decisions(decision_path)
    pending = []
    root = Path(proposals_root)
    for prop_json in sorted(root.glob("*/*/proposition.json")):
        prop = json.loads(prop_json.read_text(encoding="utf-8"))
        if prop.get("run_id") not in decided:
            prop["_date_dir"] = prop_json.parent.name
            pending.append(prop)
    return pending


def resolve_run_id(arg: str | None, reply_to_msg_id: int | None, pending: list[dict]) -> str | None:
    """« oui ac_x » explicite OU reply-to (telegram_message_id) OU « oui » nu si 1 seul pending."""
    if arg and arg.strip():
        rid = arg.strip().split()[0]
        return rid if any(p["run_id"] == rid for p in pending) else None
    if reply_to_msg_id is not None:
        for p in pending:
            if p.get("telegram_message_id") == reply_to_msg_id:
                return p["run_id"]
        return None
    if len(pending) == 1:  # « oui » nu, 1 seule proposition -> non ambigu
        return pending[0]["run_id"]
    return None  # 0 ou >=2 -> ambigu


# --- Commandes lecture seule -------------------------------------------------

def _resume(txt: str, limit: int = 160) -> str:
    """Tronque au bord de MOT (+ …). Une coupe brute trahit le sens : « Calibrer …, pas sur une »
    se lit comme l'inverse de ce que dit le vrai texte (« …pas sur une cadence fixe »)."""
    t = " ".join((txt or "").split())
    if len(t) <= limit:
        return t
    return t[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def handle_pending(proposals_root: Path, decision_path: Path) -> str:
    pending = list_pending(proposals_root, decision_path)
    if not pending:
        return "Aucune proposition en attente."
    lines = [f"• {p['skill']} · {p['run_id']} · {_resume(p.get('quoi', ''))}" for p in pending]
    return f"{len(pending)} en attente :\n" + "\n".join(lines)


handle_status = handle_pending


# --- ameliore <skill> : lance run_chain detache ------------------------------

def _default_launcher(skill: str, config: dict) -> None:  # pragma: no cover (subprocess detache)
    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([sys.executable, str(SKILL_ROOT / "lib" / "run_chain.py"), "--skill", skill],
                     cwd=str(SKILL_ROOT), creationflags=creationflags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def handle_ameliore(skill: str, *, registry: dict, config: dict, runs_dir: Path,
                    launcher=_default_launcher) -> str:
    if skill not in registry or not isinstance(registry.get(skill), dict):
        return f"Skill inconnu : « {skill} » (absent du registre). Refus."
    lock = run_chain.RUNS_DIR / f"{skill}.lock" if runs_dir is None else Path(runs_dir) / f"{skill}.lock"
    if lock.exists():
        return f"Passe deja en cours sur « {skill} ». Reessaie plus tard."
    launcher(skill, config)
    return f"Passe lancee sur « {skill} » (subprocess detache). Tu recevras la proposition ici."


# --- oui / non : decision (seule ecriture live sur oui) ----------------------

def _find_proposition(proposals_root: Path, run_id: str) -> dict | None:
    for prop_json in Path(proposals_root).glob("*/*/proposition.json"):
        prop = json.loads(prop_json.read_text(encoding="utf-8"))
        if prop.get("run_id") == run_id:
            prop["_date_dir"] = prop_json.parent.name
            return prop
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def handle_oui(arg: str | None, reply_to_msg_id: int | None, *, proposals_root: Path,
               decision_path: Path, runs_dir: Path, git, live_path=None,
               registry: dict | None = None, config: dict | None = None,
               proposed_fixes: Path = PROPOSED_FIXES, push: bool = True) -> str:
    pending = list_pending(proposals_root, decision_path)
    if not pending:
        return "Aucune proposition en attente."
    run_id = resolve_run_id(arg, reply_to_msg_id, pending)
    if run_id is None:
        rids = ", ".join(p["run_id"] for p in pending)
        return (f"{len(pending)} propositions en attente — precise laquelle : « oui <run_id> » "
                f"(ou reponds au message). Candidats : {rids}")  # rien applique

    prop = _find_proposition(proposals_root, run_id)
    skill, date = prop["skill"], prop["_date_dir"]

    # LOCK apply : une passe en cours -> refus, 0 ecriture, proposition reste en_attente (S12).
    lock = run_chain.acquire_lock(skill, runs_dir, lock_type="apply")
    if lock is None:
        return f"Passe en cours sur « {skill} », reessaie dans quelques minutes. (rien applique)"
    try:
        live = Path(live_path) if live_path else _config.resolve_live_path(skill, registry, config)
        # Gate STRUCTUREL avant écriture -> commit -> push (apply_live). Rouge = rien appliqué.
        res = apply_live.apply_with_gate(skill, date, proposals_root=Path(proposals_root),
                                         live_path=live, git=git, muscle_import=bridge.import_muscle,
                                         push=push)
        if not res["ok"]:
            return (f"⛔ Refusé par le gate structurel ({res.get('raison_courte') or res.get('raison')}). "
                    f"Live INCHANGÉ, rien commité. La proposition reste en attente.")
        write_decision(decision_path, {"ts": _now(), "run_id": run_id, "decision": "oui",
                                       "raison": "", "applied": True, "commit_sha": res.get("commit")})
        checks = " · ".join(f"{c['name']}✓" for c in res["gate"]["checks"])
        return (f"✅ Appliqué « {skill} » ({run_id}) — gate: {checks} — commit {res.get('commit')} — "
                f"push: {res.get('pushed')}.")
    finally:
        run_chain.release_lock(lock)


def handle_non(run_id: str, raison: str, *, proposals_root: Path, decision_path: Path,
               git, live_path=None, registry: dict | None = None, config: dict | None = None,
               proposed_fixes: Path = PROPOSED_FIXES) -> str:
    prop = _find_proposition(proposals_root, run_id)
    if prop is None:
        return f"Proposition introuvable : {run_id}."
    skill, date = prop["skill"], prop["_date_dir"]
    live = Path(live_path) if live_path else _config.resolve_live_path(skill, registry, config)
    apply_mod = bridge.import_muscle("apply_proposal")
    apply_mod.apply(skill, date, f"non {raison}", live, git, base_dir=Path(proposals_root),
                    proposed_fixes=proposed_fixes)
    write_decision(decision_path, {"ts": _now(), "run_id": run_id, "decision": "non",
                                   "raison": raison, "applied": False, "commit_sha": None})
    return f"🗄️ Refuse « {skill} » ({run_id}) : {raison or '(sans raison)'}. Live inchange, trace gardee."


# --- Cablage python-telegram-bot (prod ; ptb non requis pour le golden) -------

def main() -> int:  # pragma: no cover (reseau/ptb, cable S6)
    import os
    from telegram import Update
    from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

    _config.load_dotenv()                         # AMELIORE_* (token, chat_id, registre) depuis .env
    token = os.environ["AMELIORE_BOT_TOKEN"]      # token DEDIE (instance unique/token)
    allowed_chat = int(os.environ["AMELIORE_CHAT_ID"])  # chat_id whiteliste en dur (.env)
    config = _config.load_config()
    registry = _config.load_registry()
    git = _RealGit(config)

    async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != allowed_chat:
            return
        text = (update.message.text or "").strip()
        reply_to = update.message.reply_to_message.message_id if update.message.reply_to_message else None
        head, _, rest = text.partition(" ")
        head = head.lower()
        if head == "ameliore":
            out = handle_ameliore(rest.strip(), registry=registry, config=config, runs_dir=None)
        elif head in ("status", "pending"):
            out = handle_pending(PROPOSALS, DECISION_JSONL)
        elif head == "oui":
            out = handle_oui(rest.strip() or None, reply_to, proposals_root=PROPOSALS,
                             decision_path=DECISION_JSONL, runs_dir=run_chain.RUNS_DIR, git=git,
                             registry=registry, config=config)
        elif head == "non":
            run_id, _, raison = rest.strip().partition(" ")
            out = handle_non(run_id, raison.strip(), proposals_root=PROPOSALS,
                             decision_path=DECISION_JSONL, git=git, registry=registry, config=config)
        else:
            out = "Commandes : ameliore <skill> · status · pending · oui [run_id] · non <raison>"
        await update.message.reply_text(out)

    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


class _RealGit:  # pragma: no cover (git reel, cable S6)
    def __init__(self, config: dict):
        self.root = Path(config["SKILLS_ROOT"])

    def commit_file(self, path: Path, message: str) -> str:
        subprocess.run(["git", "add", str(path)], cwd=str(self.root), check=True)
        subprocess.run(["git", "commit", "-m", message, "--", str(path)], cwd=str(self.root), check=True)
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(self.root),
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def push(self) -> str:
        subprocess.run(["git", "push"], cwd=str(self.root), check=True)
        return "origin (push OK)"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
