#!/usr/bin/env python3
"""run_chain.py -- ORCHESTRATEUR E1->E4 (writer unique des artefacts, LOCK best-effort, reprise a zero).

Pipeline (archi §1/§2.1/§3.1) :
  E1 CERVEAU  : iterer (subprocess, BOITE NOIRE) -> artefacts .iter/ (classification, contrat, ...)
  E2 ROUTAGE  : par retour, deterministe, LIT classification.json -- ne re-classifie JAMAIS (routing.md)
  E3 GATE     : prose  -> holdout_scorer -> regression_gate (iterer) -> chain.ship ;
                jugement -> LIT regression_report d'iterer (delta_net >= 0) ; muscle ∅.
                ship_effectif = muscle.keep AND chain.ship.
  E4 NORMALISE: normalize_proposal -> proposals/<skill>/<date>/ (canonique) -> push Telegram.

INVARIANT SPY (HARN-202) : le muscle est instrumente par IMPORT-MODULE
(`orch = bridge.import_muscle("orchestrator"); orch.run_pass(...)`), JAMAIS `from ... import run_pass`.

Seams injectables (regression 0-LLM) : `brain` (iterer), `agents`/`git` (muscle), `telegram`.
En prod, `agents` = sous-agents LLM du muscle (cables en S5/S6) ; `brain` = subprocess reel iterer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge  # noqa: E402
import config as _config  # noqa: E402
import holdout_scorer  # noqa: E402
import iterer_adapter  # noqa: E402
import normalize_proposal  # noqa: E402
import patch_plan  # noqa: E402
import quarantaine  # noqa: E402
import target_golden  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = SKILL_ROOT / ".runs"
PROPOSALS_DIR = SKILL_ROOT / "proposals"
INTERACTIONS = SKILL_ROOT / "memory" / "interactions.jsonl"
MAX_WALLCLOCK_S = 45 * 60


# --- E2 : routage deterministe ------------------------------------------------

_TYPE_REMEDE = {
    "jugement": "jugement_iterer",
    "regle_detecteur": "prose_muscle",
    "contrainte_dure": "prose_muscle",
    "bloque_input_externe": "mis_de_cote",
}
_FAMILLE_TYPE = {"A": "regle_detecteur", "B": "regle_detecteur",
                 "C": "bloque_input_externe", "D": "jugement"}


def route(classification: dict) -> dict:
    """Retourne {items:[RoutageItem], branche}. Priorite prose > jugement > rien (routing.md)."""
    items = []
    for it in classification.get("items", []):
        # iterer RÉEL émet le champ `type` (vérifié en lançant son pipeline) ; on tolère `type_itere`.
        type_itere = (it.get("type_itere") or it.get("type")
                      or _FAMILLE_TYPE.get(it.get("famille", "?"), "bloque_input_externe"))
        remede = _TYPE_REMEDE.get(type_itere, "mis_de_cote")
        items.append({"feedback_id": it.get("feedback_id") or it.get("id"),
                      "type_itere": type_itere, "remede_route": remede})
    remedes = {i["remede_route"] for i in items}
    if "prose_muscle" in remedes:
        branche = "prose"
    elif "jugement_iterer" in remedes:
        branche = "jugement"
    else:
        branche = "rien-a-faire"
    return {"items": items, "branche": branche}


# --- LOCK best-effort ---------------------------------------------------------

def acquire_lock(skill: str, runs_dir: Path | None = None, lock_type: str = "pass") -> Path | None:
    runs_dir = Path(runs_dir) if runs_dir else RUNS_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)
    lock = runs_dir / f"{skill}.lock"
    if lock.exists():
        try:
            info = json.loads(lock.read_text(encoding="utf-8"))
            if time.time() - info.get("ts", 0) < MAX_WALLCLOCK_S:
                return None  # passe en cours, non perimee
        except (json.JSONDecodeError, OSError):
            pass  # lock corrompu -> on le casse
    lock.write_text(json.dumps({"skill": skill, "pid": os.getpid(), "ts": time.time(),
                                "type": lock_type}), encoding="utf-8")
    return lock


def release_lock(lock: Path | None) -> None:
    if lock is not None and lock.exists():
        lock.unlink()


# --- Adaptateur iterer (BOITE NOIRE) -----------------------------------------

class ItererBrain:
    """Adaptateur reel : lance la passe iterer PAR SKILL en subprocess (cwd=ITERER_PATH, boite noire).
    Appelle iterer/scripts/run_pass_skill.py qui fait normalize->classify->fork->[jugement] et ecrit
    les artefacts dans .iter/. Les tests deterministes injectent RecordedBrain a la place."""

    def __init__(self, config: dict):
        self.config = config
        self.iterer_path = Path(config["ITERER_PATH"])

    def _resolve(self, skill: str) -> tuple[Path, Path]:
        entry = _config.load_registry().get(skill) or {}
        root = Path(self.config["SKILLS_ROOT"])
        if "corpus_rel" not in entry:
            raise RuntimeError(f"skill '{skill}' sans corpus_rel dans le registre (rien a etudier).")
        return root / entry["corpus_rel"], root / entry["live_path_rel"]

    def run(self, skill: str) -> Path:  # pragma: no cover (LLM/subprocess, exerce en live)
        corpus, skill_md = self._resolve(skill)
        script = self.iterer_path / "scripts" / "run_pass_skill.py"
        sample = os.environ.get("AMELIORE_SAMPLE", "24")  # assez de cas pour capter un retour actionnable
        proc = subprocess.run(
            [sys.executable, str(script), "--skill", skill, "--corpus", str(corpus),
             "--skill-md", str(skill_md), "--sample", sample],
            cwd=str(self.iterer_path), capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"iterer run_pass_skill exit {proc.returncode} : {proc.stderr[-600:]}")
        return self.iterer_path / ".iter"

    def run_grid(self, skill: str, iter_dir: Path) -> dict:  # jugement : lit le report ecrit par iterer
        return json.loads((Path(iter_dir) / "regression_report.json").read_text(encoding="utf-8"))


class RecordedBrain:
    """Rejoue des artefacts iterer FIGES (regression, 0 LLM)."""

    def __init__(self, iter_dir: str | Path):
        self.iter_dir = Path(iter_dir)

    def run(self, skill: str) -> Path:
        return self.iter_dir

    def run_grid(self, skill: str, iter_dir: Path) -> dict:
        return json.loads((Path(iter_dir) / "regression_report.json").read_text(encoding="utf-8"))


# --- Orchestrateur ------------------------------------------------------------

def _read_json(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _append_interaction(record: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_chain(skill: str, *, config: dict | None = None, brain=None, agents=None, git=None,
              telegram=None, live_path: str | Path | None = None,
              date: str = "date", run_id: str = "ac_run", proposals_root: Path | None = None,
              runs_dir: Path | None = None, interactions_path: Path | None = None,
              live: bool = False, trigger: str = "manuel", plan_client=None) -> dict:
    """Une passe E1->E4. N'ecrit sur le live JAMAIS (seul apply_proposal le fait, sur 'oui').
    trigger='cron' respecte la quarantaine (2 erreurs consecutives -> skip) ; 'manuel'/'bot' bypasse."""
    config = config or _config.load_config()
    brain = brain or ItererBrain(config)
    telegram = telegram or (lambda msg: None)
    proposals_root = Path(proposals_root) if proposals_root else PROPOSALS_DIR
    interactions_path = Path(interactions_path) if interactions_path else INTERACTIONS

    summary = {"run_id": run_id, "skill": skill, "muscle_invoked": False, "ship": False,
               "proposals_emitted": 0, "statut": "erreur", "anti_patterns": []}

    # Quarantaine (S6) : le CRON skippe un skill en echec repete ; un declenchement humain override.
    if trigger == "cron" and quarantaine.is_quarantined(interactions_path, skill):
        summary["statut"] = "quarantaine"
        summary["erreur"] = quarantaine.quarantine_reason(interactions_path, skill)
        return summary

    lock = acquire_lock(skill, runs_dir)
    if lock is None:
        summary["statut"] = "verrou"
        return summary
    try:
        iter_dir = Path(brain.run(skill))                                    # E1
        classification = _read_json(iter_dir / "classification.json")
        routage = route(classification)                                      # E2
        summary["fork"] = classification.get("regime")
        summary["routage"] = routage["branche"]

        if routage["branche"] == "rien-a-faire":
            summary["statut"] = "rien-a-faire"
        elif routage["branche"] == "jugement":
            summary.update(_branch_jugement(skill, iter_dir, brain, live_path, run_id, date,
                                            proposals_root, config, plan_client))
        else:  # prose
            summary.update(_branch_prose(skill, iter_dir, config, agents, git, live_path, run_id,
                                         date, proposals_root, live, plan_client))

        if summary["statut"] == "propose":                                   # E4 push
            telegram(_render_message(skill, run_id, summary))
    except Exception as exc:  # archi §3.1 : toute étape qui échoue -> statut erreur, jamais de crash
        summary["statut"] = "erreur"
        summary["erreur"] = f"{type(exc).__name__}: {exc}"
    finally:
        release_lock(lock)
    _append_interaction({k: summary[k] for k in
                         ("run_id", "skill", "fork", "routage", "muscle_invoked", "ship",
                          "proposals_emitted", "statut", "anti_patterns", "erreur") if k in summary},
                        interactions_path)
    return summary


def _target_golden_gate(skill, live_path, candidate_text, config) -> dict:
    """Gate de non-régression GÉNÉRAL : golden du skill CIBLE avant/après. regression -> refus."""
    try:
        registry = _config.load_registry()
        return target_golden.check_no_regression(skill, live_path, candidate_text, registry,
                                                  cwd=config["SKILLS_ROOT"])
    except Exception as e:
        return {"verifiable": False, "regression": False, "reason": f"gate golden erreur: {e}"}


def _branch_jugement(skill, iter_dir, brain, live_path, run_id, date, proposals_root, config,
                     plan_client=None) -> dict:
    """Branche jugement : muscle ∅. La chaine LIT le regression_report d'iterer (delta_net >= 0)."""
    report = brain.run_grid(skill, iter_dir)
    ship = report.get("delta_net_holdout", -1) >= 0 and report.get("regression_suite") == 1.0
    out = {"muscle_invoked": False, "ship": ship, "anti_patterns": report.get("anti_patterns", [])}
    if not ship:
        out["statut"] = "refuse"
        out["proposals_emitted"] = 0
        return out
    patch = _read_json(iter_dir / "patch_jugement.json")
    before_text = Path(live_path).read_text(encoding="utf-8")
    candidate_text = normalize_proposal.apply_jugement_patch(before_text, patch)
    reg = _target_golden_gate(skill, live_path, candidate_text, config)  # non-régression GÉNÉRALE
    if reg.get("regression"):
        out.update({"statut": "refuse", "ship": False, "proposals_emitted": 0, "regression_cible": reg})
        return out
    plan = patch_plan.build_plan(before_text, candidate_text, plan_client) \
        if patch_plan.needs_plan(before_text, candidate_text) else None  # gros patch -> revue renforcée
    prop_path = normalize_proposal.normalize(
        "patch_jugement_iterer", skill=skill, date=date, run_id=run_id, proposals_root=proposals_root,
        quoi=patch.get("quoi", "Principe + exemple (jugement)."),
        pourquoi=patch.get("pourquoi", "Retour jugement mesure sur held-out (grille iterer)."),
        delta=f"delta_net={report.get('delta_net_holdout')}, reg_suite={report.get('regression_suite')}.",
        verdict={"source": "regression_report_iterer", "non_regression_verifiee": reg["verifiable"],
                 "golden_cible": reg, "plan": plan, **report},
        live_path=live_path, patch=patch)
    out.update({"statut": "propose", "proposals_emitted": 1,
                "proposition_path": str(prop_path),   # le push lit la VRAIE proposition (pas du générique)
                "non_regression_verifiee": reg["verifiable"], "revue_renforcee": bool(plan)})
    return out


