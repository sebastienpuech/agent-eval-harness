#!/usr/bin/env python3
"""Regression : le gate de delegation est FAIL-CLOSED.

Incident du 2026-07-14. `current_status()` renvoyait VERIFIE_V2 des que le SKILL.md de la cible
existait. Le jour ou le muscle (skill_auto_improver_v2) a recu son SKILL.md, le gate est donc passe
tout seul de HYPOTHESE_V2 a VERIFIE_V2 -- sans qu'aucune confrontation de contrat n'ait eu lieu.
En aval, `amelioration_continue/lib/bridge.py:59` laisse passer la branche factuel-prose sur la
seule foi de ce statut : le garde-fou etait donc franchi par la simple existence d'un fichier.

Invisible sous 81 tests verts : la suite n'exerce que des fixtures ecrites a la main portant
"delegation_status": "VERIFIE_V2", jamais l'appel reel a stamp()/current_status().

Ce test existe pour trois raisons, dans l'ordre :
  - fail-closed : un gate dont on ne sait pas s'il est franchi doit REFUSER, pas accorder ;
  - un garde-fou qu'on n'a jamais essaye de contourner est decoratif -- celui-ci l'a prouve ;
  - un echec constate devient un test permanent, jamais une note dans un fichier.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import delegation  # noqa: E402


def test_skill_md_present_ne_suffit_pas_a_verifier():
    """LE test de non-regression : le fichier existe, le statut reste HYPOTHESE.

    Si ce test casse, c'est que quelqu'un a re-branche le statut sur `TARGET_SKILL_MD.exists()`.
    L'existence d'un fichier n'est pas une preuve de conformite du contrat.
    """
    assert delegation.TARGET_SKILL_MD.exists(), (
        "pre-requis du test : le muscle a bien un SKILL.md (sinon le test ne prouve rien)"
    )
    assert delegation.current_status() == delegation.STATUS_HYPOTHESE


def test_verify_contract_refuse_tant_que_la_confrontation_nest_pas_implementee():
    ok, detail = delegation.verify_contract()
    assert ok is False
    assert "non confronte" in detail.lower() or "absent" in detail.lower()


def test_stamp_porte_le_statut_hypothese_et_sa_note():
    call = delegation.stamp({"payload": "x"})
    assert call["delegation_status"] == delegation.STATUS_HYPOTHESE
    assert call["delegation_cible"] == delegation.TARGET
    assert "delegation_note" in call, "un contrat non verifie doit dire pourquoi"


def test_le_gate_aval_bloquerait_ce_contrat():
    """Le contrat estampille ne doit PAS franchir le garde-fou de bridge.py (!= VERIFIE_V2)."""
    call = delegation.stamp({"payload": "x"})
    assert call["delegation_status"] != "VERIFIE_V2", (
        "bridge.py:59 laisse passer la branche factuel-prose sur ce champ : "
        "le laisser a VERIFIE_V2 sans confrontation rouvre le fail-open"
    )
