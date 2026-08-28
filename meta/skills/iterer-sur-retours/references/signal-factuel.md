# signal-factuel.md — matrice règle × cas (branche factuelle)

> Signal du régime **factuel**. Implémentation : `build_matrix.py` + `detector_log.py`.
> Sur du factuel on **ajoute** des garde-fous déterministes (remède inverse du jugement).

## Matrice règle × cas

| Statut cellule | Sens | Dénominateur |
|---|---|---|
| `applique` (MATCH) | règle respectée sur ce cas | compte |
| `regresse` (FAIL) | règle violée | compte |
| `NA_justifie` | non applicable (justifié) | exclu |
| `NOT_FOUND` | détecteur non déclenché (colonne cible absente) | **exclu** (rendu visible) |

`NOT_FOUND` hors dénominateur : une feature famille B qui ne se déclenche pas ne compte ni
comme succès ni comme échec — mais elle est **loggée** (anti-silence).

## `attendu_par_cas` dérivé, jamais deviné (patch SIM-008)

`introspect_columns(case_id)` lit les colonnes réelles du dataset (entête csv/xlsx). Pour une
règle B de détecteur `<regex>` :
- une colonne matche `<regex>` → `fire` ;
- aucune → `no_fire` (→ `NOT_FOUND` dans la matrice) ;
- colonnes indisponibles (dataset non monté) → `a_valider_humain` (loggé, **non bloquant**).

Exemple tableur (`bins_duree`, détecteur `duration|duree`) :
`C21`→fire (`duree`), `C32`→fire (`duration`), `C67`/`C75`
→no_fire (colonne absente) = **non-application silencieuse rendue visible**.

## Garde-fou anti-silence — `detector_log.json`

Par règle B × cas : `detecte | non_detecte | indetermine` + **pourquoi** (quelle colonne,
présente/absente). C'est le contournement prouvé de LM2 (le LLM ne voit pas seul qu'un
détecteur ne rend rien).

## Frontière (rappel dur)

`build_matrix` / `detector_log` **MESURENT**. Le patch code est **produit comme contrat**
(`build_contract.py` → `auto_improver_call.json`), jamais écrit ici. Held-out **exclu** des
`test_cases` du contrat (invariant anti-contournement).
