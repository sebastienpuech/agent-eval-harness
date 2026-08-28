# evals/meta_holdout/ — digue anti-gaming (patch HARN-003)

> **Invariant dur** : `case ∈ meta_holdout ⇒ JAMAIS lu par le moteur d'auto-amélioration`
> (`skill-auto-improver-v2` ni aucune passe de patch). Chargé **uniquement** par la suite
> *regression* du méta-golden-set, pour vérifier qu'un patch qui monte le score capability
> ne triche pas en overfittant les cas connus.

## Pourquoi

Le méta-golden-set (`../expected.json`) mesure `iterer-sur-retours` lui-même. Si la boucle
d'auto-amélioration (§11, **désarmée en V1**) pouvait lire *tous* les cas, elle pourrait se
régler dessus. Ce couple réservé reste **hors de sa vue** : il ne prouve rien s'il est lu.

## Contenu

- `reserved_couple.json` — un couple `(skill cible + lot de retours)` distinct de tableur/jugement
  (les 2 cas capability), réservé à la mesure seule.

## Enforcement (exécutable)

`scripts/self_diagnosis.py` échoue si :
1. `meta_holdout/` est **vide** ;
2. un fichier de `meta_holdout/` apparaît dans `memory/engine_access.log` (le moteur y a touché).

Le moteur DOIT journaliser tout accès fichier dans `memory/engine_access.log` (une ligne par
accès). Absence de log = aucun accès = invariant respecté (V1 : le moteur ne tourne pas encore).

## Statut V1

Boucle §11 **désarmée** (n_seed_cases < 5). Le slot est réservé et l'invariant d'accès est
déjà appliqué par `self_diagnosis.py`. Le corpus de retours réel sera attaché quand la boucle
s'armera (n≥5 dont ≥1 méta-held-out réel).
