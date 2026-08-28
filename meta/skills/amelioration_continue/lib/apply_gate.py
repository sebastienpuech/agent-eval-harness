#!/usr/bin/env python3
"""apply_gate.py -- garde-fou STRUCTUREL à l'apply (avant commit/push).

La mesure held-out (veto E3) protège au moment de PROPOSER. Ici, au moment d'APPLIQUER (« oui »),
on vérifie que le fichier patché n'est pas cassé AVANT de commiter/pousser :
  1. append-only : aucune suppression vs l'avant (réutilise patch_validator du muscle).
  2. frontmatter intact : le bloc `--- ... ---` (name/description = déclenchement du skill) inchangé.
  3. parse minimal : name + description présents, description <= 1024 (contrainte de triggering).
Rouge -> on NE commit PAS, on restaure l'avant. (Le comportemental = golden runnable du skill cible,
absent ici -> chantier séparé.)
"""
from __future__ import annotations

import re

MAX_DESCRIPTION = 1024


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return m.group(1) if m else None


def check(before: str, after: str, muscle_import=None) -> dict:
    """Retourne {ok, checks:[{name, ok, detail}]}. muscle_import = callable(nom)->module (bridge)."""
    checks = []

    # 1. append-only (via patch_validator du muscle si dispo, sinon fallback : longueur >= et prefixe conservé)
    append_ok, detail = True, "append-only"
    if muscle_import is not None:
        try:
            pv = muscle_import("patch_validator")
            r = pv.validate_append_only(before, after)
            append_ok = bool(r.get("ok"))
            detail = f"lignes_supprimees={r.get('lignes_supprimees')}, sections_touchees={r.get('sections_touchees')}"
        except Exception as e:  # fallback conservateur
            append_ok = after.startswith(before.rstrip()[:200]) and len(after) >= len(before)
            detail = f"fallback (patch_validator indispo: {e})"
    else:
        append_ok = after.startswith(before.rstrip()[:200]) and len(after) >= len(before)
    checks.append({"name": "append_only", "ok": append_ok, "detail": detail})

    # 2. frontmatter inchangé (le triggering ne doit pas bouger)
    fm_before, fm_after = _frontmatter(before), _frontmatter(after)
    fm_ok = fm_before is not None and fm_before == fm_after
    checks.append({"name": "frontmatter_intact", "ok": fm_ok,
                   "detail": "identique" if fm_ok else "frontmatter modifié ou absent"})

    # 3. parse minimal
    desc = re.search(r"^description\s*:\s*(.*)$", fm_after or "", re.MULTILINE)
    has_name = bool(re.search(r"^name\s*:", fm_after or "", re.MULTILINE))
    desc_len = len((desc.group(1) if desc else "").strip())
    parse_ok = has_name and desc is not None and desc_len <= MAX_DESCRIPTION
    checks.append({"name": "parse_minimal", "ok": parse_ok,
                   "detail": f"name={has_name}, description_len={desc_len} (<= {MAX_DESCRIPTION})"})

    return {"ok": all(c["ok"] for c in checks), "checks": checks}
