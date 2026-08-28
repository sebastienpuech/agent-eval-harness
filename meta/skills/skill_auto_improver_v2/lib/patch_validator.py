#!/usr/bin/env python3
"""patch_validator.py -- valide un patch du rewriter (append-only strict + supersedes).

Invariants (regle de fer 3, Sce.4 patch v1.1, supersedes v1.2) :
  - APPEND-ONLY STRICT : lignes_supprimees == 0 (le rewriter n'efface rien).
  - 1 SECTION MAX : sections_touchees <= 1 (anti context-collapse). Section absente -> le rewriter
    cree une section nommee en fin de fichier (fallback) = 1 section touchee.
  - SUPERSEDES (Sce.4b) : deprecier = INSERER un marqueur (lignes_supprimees reste 0) ; chaque
    entree supersedes cite {regle_id, raison, remplacee_par} ; > 3 marqueurs -> consolidation-requise.

Determinisme : la validation est du Python pur (diff de lignes), aucun LLM. Le rewriter LLM
produit le candidat ; ce module le VERIFIE. Teste sur des candidats construits depuis le SKILL.md
jouet (evals/fixtures/skill_md_jouet/).

CLI :
  python patch_validator.py --self-test
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
JOUET = SKILL_ROOT / "evals" / "fixtures" / "skill_md_jouet" / "SKILL.md"

MARKER = "⚠ DÉPRÉCIÉ"  # "⚠ DÉPRÉCIÉ" sans char accentue en clair dans le source


def diff_stats(original: str, candidate: str) -> dict:
    a, b = original.splitlines(), candidate.splitlines()
    added = deleted = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "delete":
            deleted += i2 - i1
        elif tag == "insert":
            added += j2 - j1
        elif tag == "replace":
            deleted += i2 - i1
            added += j2 - j1
    return {"lignes_ajoutees": added, "lignes_supprimees": deleted}


def _sections(md: str) -> dict:
    # Corps normalise (blanc final retire) : appendre une section ajoute un separateur vide qui
    # tomberait dans le corps de la section precedente et la ferait paraitre "modifiee" a tort.
    sections, cur, buf = {}, "__preamble__", []
    for line in md.splitlines():
        if line.startswith("## "):
            sections[cur] = "\n".join(buf).rstrip()
            cur, buf = line, []
        else:
            buf.append(line)
    sections[cur] = "\n".join(buf).rstrip()
    return sections


def sections_touched(original: str, candidate: str) -> int:
    so, sc = _sections(original), _sections(candidate)
    return sum(1 for k, v in sc.items() if k not in so or so[k] != v)


def validate_append_only(original: str, candidate: str) -> dict:
    d = diff_stats(original, candidate)
    st = sections_touched(original, candidate)
    return {"lignes_supprimees": d["lignes_supprimees"], "lignes_ajoutees": d["lignes_ajoutees"],
            "sections_touchees": st, "ok": d["lignes_supprimees"] == 0 and st <= 1}


# Neutralisation semantique d'une regle (patch red-team #4) : deprecier / ignorer / remplacer une
# regle SANS passer par le canal supersedes controle = suppression deguisee en ajout.
_DEPRECATION_RE = re.compile(
    r"(obsol[eè]te|caduque|d[eé]pr[eé]ci|p[eé]rim[eé]|ne\s+plus\s+(suivre|appliquer|tenir)|"
    r"ne\s+pas\s+(suivre|appliquer)|ignore[rz]?\b|au\s+lieu\s+de|remplace)\b",
    re.IGNORECASE)


def _added_lines(original: str, candidate: str) -> str:
    a, b = original.splitlines(), candidate.splitlines()
    added: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag in ("insert", "replace"):
            added.extend(b[j1:j2])
    return "\n".join(added)


def has_uncontrolled_deprecation(original: str, candidate: str, declared_supersedes: list[dict]) -> bool:
    """True si le patch neutralise une regle (langage de depreciation) SANS passer par supersedes
    (marqueur inline + entree citee). Ferme la faille « suppression semantique en append pur »."""
    added = _added_lines(original, candidate)
    if not _DEPRECATION_RE.search(added):
        return False
    controlled = (MARKER in added) and bool(declared_supersedes) and all(
        all(e.get(k) for k in ("regle_id", "raison", "remplacee_par")) for e in declared_supersedes)
    return not controlled


def validate_supersedes(supersedes: list[dict], original: str, candidate: str,
                        max_markers: int = 3) -> dict:
    d = diff_stats(original, candidate)
    n_marqueurs = candidate.count(MARKER)
    cite_complet = bool(supersedes) and all(
        all(e.get(k) for k in ("regle_id", "raison", "remplacee_par")) for e in supersedes)
    consolidation = n_marqueurs > max_markers
    return {"lignes_supprimees": d["lignes_supprimees"], "cite_complet": cite_complet,
            "n_marqueurs": n_marqueurs, "consolidation_requise": consolidation,
            "ok": d["lignes_supprimees"] == 0 and cite_complet and not consolidation}


# --- Constructeurs de candidats de test (depuis le SKILL.md jouet) -----------------------------

def _append_section(original: str) -> str:
    return original.rstrip() + "\n\n## Fidelite au commentaire\n\n- Lire le commentaire ENTIER avant d'y repondre.\n"

def _delete_a_line(original: str) -> str:
    return "\n".join(l for l in original.splitlines() if "§2 : reponse courte" not in l) + "\n"

def _supersede_rule(original: str) -> str:
    out = []
    for line in original.splitlines():
        out.append(line)
        if line.startswith("- §1 :"):
            out.append(f"> {MARKER} (v1) -- remplace par #16 : reprendre un mot ne prouve pas qu'on a lu")
        if line.strip() == "- §2 : reponse courte.":
            out.append("- #16 : lire le commentaire ENTIER puis repondre a ce qu'il dit (remplace §1).")
    return "\n".join(out) + "\n"

def _too_many_markers(original: str) -> str:
    extra = "\n".join(f"> {MARKER} (v{i})" for i in range(4))
    return original.rstrip() + "\n\n## Depreciations\n\n" + extra + "\n"


def _self_test() -> int:
    ok = True
    original = JOUET.read_text(encoding="utf-8")

    r1 = validate_append_only(original, _append_section(original))
    try:
        assert r1["ok"] and r1["lignes_supprimees"] == 0 and r1["sections_touchees"] == 1, r1
        print(f"  [OK] append pur : suppr={r1['lignes_supprimees']} sections={r1['sections_touchees']}")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] append pur : {e}")

    r2 = validate_append_only(original, _delete_a_line(original))
    try:
        assert not r2["ok"] and r2["lignes_supprimees"] > 0, r2
        print(f"  [OK] suppression detectee : suppr={r2['lignes_supprimees']} -> rejete")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] suppression : {e}")

    sup = [{"regle_id": "§1", "raison": "alimente le keyword-spotting", "remplacee_par": "#16"}]
    r3 = validate_supersedes(sup, original, _supersede_rule(original))
    try:
        assert r3["ok"] and r3["lignes_supprimees"] == 0 and r3["cite_complet"] and r3["n_marqueurs"] == 1, r3
        print(f"  [OK] supersedes valide : suppr=0, cite_complet, marqueurs={r3['n_marqueurs']}")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] supersedes valide : {e}")

    # Sce.4b : un supersedes qui NE cite pas remplacee_par est rejete.
    sup_bad = [{"regle_id": "§1", "raison": "x"}]
    r4 = validate_supersedes(sup_bad, original, _supersede_rule(original))
    try:
        assert not r4["ok"] and not r4["cite_complet"], r4
        print("  [OK] supersedes incomplet (sans remplacee_par) -> rejete (Sce.4b)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] supersedes incomplet : {e}")

    # Garde anti-empilement : > 3 marqueurs -> consolidation-requise.
    r5 = validate_supersedes(sup, original, _too_many_markers(original))
    try:
        assert r5["consolidation_requise"] and not r5["ok"], r5
        print(f"  [OK] {r5['n_marqueurs']} marqueurs -> consolidation-requise")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] consolidation : {e}")

    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
    sys.exit(0)
