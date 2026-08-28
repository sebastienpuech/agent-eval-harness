# Routage E2 — règles déterministes (lit `classification.json`, ne re-classifie JAMAIS)

Le routage est **par retour** (pas par skill) : un skill de jugement peut contenir un retour
`regle_detecteur` (S1 doublon) qui, lui, part en factuel-prose. La chaîne LIT la classification
produite par iterer ; elle ne re-juge rien (spec principe 1).

## Mapping retour → remède (V1)

| `type_itere` (iterer) | famille | remède V1 | exécuteur |
|---|---|---|---|
| `jugement` | D | `jugement_iterer` | patch iterer (run_grid) — **muscle ∅** |
| `regle_detecteur` | A/B | `prose_muscle` | bridge → muscle.run_pass |
| `contrainte_dure` | A/B | `prose_muscle` | bridge → muscle (le muscle rédige la règle) |
| `bloque_input_externe` | C | `mis_de_cote` | — |

**Frontière méca/prose (SIM-001)** : un remède qui exige de RÉDIGER une règle + un exemple contrasté
n'est pas mécanique → `prose_muscle`. La branche factuel-**mécanique** est reportée en **V1.1** et
n'a donc **aucun applicateur dans le repo** (rien à chercher dans `lib/`) : en V1 un retour purement
mécanique est routé `prose_muscle` ou `mis_de_cote`. Elle sera écrite quand un vrai cas l'exigera.

## Branche dominante de la passe (V1 = 1 branche/passe)

Priorité : **prose > jugement > rien-à-faire**.
- ≥ 1 retour `prose_muscle` → branche **prose** (S1) ;
- sinon ≥ 1 retour `jugement_iterer` → branche **jugement** (muscle ∅) ;
- sinon → **rien-à-faire** (silence, 0 message — S7).

Invariant (data_model RoutageItem) : `type_itere == jugement ⇒ remede == jugement_iterer` ;
un remède exigeant de rédiger ⇒ `prose_muscle` (jamais `mecanique` en V1).