def _branch_prose(skill, iter_dir, config, agents, git, live_path, run_id, date, proposals_root,
                  live=False, plan_client=None) -> dict:
    """Prose : bridge -> muscle.run_pass (import-module) -> E3 holdout_scorer -> regression_gate."""
    # Lecture via l'adaptateur : gère les shapes RÉELLES d'iterer (référence : iterer_artifacts.md).
    # case_data lève ItererShapeError si le mapping input/sid n'est pas encore réconcilié (jamais de
    # devinette). rates/diagnosis optionnels (None -> le muscle mine/diagnostique, retouche B).
    contract = iterer_adapter.read_contract(iter_dir)
    case_inputs, source_sessions = iterer_adapter.read_case_data(iter_dir, contract)
    rates = iterer_adapter.read_rates(iter_dir)
    diagnosis = iterer_adapter.read_diagnosis(iter_dir)

    call = bridge.prepare_muscle_call(contract, case_inputs, source_sessions, rates, diagnosis)

    orch = bridge.import_muscle("orchestrator")            # IMPORT-MODULE (invariant spy HARN-202)
    keep_revert = bridge.import_muscle("keep_revert")
    if agents is None:
        if live:  # PROD : agents LLM réels (Opus) ; le juge voit le golden, pas le rewriter
            agents = bridge.import_muscle("llm_agents").build_real_agents(sealed=call["golden_sealed"])
        else:     # REGRESSION : agents mock déterministes (0 LLM)
            agents = orch._MockAgents([{"capability": 0.8, "regression": 1.0}])
    git = git if git is not None else keep_revert.MockGit()
    muscle_base = iter_dir / "_muscle_out"
    res = orch.run_pass(call["skill"], Path(live_path), agents, git, muscle_base, date,
                        max_iter=call["max_iter"], golden_sealed=call["golden_sealed"],
                        rates=call["rates"], diagnosis=call["diagnosis"], fixture_source=None)

    out = {"muscle_invoked": True}
    if res["statut"] == "isolation-violation":            # fuite golden -> 0 proposition (S4)
        out.update({"statut": "isolation-violation", "ship": False, "proposals_emitted": 0})
        return out

    # E3 : mesure held-out via holdout_scorer -> regression_gate reel (iterer).
    holdout_cases = holdout_scorer.load_holdout_dir(iter_dir)
    holdout_dict = holdout_scorer.build_holdout(holdout_cases)
    gate = holdout_scorer.feed_regression_gate(holdout_dict, config["ITERER_PATH"])
    chain_ship = gate["ship"]
    muscle_keep = res["statut"] == "propose"
    ship_eff = muscle_keep and chain_ship                 # veto (ARCH-R3-002)
    out.update({"ship": ship_eff, "anti_patterns": gate.get("anti_patterns", [])})

    if not ship_eff:
        out.update({"statut": "refuse", "proposals_emitted": 0})
        return out

    cand = (muscle_base / call["skill"] / date / "candidate.md").read_text(encoding="utf-8")
    diff = (muscle_base / call["skill"] / date / "proposition.diff").read_text(encoding="utf-8")

    reg = _target_golden_gate(skill, live_path, cand, config)          # non-régression GÉNÉRALE
    if reg.get("regression"):
        out.update({"statut": "refuse", "proposals_emitted": 0, "regression_cible": reg})
        return out
    before_text = Path(live_path).read_text(encoding="utf-8")
    plan = patch_plan.build_plan(before_text, cand, plan_client) \
        if patch_plan.needs_plan(before_text, cand) else None          # gros patch -> revue renforcée
    prop_path = normalize_proposal.normalize(
        "patch_prose_muscle", skill=skill, date=date, run_id=run_id, proposals_root=proposals_root,
        quoi="Garde-fou redige par le muscle (voir proposition.diff).",
        pourquoi=f"{len(rates or [])} rate(s) mine(s), diagnostic injecte (pas de re-mining).",
        delta=f"held-out delta_net={gate['delta_net_holdout']}, reg_suite={gate['regression_suite']}.",
        verdict={"muscle_keep": muscle_keep, "chain_ship": chain_ship, "ship_effectif": ship_eff,
                 "non_regression_verifiee": reg["verifiable"], "golden_cible": reg, "plan": plan, **gate},
        candidate_md=cand, diff_text=diff)
    out.update({"statut": "propose", "proposals_emitted": 1,
                "proposition_path": str(prop_path),   # le push lit la VRAIE proposition (pas du générique)
                "non_regression_verifiee": reg["verifiable"], "revue_renforcee": bool(plan)})
    return out


