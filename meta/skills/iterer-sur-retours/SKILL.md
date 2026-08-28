---
name: iterer-sur-retours
description: >
  COMPOSANT INTERNE (le cerveau) de la chaine `amelioration_continue` -- PAS une porte d'entree.
  Transforme un lot de retours terrain sur un skill LLM+regles DEJA DEPLOYE en une amelioration
  MESUREE et non-overfittee. Route selon le fork : tache a verite verifiable mecaniquement
  (factuel -> matrice deterministe + garde-fous, patch delegue au muscle skill-auto-improver-v2) vs
  jugement subjectif (jugement -> juge-par-grille ancre + exemples contrastes, et MOINS de regles).
  Ce skill PRODUIT le contrat d'entree du muscle ; il n'ecrit lui-meme que le patch JUGEMENT
  (principe + exemple). En usage normal il est lance en subprocess par `amelioration_continue`,
  qui seul porte le held-out et la validation utilisateur.
  NE PAS le declencher directement sur "ameliore un skill" / "j'ai des retours sur un skill" :
  utiliser `amelioration_continue`. Court-circuiter la chaine saute le held-out et la validation --
  reserve a l'expert qui sait pourquoi il le fait, sur demande EXPLICITE du nom `iterer-sur-retours`
  ou d'un de ses artefacts (.iter/, classification.json, fork factuel/jugement, matrice de retours).
  NE PAS utiliser pour creer un skill neuf (skill-creator-v12), auditer a froid (skill-reviewer-v2),
  ou deployer (deploy-skill-edite).
---

# iterer-sur-retours

Meta-skill : opere sur un AUTRE skill (LLM + regles) deja deploye. Entree = lot de retours reels
sur plusieurs cas + repo cible + corpus. Sortie = amelioration **mesuree sur held-out**, routee
selon le fork, jamais un fix qui regresse le net.

**Cadrage** : le moteur est generique, mais il est taille pour les skills dont la sortie est
**arbitree par le gout d'un humain** — typiquement un assistant qui redige de courtes reponses
aux commentaires d'une revue de code. C'est pour eux que la branche JUGEMENT existe (aucun oracle
-> juge ancre par correlation au gout, `correlate_taste.py`), et c'est de la que vient la severite
du contrat de confidentialite : un fil de revue porte des noms d'auteurs, des @handles et des URL
internes. Cas de demo : `demo-revue` (reponses courtes sur un fil de revue) pour la branche
jugement ; `tableur` (retours a verite verifiable mecaniquement) pour la branche factuelle.

## Regles de fer (immuables)

1. **« Generalise / coherent » se MESURE sur un held-out sanctuarise, jamais par raisonnement.**
   Aucune conclusion « ca generalise » sans >=1 held-out a l'appui.
2. **Held-out sanctuarise** : un cas reserve a la mesure ne sert JAMAIS a regler une regle, et il est
   **retire des evals passees a auto-improver** (sinon la digue anti-overfit est contournee).
3. **Chaque echec reel devient un test permanent** (un held-out de plus), jamais une regle isolee de plus.
4. **Route par ARTEFACT** : sur le factuel, produit le **contrat d'entree** d'auto-improver
   (`auto_improver_call.json`), **0 patch de code**. Le seul patch ecrit par ce skill = le patch
   **jugement** (principe + exemple).
5. **Remedes OPPOSES selon le fork** : factuel -> +garde-fous deterministes ; jugement -> **-regles, +exemples**
   (empiler des regles sur du jugement fragmente la coherence).
6. **Confidentialite** : jamais de verbatim/PII en memoire ni artefact (resumes/metadonnees only ;
   lint anti-PII sur `grid_scores.json`).
7. **Modele constant, aucun downgrade** : une mesure avant/apres suppose le modele identique
   entre les deux passes, sans quoi le delta mesure le modele et non le correctif.
8. **Aucune publication automatique** : rien n'est applique ni pousse sans validation humaine.

