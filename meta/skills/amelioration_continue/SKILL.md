---
name: amelioration_continue
description: >-
  Méta-skill orchestrateur qui améliore les AUTRES skills sur la base de l'étude des vraies sessions.
  Chaîne iterer-sur-retours (le cerveau : auto-collecte, fork factuel/jugement, held-out) → routage
  déterministe → skill_auto_improver_v2 (le muscle : réécriture GEPA sur le factuel-prose) → mesure
  sur held-out → proposition Telegram que l'utilisateur valide (« oui »). Déclencher quand l'utilisateur dit :
  améliore un skill, lance une passe d'amélioration, étudie mes sessions pour corriger un skill, fais
  tourner la chaîne d'amélioration continue, ou via le bot Telegram dédié (ameliore <skill>). NE PAS
  utiliser pour créer un skill (skill-creator), ni pour une revue à froid (skill-reviewer), ni pour
  appliquer un correctif sans mesure.
---

# amelioration_continue — chef d'orchestre de l'amélioration des skills

**Objectif** : le meilleur skill possible pour améliorer les autres skills sur la base de l'étude
des sessions réelles. Un seul écrivain live, une seule validation humaine (« oui »).

## Cadrage — quel genre de skills ce moteur améliore

Le moteur est **générique** : il s'applique à tout skill LLM+règles déjà déployé. Mais il est taillé
pour une famille précise : **les skills dont la sortie est arbitrée par le goût d'un humain** —
typiquement un assistant qui **rédige de courtes réponses aux commentaires d'une revue de code**.

C'est ce qui explique toute la mécanique, et il faut la lire avec ce cadrage en tête :
- la sortie est un **lot de propositions classées** dont l'humain en **retient une** (d'où
  `top10_sorties`, `choisi_par_user`, `score_top1` dans l'allowlist) ;
- il n'existe **pas d'oracle** sur cette sortie : le juge doit être **corrélé au goût** du
  mainteneur (`correlate_taste.py`, Spearman ρ≥0,6 sur ≥8 cas notés à la main) ;
- les checks par défaut sont des checks de **goût rédactionnel** (`profondeur_alignee`,
  `reponse_len_words`, `ne_coupe_pas_la_subordonnee_porteuse`) ;
- un fil de revue peut porter des **noms d'auteurs, des @handles et des URL internes** — d'où la
  paranoïa PII (scrub NER + allowlist stricte), qui n'est pas du zèle mais le minimum vital.

**Cas de démo du dépôt** : `demo-revue`, un assistant qui rédige les réponses aux commentaires
d'une revue de code (objection sur un choix d'implémentation, demande de contexte, remarque de
style). Le fork factuel est démontré sur un second cas sans rapport (`tableur`), pour prouver que
le moteur n'est pas prisonnier du rédactionnel.

## Règle de fer (immuable)
1. **Zéro écriture live sans « oui »** explicite. Un SEUL écrivain live = `apply_proposal` (muscle).
2. **`iterer-sur-retours` = boîte noire** : CLI subprocess, jamais d'import ni de modif.
3. **Double digue** : le held-out d'iterer n'entre JAMAIS dans le muscle ; toute proposition re-passe
   par `holdout_scorer → regression_gate` ; `ship_effectif = muscle.keep AND chain.ship`.
4. **Un accusé de réception n'est PAS un signal** : que le relecteur ait répondu, ou n'ait pas
   répondu, est une donnée **binaire** qui ne dit rien de la qualité du message — mille raisons hors
   du texte l'expliquent. Seuls le **golden de goût** (jugement, ancré sur des cas notés à la main)
   et le **détecteur** (factuel, déterministe) font foi.
5. **Confidentialité** : résumés/métadonnées only, JAMAIS de verbatim de session (Telegram ni mémoire).
6. **Modèle constant, aucun downgrade** : tous les étages tournent sur le modèle de session.
   Comparer un `avant` et un `après` n'a aucun sens si le modèle a changé entre les deux —
   le delta mesurerait le modèle, pas le correctif.
7. **Aucune publication automatique** : le moteur propose, il n'applique et ne pousse jamais
   seul. La validation humaine est un étage du pipeline, pas une politesse.

