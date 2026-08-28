#!/usr/bin/env python3
"""self_diagnosis.py -- circuit-breakers binaires du meta-skill iterer-sur-retours.

Regle de fer : le held-out se MESURE, il ne se raisonne pas. Ce script est l'instrument
qui verifie que l'instrument lui-meme est sain AVANT toute logique (Session 1).

Checks (chacun PASS / FAIL / SKIP) :
  1. expected_parse   -- evals/expected.json parse et porte les cles attendues (tableur + jugement).
  2. cases_parse      -- evals/cases/{tableur,jugement}.json parsent.
  3. completude       -- si classification.json existe : count(items) == n_retours_normalises.
                         SKIP tant que le fichier n'existe pas (produit en Session 2+).
  4. holdout_coherence-- si registry.yaml + holdout.txt existent :
                         registry.holdout == holdout.txt (rendu derive) ET
                         set(expected.holdout_doit_exclure) INTER registry.holdout == vide.
                         SKIP tant que registry.yaml n'existe pas (produit en Session 3).
  5. meta_holdout     -- evals/meta_holdout/ non vide ET aucun de ses fichiers n'apparait
                         dans memory/engine_access.log (invariant d'acces, patch HARN-003).

Sortie : exit 0 si aucun FAIL, exit 1 sinon. SKIP ne fait pas echouer.

Mode --self-test : plante un held-out INCOHERENT (holdout contient C21, qui est un cas de
retour donc dans holdout_doit_exclure) et verifie que le check de coherence le DETECTE (FAIL).
Prouve que le garde-fou echoue proprement sur un cas plante. exit 0 si le garde-fou attrape,
exit 1 s'il laisse passer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
EVALS = SKILL_ROOT / "evals"
MEMORY = SKILL_ROOT / "memory"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

EXPECTED_KEYS = {
    "tableur": {"regime_attendu", "part_oracle_min", "holdout_doit_exclure",
             "signal_attendu", "g2_factuel_ecrit_0_patch_code", "produit_contrat",
             "types_attendus"},
    "jugement": {"regime_attendu", "signal_attendu", "holdout_min", "n_rerun_min",
               "calibration_bloquante", "rho_min"},
}


class Result:
    def __init__(self, name: str, status: str, detail: str = ""):
        self.name, self.status, self.detail = name, status, detail

    def __str__(self) -> str:
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[self.status]
        return f"{icon} {self.name:<20} {self.detail}"


# --------------------------------------------------------------------------- #
# Logique de coherence held-out, isolee pour etre testable par --self-test.
# --------------------------------------------------------------------------- #
def check_holdout_coherence_logic(registry_holdout, holdout_txt_lines, holdout_doit_exclure):
    """Retourne (ok: bool, detail: str). Coeur logique reutilise par le check reel
    ET par --self-test. Ne touche pas au disque."""
    reg = list(registry_holdout)
    txt = [x for x in holdout_txt_lines if x.strip() and not x.strip().startswith("#")]
    if sorted(reg) != sorted(txt):
        return False, f"registry.holdout {sorted(reg)} != holdout.txt {sorted(txt)} (rendu derive desynchronise)"
    inter = set(holdout_doit_exclure) & set(reg)
    if inter:
        return False, f"held-out INCOHERENT : cas de retour {sorted(inter)} presents dans le held-out (digue anti-overfit contournee)"
    return True, f"held-out coherent ({len(reg)} porteurs), cas de retour exclus"


# --------------------------------------------------------------------------- #
# Checks reels
# --------------------------------------------------------------------------- #
def check_expected_parse() -> Result:
    fp = EVALS / "expected.json"
    if not fp.exists():
        return Result("expected_parse", FAIL, "evals/expected.json absent")
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return Result("expected_parse", FAIL, f"JSON invalide : {e}")
    manques = []
    for cas, keys in EXPECTED_KEYS.items():
        if cas not in data:
            manques.append(f"cas '{cas}' absent")
            continue
        miss = keys - set(data[cas])
        if miss:
            manques.append(f"{cas}: cles manquantes {sorted(miss)}")
    if manques:
        return Result("expected_parse", FAIL, " ; ".join(manques))
    return Result("expected_parse", PASS, "tableur + jugement parses, cles presentes")


def check_cases_parse() -> Result:
    manques = []
    for cas in ("tableur", "jugement"):
        fp = EVALS / "cases" / f"{cas}.json"
        if not fp.exists():
            manques.append(f"{cas}.json absent")
            continue
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            manques.append(f"{cas}.json invalide : {e}")
            continue
        if d.get("skill_cible") is None or d.get("regime_attendu") is None:
            manques.append(f"{cas}.json: champ skill_cible/regime_attendu manquant")
    if manques:
        return Result("cases_parse", FAIL, " ; ".join(manques))
    return Result("cases_parse", PASS, "tableur.json + jugement.json parses")


def check_completude() -> Result:
    fp = EVALS.parent / ".iter" / "classification.json"
    if not fp.exists():
        return Result("completude", SKIP, "classification.json absent (produit en Session 2+)")
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return Result("completude", FAIL, f"classification.json invalide : {e}")
    n_items = len(d.get("items", []))
    n_ret = d.get("n_retours_normalises")
    if n_ret is None:
        return Result("completude", FAIL, "n_retours_normalises absent")
    if n_items != n_ret:
        return Result("completude", FAIL, f"count(items)={n_items} != n_retours_normalises={n_ret}")
    return Result("completude", PASS, f"{n_items} items == {n_ret} retours normalises")


def check_holdout_coherence() -> Result:
    registry = SKILL_ROOT / "signal" / "registry.yaml"
    holdout_txt = SKILL_ROOT / "signal" / "holdout.txt"
    if not registry.exists():
        return Result("holdout_coherence", SKIP, "signal/registry.yaml absent (produit en Session 3)")
    try:
        import yaml  # lazy : requis seulement quand registry.yaml existe
    except ImportError:
        return Result("holdout_coherence", FAIL, "PyYAML requis pour lire registry.yaml (pip install pyyaml)")
    reg = yaml.safe_load(registry.read_text(encoding="utf-8")) or {}
    reg_holdout = reg.get("holdout", [])
    txt_lines = holdout_txt.read_text(encoding="utf-8").splitlines() if holdout_txt.exists() else []
    exp = json.loads((EVALS / "expected.json").read_text(encoding="utf-8"))
    exclure = exp.get("tableur", {}).get("holdout_doit_exclure", [])
    ok, detail = check_holdout_coherence_logic(reg_holdout, txt_lines, exclure)
    return Result("holdout_coherence", PASS if ok else FAIL, detail)


def check_meta_holdout() -> Result:
    mh = EVALS / "meta_holdout"
    if not mh.exists():
        return Result("meta_holdout", FAIL, "evals/meta_holdout/ absent")
    files = [p for p in mh.iterdir() if p.is_file()]
    if not files:
        return Result("meta_holdout", FAIL, "evals/meta_holdout/ vide")
    log = MEMORY / "engine_access.log"
    if log.exists():
        accessed = log.read_text(encoding="utf-8")
        touches = [p.name for p in files if p.name in accessed or str(mh.name + "/" + p.name) in accessed]
        if touches:
            return Result("meta_holdout", FAIL,
                          f"INVARIANT VIOLE : le moteur a accede a {touches} (voir engine_access.log)")
    return Result("meta_holdout", PASS, f"{len(files)} fichier(s), aucun acces moteur logge")


CHECKS = [
    check_expected_parse,
    check_cases_parse,
    check_completude,
    check_holdout_coherence,
    check_meta_holdout,
]


def run_diagnosis() -> int:
    print(f"self_diagnosis -- {SKILL_ROOT}")
    print("-" * 72)
    results = [c() for c in CHECKS]
    for r in results:
        print(r)
    print("-" * 72)
    n_fail = sum(1 for r in results if r.status == FAIL)
    n_skip = sum(1 for r in results if r.status == SKIP)
    n_pass = sum(1 for r in results if r.status == PASS)
    print(f"{n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP")
    if n_fail:
        print("=> DIAGNOSTIC ECHOUE (au moins un FAIL).")
        return 1
    print("=> DIAGNOSTIC OK (aucun FAIL ; SKIP = fichiers produits aux sessions suivantes).")
    return 0


def run_self_test() -> int:
    """Plante un held-out incoherent et verifie que le garde-fou l'attrape."""
    print("self_diagnosis --self-test : held-out incoherent plante")
    print("-" * 72)
    # Cas plante : C21 est un cas de retour (holdout_doit_exclure) mais qqn l'a mis dans le held-out.
    planted_holdout = ["C67", "C21", "C75"]
    planted_txt = ["C67", "C21", "C75"]
    doit_exclure = ["C21", "C32"]
    ok, detail = check_holdout_coherence_logic(planted_holdout, planted_txt, doit_exclure)
    print(f"held-out plante : {planted_holdout}")
    print(f"doit_exclure    : {doit_exclure}")
    print(f"resultat garde-fou : {'DETECTE (FAIL attendu)' if not ok else 'NON DETECTE'} -> {detail}")
    print("-" * 72)
    # Sanity : un held-out propre doit PASSER.
    ok2, _ = check_holdout_coherence_logic(
        ["C67", "C41", "C75"],
        ["C67", "C41", "C75"],
        doit_exclure,
    )
    if not ok and ok2:
        print("=> SELF-TEST OK : le garde-fou attrape l'incoherence ET laisse passer le cas propre.")
        return 0
    print("=> SELF-TEST ECHOUE : le garde-fou ne discrimine pas correctement.")
    return 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())
    sys.exit(run_diagnosis())