def _horodatage(skill: str) -> tuple[str, str]:
    """Vraie date + run_id UNIQUE pour une passe de PROD.

    Les défauts `date="date"` / `run_id="ac_run"` de run_chain() sont des valeurs de TEST (fixtures
    déterministes). En prod, sans horodatage réel : tout atterrit dans proposals/<skill>/date/ et
    toutes les passes partagent run_id="ac_run" -> elles s'écrasent et « oui ac_run » est ambigu.
    """
    from datetime import datetime
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), f"ac_{skill}_{now.strftime('%Y%m%d_%H%M%S')}"


def _render_message(skill: str, run_id: str, summary: dict) -> str:
    """4 blocs, 0 verbatim, inclut le run_id (data_model §3).

    Lit la VRAIE proposition écrite (quoi/pourquoi/delta réels). Sans ça, l'humain validerait à
    l'aveugle : le contenu resterait dans proposition.json et le message ne dirait rien.
    Repli dégradé (texte générique) si la proposition est illisible — jamais de crash du push.
    """
    prop: dict = {}
    ppath = summary.get("proposition_path")
    if ppath:
        try:
            prop = json.loads(Path(ppath).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — message dégradé plutôt que push cassé
            prop = {}
    nrv = ("golden cible VERT (non-regression verifiee)" if summary.get("non_regression_verifiee")
           else "NON verifiee (skill sans golden runnable) -> ton jugement fait foi")
    taille = ("⚠️ GROS PATCH — revue renforcee (plan joint a la proposition)\n"
              if summary.get("revue_renforcee") else "")
    quoi = (prop.get("quoi") or "proposition mesuree (voir proposition.diff)").strip()
    pourquoi = (prop.get("pourquoi") or "retour mine, held-out mesure").strip()
    delta = (prop.get("delta") or f"ship={summary.get('ship')}").strip()
    return (f"🔧 {skill} — proposition {run_id}\n"
            f"{taille}"
            f"QUOI : {quoi}\n"
            f"POURQUOI : {pourquoi}\n"
            f"DELTA : {delta}\n"
            f"NON-REGRESSION : {nrv}.\n"
            f"VALIDER : « oui {run_id} » (ou reponds a ce message) / « non <raison> ».")


def _prod_telegram(config: dict):
    """Transport Telegram réel si dispo, sinon no-op loggé (ptb/token peuvent manquer hors prod)."""
    import os
    token, chat = os.environ.get("AMELIORE_BOT_TOKEN"), os.environ.get("AMELIORE_CHAT_ID")
    if not token or not chat:
        return lambda msg: print("[telegram absent] proposition prête (non envoyée) :\n" + msg)
    import notify
    transport = notify.TelegramTransport(token, int(chat))
    return lambda msg: transport.send(msg)


def main(argv: list[str]) -> int:
    """Entrée lancée par le bot (`ameliore <skill>` -> subprocess détaché). PROD : live=True."""
    import argparse
    _config.load_dotenv()          # charge AMELIORE_REGISTRY / token depuis .env (opérationnel)
    parser = argparse.ArgumentParser(description="Lance une passe d'amélioration sur un skill.")
    parser.add_argument("--skill", help="nom du skill (doit être dans le registre)")
    parser.add_argument("--all", action="store_true",
                        help="passe sur TOUS les skills du registre (défaut du cron nocturne)")
    parser.add_argument("--trigger", default="manuel", choices=["manuel", "bot", "cron"],
                        help="cron respecte la quarantaine ; manuel/bot l'override")
    args, _ = parser.parse_known_args(argv)
    config = _config.load_config()

    if args.all or not args.skill:
        if not args.all:  # ni --skill ni --all : afficher l'aide (comportement historique)
            print(__doc__)
            return 0
        reg = _config.load_registry()
        skills = [k for k in reg if not k.startswith("_")]
        if not skills:
            print("REFUS : registre vide (AMELIORE_REGISTRY).")
            return 2
        rc = 0
        for sk in skills:
            entry = reg.get(sk, {})
            if not (entry.get("corpus_rel") or entry.get("corpus")):
                print(json.dumps({"skill": sk, "statut": "skip", "raison": "aucun corpus a miner"},
                                 ensure_ascii=False))
                continue
            live_path = _config.resolve_live_path(sk, config=config)
            d, rid = _horodatage(sk)
            summary = run_chain(sk, config=config, live=True, live_path=live_path, date=d, run_id=rid,
                                telegram=_prod_telegram(config), trigger=args.trigger)
            print(json.dumps(summary, ensure_ascii=False))
            if summary["statut"] not in ("propose", "rien-a-faire", "quarantaine"):
                rc = 1
        return rc

    try:
        live_path = _config.resolve_live_path(args.skill, config=config)  # refuse si absent du registre
    except KeyError as e:
        print(f"REFUS : {e}")
        return 2
    d, rid = _horodatage(args.skill)
    summary = run_chain(args.skill, config=config, live=True, live_path=live_path, date=d, run_id=rid,
                        telegram=_prod_telegram(config), trigger=args.trigger)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["statut"] in ("propose", "rien-a-faire") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
