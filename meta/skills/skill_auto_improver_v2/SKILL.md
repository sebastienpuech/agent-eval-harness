---
name: skill-auto-improver-v2
description: >
  COMPOSANT INTERNE (le muscle) de la chaîne `amelioration_continue` — PAS une porte d'entrée.
  Mine les ratés réels d'un skill cible (sessions idle), diagnostique les modes de défaillance cités,
  réécrit le SKILL.md en append-only (rewriter GEPA), juge la variante contre un golden scellé
  (juge gelé séparé), garde/revert par git, et propose un diff à valider. NE fusionne JAMAIS sans
  « oui » explicite de l'utilisateur. En usage normal il est appelé par import-module depuis
  `amelioration_continue`, qui seul porte le held-out et la validation utilisateur.
  NE PAS le déclencher directement sur « améliore un skill » : utiliser `amelioration_continue`.
  Court-circuiter la chaîne saute le held-out — réservé à l'expert qui sait pourquoi il le fait, sur
  demande EXPLICITE du nom `skill-auto-improver-v2` ou de son travail propre (« mine les ratés de X »,
  « réécriture GEPA », « juge gelé », « golden scellé »).
  Remplace et rend obsolète skill-auto-improver (v1), supprimé du parc le 2026-07-14.
---

# skill-auto-improver-v2

Moteur de la couche harnais 3+4 appliqué **aux autres skills**. Il ne s'auto-améliore pas
(récursion = Goodhart démultiplié — sa propre évolution passe par mode-plan + skill-reviewer).

## Règle de fer (immuable)
1. **Human-in-the-loop** : la passe n'écrit JAMAIS sur un SKILL.md live. Seul `apply_proposal.py`,
   sur un « oui » explicite, écrit live.
2. **Juge ≠ rewriter** : le juge gelé ne voit pas les notes du rewriter ; le rewriter ne voit pas
   le golden (`isolation.py`, 2 disjonctions).
3. **Append-only strict** : un patch ajoute (suppressions == 0), 1 section max ; dépréciation via
   `supersedes` (marqueur inline). > 3 marqueurs → `consolidation-requise`.
4. **Circuit-breaker** : `max_iter = 3` ; arrêt à 3 régressions consécutives.
5. **Confidentialité** : résumés/métadonnées only, allowlist + scrub NER. Le corpus, ce sont des
   fils de revue réels : jamais de verbatim du fil, de nom d'auteur, de @handle ni de lien.
   L'extracteur écrit en rôles.
6. **Modèle constant, aucun downgrade** : tous les sous-agents héritent du modèle de session,
   pour que deux passes restent comparables entre elles.

## Pipeline (une passe, par skill cible)
```
CAPTURE (liste curatée de sessions idle → ratés résumés)      lib/extractor.py + confidential.py
  → DIAGNOSTIC (modes de défaillance cités)                   agents/diagnosticien.md + verify_citations.py
  → [ REWRITER (patch append-only) → JUGE GELÉ (golden) → keep/revert ] × k≤3
                                                              agents/rewriter.md, juge_gele.md, patch_validator.py,
                                                              golden_runner.py, keep_revert.py, isolation.py
  → PROPOSITION (report.md 4 blocs + diff)                    lib/propose.py → proposals/<skill>/<date>/
```
Writer **unique** (écritures sérialisées). La passe s'orchestre via `lib/orchestrator.py:run_pass`.

## Lancer une passe (nuit / manuel)
```
python lib/orchestrator.py            # doc
# (S6) run réel : brancher ProdMcpSource (mining) + le vrai git dans run_pass(...)
```
Le résultat atterrit dans `proposals/_A_VALIDER.md` (canal du matin).

## Valider (le matin, toi seul)
```
python lib/apply_proposal.py <skill> <date> oui           # applique le candidate + git commit (SEULE écriture live)
python lib/apply_proposal.py <skill> <date> non "raison"  # archive + note dans memory/proposed_fixes.md
```

## Signal de succès
`python lib/meta_runner.py` (golden META de la machinerie) et
`python lib/target_runner.py <skill>` (golden CIBLE). Une feature n'est « done » que si la suite
**regression = 100 %**. Aujourd'hui : le cas jugement a **0 tag réel** → `signal-insuffisant` (la passe ne
propose pas tant que le signal est sous le seuil : `< 6 cas` ou `< 2 tags`).

## État de câblage (à finir en Session 6)
- **Mining réel** : `extractor.ProdMcpSource` est un stub (le MCP `read_transcript` n'est pas dispo
  ici) → à câbler.
- **Git réel** : `keep_revert.MockGit` / `apply_proposal.MockGit` → brancher le vrai git.
- **Déclencheur** : `scheduled_task.json` = spec ; le cron n'est **pas** enregistré (à activer en
  session interactive quand la passe tourne de bout en bout).
