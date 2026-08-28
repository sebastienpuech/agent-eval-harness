# fork.md — régime par SEUIL (P1)

> Le fork fixe le régime **primaire** par seuil, pas par label libre (patch ARCH-004).
> Implémentation exécutable : `scripts/fork.py`.

## Signal

Le classificateur émet, par retour, une **famille** :

| Famille | Nature | Oracle mécanique ? |
|---|---|---|
| **A** structurelle | contrainte dure vérifiable | **oui** |
| **B** détecteur | règle-à-détecteur (feature conditionnelle) | **oui** |
| C bloqué input | dépend d'une donnée absente | non |
| D jugement narratif | goût / subjectif | non |

`part_oracle_mecanique = (n_A + n_B) / n_total` ∈ [0,1].

## Seuils

```
part_oracle >= 0.5  -> factuel   (matrice déterministe + garde-fou anti-silence + contrat auto-improver)
part_oracle <= 0.2  -> jugement  (juge-par-grille ancré + exemples contrastés + réduction de règles)
0.2 < part < 0.5    -> mixte     (régime primaire = dominant ; retours de l'autre nature -> sous-routine, PAS une nouvelle règle)
```

## Complétude (dur)

`n_total` DOIT égaler `n_retours_normalises` (sortie de `normalize_feedback.py`). Un retour
perdu fausse le fork → `fork.py` lève et STOP.

## Exemple résolu — garde-fou du cas-graine tableur

Fixture `evals/fixtures/tableur_classified.json` (synthétique, non sensible) : majorité A/B →
`part_oracle = 0.75` ≥ 0.5 → **factuel**. Assertion golden (`fork.py --golden`) :
`regime == factuel` ET `part_oracle >= 0.5` ET `A>=5, B>=1, C>=1` (types_attendus `expected.json`).

Cas jugement (fixture) : majorité D → `part_oracle = 0.083` ≤ 0.2 → **jugement**.

> Ces fixtures ne sont PAS le corpus réel (hors-repo / PII). Elles gèlent l'attendu du fork
> pour que le cas-graine reste vérifiable sans monter le corpus.
