#!/usr/bin/env python3
"""delegation.py -- statut du contrat de delegation vers skill-auto-improver.

GATE (spec 0bis) : la delegation factuelle n'est ACQUISE que si l'on a lu le SKILL.md REEL
de la cible et verifie {fichier d'entree, format golden, invocation, verdict}.

Cible retenue = skill_auto_improver_v2, qui N'A PAS ENCORE de SKILL.md (dossier mode-plan).
=> statut = HYPOTHESE_V2. On n'ancre PAS sur v1 (decision l'utilisateur).

Tout artefact de handoff (auto_improver_call.json, Session 4) DOIT etre estampille via
`stamp()` : il porte alors `delegation_status = HYPOTHESE_V2` et ne peut pas se pretendre
verifie tant que `verify_contract()` n'a pas ete franchi contre le SKILL.md reel de v2.
"""
from __future__ import annotations

from pathlib import Path

STATUS_HYPOTHESE = "HYPOTHESE_V2"
STATUS_VERIFIE = "VERIFIE_V2"

# Cible + emplacement attendu du SKILL.md a vérifier quand v2 sera implémenté.
TARGET = "skill_auto_improver_v2"
TARGET_SKILL_MD = (Path(__file__).resolve().parents[2] / TARGET / "SKILL.md")

# Contrat pressenti (references/adapters.md B) -- a re-verifier, pas fige.
CONTRAT_HYPOTHESE = {
    "entree_machinerie": "evals/evals.json (critical_checks)",
    "entree_cible": "evals/cible/<skill>/sealed.json (golden cible scelle)",
    "runners": ["meta_runner.py", "target_runner.py", "golden_runner.py"],
    "verdict": ["capability_pass_rate", "regression_pass_rate", "decision(keep|revert)"],
    "invariant_keep": "regression_pass_rate == 1.0 ET capability en hausse",
    "invariant_holdout": "held-out retire des evals passees au moteur (source_session_id disjoint)",
}


def current_status() -> str:
    """VERIFIE_V2 seulement si la cible a un SKILL.md reel ET que son contrat a ete CONFRONTE.

    FAIL-CLOSED (correctif 2026-07-14). L'ancienne version renvoyait VERIFIE_V2 des que
    TARGET_SKILL_MD.exists(). C'etait un fail-OPEN latent : le jour ou le muscle a recu un SKILL.md,
    le gate est passe tout seul de HYPOTHESE a VERIFIE sans qu'aucune verification n'ait eu lieu --
    la docstring exigeait deja "ET a ete verifiee", le code ne testait que l'existence.
    L'existence d'un fichier n'est pas une preuve de conformite. Principe fail-closed : un gate
    dont on ne sait pas s'il est franchi est REFUSE, jamais accorde par defaut -- c'est l'absence
    de preuve qui doit couter, pas sa presence.

    Tant que la confrontation aux cles de CONTRAT_HYPOTHESE n'est pas implementee (tache S4),
    le statut reste HYPOTHESE_V2 -- meme si le SKILL.md existe.
    """
    ok, _ = verify_contract()
    return STATUS_VERIFIE if ok else STATUS_HYPOTHESE


def stamp(call: dict) -> dict:
    """Estampille un auto_improver_call.json avec le statut de delegation courant."""
    call = dict(call)
    call["delegation_status"] = current_status()
    call["delegation_cible"] = TARGET
    if current_status() == STATUS_HYPOTHESE:
        call["delegation_note"] = (
            "HYPOTHESE : contrat pressenti sur v2 (data_model), non verifie contre un SKILL.md "
            "reel. Re-ouvrir le gate en Session 4 avant tout envoi effectif au moteur."
        )
    return call


def verify_contract() -> tuple[bool, str]:
    """Franchit le gate : exige un SKILL.md reel de la cible ET la confrontation du contrat.

    FAIL-CLOSED : renvoie False tant que la confrontation n'est pas implementee. Ne JAMAIS
    renvoyer True sur la seule presence du fichier (c'etait le bug corrige le 2026-07-14).
    """
    if not TARGET_SKILL_MD.exists():
        return False, f"{TARGET}/SKILL.md absent -> delegation HYPOTHESE, rien a verifier."
    # Le SKILL.md existe (depuis que le muscle est implemente). Mais l'exigence du gate 0bis est de
    # CONFRONTER {entree, format golden, invocation, verdict} aux cles de CONTRAT_HYPOTHESE.
    # Tant que ce parsing n'est pas ecrit (tache S4), on n'a rien verifie -> on refuse.
    return False, (
        "SKILL.md present mais contrat NON confronte aux cles de CONTRAT_HYPOTHESE "
        "(parsing S4 non implemente) -> HYPOTHESE. Fail-closed : la presence d'un fichier "
        "n'est pas une verification."
    )


if __name__ == "__main__":
    ok, detail = verify_contract()
    print(f"delegation status : {current_status()}")
    print(f"gate contrat      : {'FRANCHI' if ok else 'BLOQUE'} -- {detail}")
    print(f"exemple estampille: {stamp({'skill_path': '<cible>', 'max_iter': 5})}")
