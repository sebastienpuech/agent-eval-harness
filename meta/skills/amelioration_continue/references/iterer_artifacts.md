# Réconciliation des artefacts iterer ↔ run_chain (spec du build `ItererBrain`)

> Établi le 2026-07-09 en **lançant réellement** `iterer/scripts/run_pipeline.py` et en inspectant
> son `.iter/`. Échantillon structurel figé dans `evals/fixtures/iterer_real_sample/` (tableur, 0 PII).
> But : rendre le build d'`ItererBrain` (le seul maillon manquant de la capability live) **borné**.

## Ce qu'iterer produit VRAIMENT (`.iter/`)
`classification.json · auto_improver_call.json · generated_evals.json · grid_scores.json ·
grid_regression_report.json · regression_report.json · detector_log.json · attendu_derive.json ·
matrix.csv · calibration.json · collected/<skill>_NN.json (+ _manifest_<skill>.json) · rapport.md`

## Écarts vs ce que `run_chain._branch_prose` lit aujourd'hui

| `run_chain` lit | iterer réel | Action `ItererBrain` |
|---|---|---|
| `classification.json` items `type_itere` | items `{id, famille, type, regle_cible}` — champ **`type`** | ✅ **corrigé** : `route()` lit `type` (test `test_route_sur_vraie_classification_iterer`) |
| `auto_improver_call.json` | **identique** (skill_path, evals_file, test_case_ids, holdout_case_ids, regles_a_detecteur, max_iter, delegation_status) | rien |
| `generated_evals.json` = `{cases:{cid:{input, source_session_id}}}` | `{_note, critical_checks:[{id, case, check}]}` — **shape différente**, pas d'`input`/`source_session_id` | ⚠️ **trouver la vraie source des inputs de cas** : probablement `<skill_path>/evals` (cas cibles) + `collected/_manifest_<skill>.json` (session_id d'origine). À verrouiller sur un run **demo-revue** réel. |
| `rates.json` = `{rates:[…]}` | **absent** — les ratés bruts sont dans `collected/<skill>_NN.json` | dériver `rates` depuis `collected/` (résumés, allowlist PII) |
| `diagnosis.json` | **absent** — iterer ne diagnostique pas (c'est le rôle du diagnosticien du muscle) | 2 choix : (a) **ne pas injecter** `diagnosis` → laisser le muscle diagnostiquer (retouche B rend `diagnosis` optionnel — déjà supporté) ; (b) synthétiser depuis `regles_a_detecteur` du contrat. **Défaut recommandé : (a)** pour la branche prose factuelle. |
| `held_out/*.json` avec `avant`/`apres` figés | `holdout_case_ids` (ids) + `regression_report.json` déjà calculé (sur le **détecteur**, pas sur la prose du muscle) | la mesure held-out de la **prose** exige de faire tourner le **candidat (skill) en live** sur les inputs held-out + détecteur → `holdout_scorer` mode **live** (LLM, budgété). C'est la dernière pièce non-déterministe. |

## Conséquence : plan de build `ItererBrain` (borné)
1. `ItererBrain.run(skill)` : `subprocess` `run_pipeline.py` (ou l'entrée collect→fork→contract pour un skill donné) `cwd=ITERER_PATH` → retourne `<ITERER_PATH>/.iter`.
2. **Adaptateur de lecture** `iterer_adapter.py` : normalise les artefacts réels →
   - `route()` : ✅ déjà OK (`type`).
   - `rates` ← `collected/<skill>_*.json` (résumés, jamais de verbatim).
   - `diagnosis` ← **None** (le muscle diagnostique ; retouche B l'autorise déjà).
   - `case_inputs`/`source_sessions` ← **à verrouiller** : mapper `test_case_ids` → inputs réels (source à confirmer sur un run demo-revue) + `source_session_id` via les manifests.
3. `holdout_scorer` mode **live** : faire tourner le candidat sur les held-out (LLM budgété) → `{avant,apres}`.
4. `ItererBrain.run_grid` (jugement) : lire `grid_regression_report.json` d'iterer (déjà produit).

## Le seul vrai inconnu restant
La **source exacte des `input`/`source_session_id` des test_case_ids** (le `generated_evals.json` réel ne les porte pas sous la forme attendue). Se résout en **1 run iterer sur demo-revue** (pas tableur) : on regarde d'où viennent `C21`-like pour jugement et on fige le mapping. Tout le reste ci-dessus est déterministe et codable sans deviner.