## Pipeline (E1→E4)
```
trigger → E1 iterer (subprocess, boîte noire) : collecte → fork → held-out → contrat
        → E2 routage par retour (déterministe, lit classification.json ; routing.md)
        → [ jugement : patch iterer, muscle ∅ | prose : bridge → muscle.run_pass ]
        → E3 GATE : prose → holdout_scorer → regression_gate ; jugement → lit regression_report iterer
                    ship_effectif = muscle.keep AND chain.ship
        → E4 normalisation → proposals/<skill>/<date>/ → push Telegram → « oui » → apply live
```

## Commandes (bot Telegram dédié, `bot/ameliore_bot.py`)
| Commande | Effet |
|---|---|
| `ameliore <skill>` | lance une passe (`run_chain`) en subprocess détaché ; refuse un skill absent du registre |
| `status` / `pending` | liste les propositions en attente (lecture seule) |
| `oui [run_id]` (ou réponse au message) | applique la proposition → commit → `decision.jsonl` (**seule écriture live**) |
| `non <raison>` | archive + `proposed_fixes.md` + `decision.jsonl` ; live inchangé |
`« oui »` nu avec ≥ 2 propositions en attente → liste renvoyée, rien appliqué. Passe en cours → refus.

## Lancer une passe en CLI
```
python lib/grade_chain.py --mvp          # golden MVP {S1,S4,S7,S11} (regression, 0 LLM)
python lib/grade_chain.py --suite regression
# passe réelle (live) : via le bot (ameliore <skill>) ou run_chain(live=True) — cf. état ci-dessous
```

## Config
`config.json` (gitignoré, cf. `config.example.json`) ou variables d'env : `ITERER_PATH`, `MUSCLE_PATH`,
`SKILLS_ROOT`. `references/skills_registry.json` (versionné) mappe nom de skill → SKILL.md live.
Bot : `AMELIORE_BOT_TOKEN` + `AMELIORE_CHAT_ID` (`.env`, non commité). Cf. `references/telegram.md`.

## Composants
`lib/run_chain.py` (orchestrateur E1→E4) · `lib/bridge.py` (contrat iterer → muscle) ·
`lib/holdout_scorer.py` + `lib/detectors/doublon.py` (couche de mesure) · `lib/normalize_proposal.py`
(dossier canonique) · `lib/iterer_adapter.py` (shapes réelles iterer) · `lib/notify.py` (Telegram) ·
`lib/grade_chain.py` + `lib/spy.py` (golden non-gamable) · `bot/ameliore_bot.py`.

## État de câblage (2026-07-09)
- ✅ **Chaîne S0-S4 + S5-regression verte** (60 tests) : mesure, golden, bridge + retouches muscle
  (golden muscle 16/16), orchestrateur E1→E4, bot (validation + commandes), E2E S1 + S11 injection.
- ✅ **Moteur IA du muscle câblé et prouvé LIVE** (`skill_auto_improver_v2/lib/{llm_client,llm_agents}.py` ;
  `run_chain(live=True)` → `build_real_agents`). **Passe E2E complète prouvée avec Opus réel** : le muscle
  a rédigé un garde-fou anti-doublon, juge → keep, held-out mesuré (`ship_effectif=true`), proposition émise,
  live inchangé. (Grosse génération = flaky en sandbox headless, OK en local.)
- 🟡 **`ItererBrain.run()`** (lancer iterer sur les vraies sessions) + **mapping `case_inputs`** de la shape
  réelle `{critical_checks}` : à verrouiller sur 1 run iterer demo-revue (cf. `references/iterer_artifacts.md`).
- ⏭️ **S6** : `pip install python-telegram-bot` + token dédié + tâche planifiée au logon (confirmation
  explicite) + quarantaine. Prérequis : ≥ 1 passe réelle validée par l'utilisateur.

## Plan & journal
Les documents de conception — `spec_produit.md` → `archi.md` → `data_model.md` →
`sessions_claude_code.md` (statut par session) · `journal.md` (état glissant, se rejoue) — sont
**privés et ne sont pas publiés** : c'est vers eux que pointent les renvois `§` du code, et ils ne
sont nécessaires ni pour lire ni pour faire tourner le moteur.

Ce qui vaut sans eux, c'est la **discipline** : golden vert en fin de session ; `git add` scopé ;
tags `ac-session-N` ; iterer intouché ; retouches muscle OK tant que son golden reste vert.
