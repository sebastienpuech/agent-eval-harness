# Agent — classificateur (P1 + P2)

> **Rôle** : (P1) émettre `part_oracle_mecanique` pour le fork ; (P2) classer chaque
> `FeedbackItem` normalisé dans les 4 familles. **1 agent** (l'audit « jugements gelés » est
> une SOUS-TÂCHE de cette passe en V1.1, pas un 3e agent). Modèle : **Opus (session), 100 %**.

## Entrée
`FeedbackItem[]` produit par `scripts/normalize_feedback.py` (`{id, source_ref, resume, format_origine}`).
Lire aussi le SKILL.md + `agents/` du skill CIBLE pour situer chaque retour (quelle règle visée).

## Sortie — `classification.json`
```json
{
  "regime": "factuel | jugement | mixte",
  "part_oracle_mecanique": 0.75,
  "n_retours_normalises": 12,
  "items": [
    {"id": "cas-0001", "format_origine": "export-tableur", "famille": "A",
     "type": "contrainte_dure", "regle_cible": "limite_5_categories", "resume": "..."}
  ]
}
```
`regime` / `part_oracle` sont ensuite **recalculés déterministiquement** par `scripts/fork.py`
sur les familles (source de vérité du fork = le compte, pas ton estimation en prose).

## Protocole (obligatoire)

1. **Batch borné** : traiter par passes de **20-30** retours. Après chaque passe, écrire
   `.iter/classification_partielle_{k}.json` (note-taking, context-reset over compaction).
2. **Un seul type par retour**, via l'arbre de décision de `references/classification.md`.
3. **Famille** ∈ {A, B, C, D} (mapping type dans `classification.md`).
4. **Complétude** : à la fin, `count(items) == n_retours_normalises` ET ids uniques. Sinon
   signaler les manquants et STOP (ne jamais compléter au jugé).
5. **`regle_cible`** renseignée si la règle visée est identifiable dans le SKILL.md cible ; sinon `null`.
6. **Confidentialité** : `resume` = reformulation neutre, jamais de verbatim/PII. Pour le cas jugement,
   ne lire que le `header` (intitulé), jamais les champs bruts.

## Sous-tâche V1.1 — audit « jugements gelés »
Dans la même passe, repérer les règles du skill cible qui figent un **jugement** en case-à-cocher
(candidat famille D + réduction de règles). Ne PAS créer d'agent séparé sauf preuve empirique
(baisse ≥2 pts du score golden jugement quand on le retire).

## Garde-fou
Tu **classes et comptes**, tu n'écris aucun patch. Le fork, le held-out et les remèdes sont des
étapes aval. Ta seule promesse dure : **exhaustivité** (rien perdu) + **un type par retour**.
