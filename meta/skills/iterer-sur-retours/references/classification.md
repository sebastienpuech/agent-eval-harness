# classification.md — 4 types de retour + arbre de décision

> Chaque `FeedbackItem` normalisé reçoit **une** famille/type. Traitement FIXE par type
> (spec §6.bis). La classification par-retour est **orthogonale** au fork (régime primaire).

## Les 4 types (famille ↔ type ↔ remède)

| Famille | `type` (data_model §1) | Oracle | Remède | Écrit par |
|---|---|---|---|---|
| **A** structurelle | `contrainte_dure` | mécanique | assertion / code | **auto-improver** (via contrat) |
| **B** détecteur | `regle_detecteur` | mécanique | garde-fou anti-silence (log détecté/non-détecté + `attendu_par_cas`) | **auto-improver** (via contrat) |
| **C** bloqué input | `bloque_input_externe` | — | **mis de côté** (Scénario 3), pas un défaut de règle | personne |
| **D** jugement | `jugement` | non | principe scopé (*pourquoi* + *quand/quand PAS*) + exemple contrasté | **ce skill** (seul patch qu'il écrit) |

> Rappel frontière : sur A/B le skill **produit le contrat** d'auto-improver, il n'écrit PAS
> le patch code. Sur D il écrit principe+exemple ET propose de **réduire** les règles.

## Arbre de décision (par retour)

```
Le retour dépend-il d'une donnée/input absent (spec de la CI, historique de runs, dataset non fourni) ?
 ├─ oui -> C bloque_input_externe (mis de côté, hors matrice & hors juge)
 └─ non :
     La bonne réponse est-elle vérifiable MÉCANIQUEMENT (présence/format/compte/regex) ?
      ├─ oui :
      │    S'applique-t-elle à TOUT output (universelle) ?
      │     ├─ oui -> A contrainte_dure (assertion)
      │     └─ non, conditionnée à une feature/colonne du cas -> B regle_detecteur
      │                                                          (garde-fou anti-silence)
      └─ non (goût, ton, pertinence, cohérence subjective) -> D jugement
```

## Complétude + batch (patch SIM-007 / HARN-006)

- Classification par **passes de 20-30 retours** ; note-taking `.iter/classification_partielle_{k}.json`
  (context-reset over compaction) ; résultats concaténés ; budget tokens affiché.
- **Assertion dure** : `count(items) == count(retours normalisés)` ET ids uniques. Sinon STOP.
- **Dédup** appliquée en amont par `normalize_feedback.py` (`(source_ref, resume)`).

## Garde-fou `attendu_par_cas` (famille B)

`attendu_par_cas` ne contient QUE des **cas de retour** (jamais du held-out — sinon on réglerait
dessus, cf. `split_holdout.py`). En Session 4 il est **dérivé par introspection** des colonnes
réelles (`fire` si la colonne cible existe, `no_fire` sinon), jamais deviné ; non-dérivable →
`a_valider_humain` (loggé, non bloquant).