## Philosophie (socle hors-cadre)
Mesure > raisonnement. La tache choisit le remede. Rendre visible le silencieux (une regle qui ne
s'applique pas le DIT). Coherence > completude de regles.

## Pipeline (ordre a suivre)

> Scripts dans `scripts/`, agents dans `agents/`, patrons dans `references/`. Le signal de succes
> du skill lui-meme = `evals/` (meta-golden-set) + `scripts/self_diagnosis.py`.

**Etape 0 — pre-requis (AVANT toute mesure)**
1. **Faisabilite corpus** : `python scripts/feasibility.py <case.json>`. Echec -> `bloque_input_externe`
   (Scenario 3), stop propre (ne PAS reconstruire un corpus).
2. **Contrat de delegation (gate)** : lire le SKILL.md REEL de `skill-auto-improver-v2` (le muscle,
   dossier `meta/skills/skill_auto_improver_v2/`) et documenter {entree, format golden, invocation,
   verdict} dans `references/adapters.md`. Tant que non verifie -> `python scripts/delegation.py`
   renvoie `HYPOTHESE_V2` (estampille tout contrat produit).
   (Le v1 `skill-auto-improver` a ete supprime du parc le 2026-07-14 : il n'y a plus de "ou v2".)
3. **Normalisation** : `python scripts/normalize_feedback.py` (4 adaptateurs : tracker-HTML,
   jsonl-header-prose, tags, **chat-transcript**). Format sans adaptateur -> bloque (S3).
   Assertion `n_out+n_dupes==n_in`.

   **Mode AUTO-COLLECTE (Cowork/Claude Code)** : quand l'utilisateur dit « va lire mes sessions
   ou j'ai appele <skill> » :
   - `python scripts/collect_sessions.py --skill <cible> --since-days 7` -> decouvre les sessions
     (Cowork `local-agent-mode-sessions` + CC `.claude/projects`), long-path safe (>260 car),
     filtre par date + nom de skill, extrait les tours en JIT (`.iter/collected/`, **gitignore**,
     PII locale — n'imprime que des metadonnees).
   - `python scripts/adapt_chat.py <bundle>` -> candidats retour (tour user apres tour assistant).
   - Le **classificateur** (agent) lit les bundles, NEUTRALISE (sans-PII) et classe. Rien de brut
     ne persiste hors `.iter/`.

**Planner (definir le succes AVANT de generer)**
4. **Fork** (`agents/classificateur.md` emet les familles ; `scripts/fork.py` recalcule) :
   `part_oracle>=0.5 -> factuel` ; `<=0.2 -> jugement` ; entre -> `mixte` (regime dominant + sous-routine).
5. **Classer** les retours en 4 familles (A structurelle / B detecteur / C bloque input / D jugement),
   par BATCH de 20-30, complétude `count(items)==n_retours` (`references/classification.md`).
6. **Held-out (registre unique)** : `python scripts/split_holdout.py` ECRIT `signal/registry.yaml.holdout`
   + `signal/holdout.txt` (derive) ; refuse un held-out qui intersecte les cas cites ou `attendu_par_cas`.

**Generator + Evaluator — selon le fork**

Branche **FACTUELLE** (`references/signal-factuel.md`) :
7f. `python scripts/build_matrix.py` (matrice regle×cas, `attendu_par_cas` derive par introspection,
    NOT_FOUND hors denominateur) + `python scripts/detector_log.py` (anti-silence : detecte/non_detecte + pourquoi).
8f. `python scripts/build_contract.py` -> `auto_improver_call.json` (held-out EXCLU des test_cases, **0 patch code**).

Branche **JUGEMENT** (`references/signal-jugement.md`, `agents/juge-par-grille.md`) :
7j. `python scripts/run_grid.py` (6 criteres 0-2, N>=3 rejeux, seed loge, INDECIS si |delta|<=bruit,
    lint anti-PII). Remede : **reduire** les regles en principe scope + exemples contrastes ❌→✅.
8j. `python scripts/correlate_taste.py` : Spearman juge↔gout sur >=8 cas -> `calibration.json`.
    ρ>=0.6 **bloquant pour la calibration** (non bloquant pour le run). Sinon signal **NON_ANCRE** -> HITL.

**Gate + rapport**
9. `python scripts/regression_gate.py` : `ship = delta_net_holdout>=0 & regression_suite==1.0`.
   Sinon **refus** + anti-pattern nomme (`whack_a_mole`) + **error-analysis** (lire les traces des
   cas regresses, pas que le score). Rapport final : fork, comptes, held-out, delta+significativite,
   anti-patterns, delegation, budget tokens.

**Chaine complete** : `python scripts/run_pipeline.py` (mode degrade si corpus hors-repo, `degraded=true`).

## Frontieres ecosysteme (ne pas reimplementer)
- Patch factuel / boucle fermee -> **`skill-auto-improver-v2`** (ce skill produit son contrat d'entree).
- Creer un skill neuf -> **`skill-creator-v12`**. Deployer / re-upload -> **`deploy-skill-edite`**.
- Revue a froid (2 lentilles, axes 1-8 + frontiere) -> **`skill-reviewer-v2`**.
- Orchestration de la passe complete (held-out + validation utilisateur) -> **`amelioration_continue`**.
  Ce skill en est le CERVEAU, pas la porte d'entree : on l'appelle via l'orchestrateur, on ne
  l'invoque pas directement pour lancer une passe.

## Verification (avant de rendre)
`python scripts/self_diagnosis.py` (complétude, coherence held-out, meta_holdout non lu) doit passer.
`python scripts/run_meta_golden.py` (capability + regression) reste vert. Une iteration n'est « done »
que si elle produit un split held-out documente, un signal rejouable, des corrections routees, et un
delta net mesure sur held-out — et refuse tout changement qui regresse le net.

## Limites assumees
Ne nettoie pas un corpus (pre-requis). Ne juge pas a la place de l'humain (instrumente + propose).
A 2 cas-graines, le meta-golden-set est une non-regression binaire (mesure fiable a n>=5).
