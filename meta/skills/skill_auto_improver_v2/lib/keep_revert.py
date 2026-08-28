#!/usr/bin/env python3
"""keep_revert.py -- decision keep|revert + registre de variantes + choix du `best`.

Regle de decision (invariant de securite anti-gaming) :
  keep  SSI  regression == 1.0  ET  capability > best_precedent
  sinon revert. Une variante qui casse un invariant (regression < 1.0) est DISQUALIFIEE quel que
  soit son capability -> revert (G8).

Choix du `best` (patch ARCH-003) : registre {variants[{id,decision,capability,regression,commit_sha}]}.
  best = argmax(capability) parmi les variantes {decision==keep ET regression==1.0}.
  Aucune keep -> best = None -> statut `plateau`, PAS de proposition (proposals_emitted == 0).

Les effets git (commit si keep / revert sinon) sont injectes via `git_ops` (interface) -> mockables
en test, cables sur du vrai git par l'orchestrateur (Session 5). Ici : logique pure + registre.

CLI :
  python keep_revert.py --self-test
"""
from __future__ import annotations

import sys


def decide(capability: float, regression: float, best_prev_capability: float | None) -> str:
    """keep|revert. regression < 1.0 -> revert (anti-gaming). Pas de gain -> revert."""
    if regression < 1.0:
        return "revert"
    if best_prev_capability is not None and capability <= best_prev_capability:
        return "revert"
    return "keep"


class Registry:
    """Registre des variantes d'une passe (patch ARCH-003)."""

    def __init__(self) -> None:
        self.variants: list[dict] = []

    def add(self, variante_id: str, decision: str, capability: float, regression: float,
            commit_sha: str | None = None) -> None:
        self.variants.append({"variante_id": variante_id, "decision": decision,
                              "capability": capability, "regression": regression,
                              "commit_sha": commit_sha})

    def best(self) -> dict | None:
        eligibles = [v for v in self.variants if v["decision"] == "keep" and v["regression"] == 1.0]
        return max(eligibles, key=lambda v: v["capability"]) if eligibles else None

    def statut(self) -> str:
        return "propose" if self.best() else "plateau"

    def proposals_emitted(self) -> int:
        return 1 if self.best() else 0


class MockGit:
    """Enregistre les effets git sans toucher au repo (test / dry-run)."""

    def __init__(self) -> None:
        self.commits: list[str] = []
        self.reverts: list[str] = []
        self.head = "HEAD@0"

    def commit(self, variante_id: str) -> str:
        sha = f"sha-{variante_id}"
        self.commits.append(sha)
        self.head = sha
        return sha

    def revert(self, variante_id: str) -> None:
        self.reverts.append(variante_id)  # HEAD inchange (rien n'a ete commite)


def apply_decision(registry: Registry, variante_id: str, capability: float, regression: float,
                   git_ops) -> str:
    """Decide puis applique l'effet git. Retourne la decision."""
    best = registry.best()
    dec = decide(capability, regression, best["capability"] if best else None)
    if dec == "keep":
        sha = git_ops.commit(variante_id)
        registry.add(variante_id, "keep", capability, regression, sha)
    else:
        git_ops.revert(variante_id)
        registry.add(variante_id, "revert", capability, regression, None)
    return dec


def _self_test() -> int:
    ok = True
    try:
        assert decide(0.7, 1.0, 0.5) == "keep", "gain + reg 1.0 -> keep"
        assert decide(0.5, 1.0, 0.7) == "revert", "pas de gain -> revert"
        assert decide(0.9, 0.8, None) == "revert", "regression < 1.0 -> revert (G6)"
        assert decide(0.99, 0.5, 0.6) == "revert", "game (cap haut, reg cassee) -> revert (G8)"
        print("  [OK] decide : keep/revert/regression/anti-gaming")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] decide : {e}")

    # G6 : une variante en regression -> revert, best=None, plateau, 0 proposition, HEAD inchange.
    reg, git = Registry(), MockGit()
    apply_decision(reg, "v1", 0.9, 0.8, git)
    try:
        assert reg.best() is None and reg.proposals_emitted() == 0, reg.variants
        assert reg.statut() == "plateau" and git.head == "HEAD@0" and not git.commits, git.__dict__
        print("  [OK] G6 : regression -> revert, plateau, 0 proposition, HEAD inchange")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] G6 : {e}")

    # G8 : variante gamee (cap 0.99 mais reg 0.5) apres une keep legitime -> best reste la keg legit.
    reg2, git2 = Registry(), MockGit()
    apply_decision(reg2, "v1", 0.7, 1.0, git2)   # keep
    apply_decision(reg2, "v2", 0.99, 0.5, git2)  # gamee -> revert
    try:
        assert reg2.best()["variante_id"] == "v1", reg2.best()
        assert reg2.proposals_emitted() == 1 and git2.reverts == ["v2"], (reg2.variants, git2.reverts)
        print("  [OK] G8 : variante gamee ecartee, best = keep legitime (v1)")
    except AssertionError as e:
        ok = False
        print(f"  [FAIL] G8 : {e}")

    print("=> SELF-TEST OK" if ok else "=> SELF-TEST ECHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
    sys.exit(0)
