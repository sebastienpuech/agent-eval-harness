# signal-jugement.md — remède INVERSE (branche jugement)

> Sur du jugement, ajouter des règles-détecteurs **coûte** de la cohérence (LM3). Remède
> **opposé** au factuel : **−règles, +exemples**. Implémentation : `run_grid.py` +
> `correlate_taste.py` + `lint_pii.py`. Signal = `juge-par-grille.md`.

## Principe scopé, pas règle isolée

Reconvertir un jugement figé en **principe** : *pourquoi* + *quand / quand PAS* + **exemple
contrasté** ❌→✅. Puis **proposer la réduction** de la pile de règles — en gardant les asserts
**déterministes** du skill cible (typiquement `char_check`, `max_questions`, `longueur_max` : tout
ce qui se vérifie sans jugement). La réduction ne touche qu'aux règles qui prétendent arbitrer du
goût ; ce qui se mesure reste.

## Exemples contrastés (patron)

Illustrations sur le cas de démo : un skill qui **rédige des reponses courtes dans un fil de revue**
(registre technique). Le patron vaut pour tout skill de jugement :

| Règle isolée (❌ fragmente) | Principe + exemple (✅ cohérent) |
|---|---|
| « Toujours finir une réponse par une question » | *Poser une question SEULEMENT si elle relance vraiment ; jamais trois d'affilée.* ❌ `Ça te va ? Tu veux que je change ? Je pousse ?` → ✅ une remarque ancrée sur ce qu'il vient de dire + une seule question qui ouvre |
| « Reprendre un mot du commentaire dans chaque réponse » | *Reprendre SI le mot porte le sens ; sinon rebondir sur l'idée.* ❌ `Ah, le cache.` (paraphrase du commentaire) → ✅ `Invalider au write plutôt qu'au read, ça déplace le coût mais ça le borne.` |
| « Réponse courte » | *Court n'est pas juste : la longueur suit celle du commentaire.* ❌ `Cool !` en réponse à un commentaire qui argumente un choix → ✅ une réponse qui prend le temps de répondre à l'argument |

## Cas discriminants (spec §12bis) — prouvent LM1/LM3

- **6a (LM3)** : `grid(cohérente) − grid(fragmentée) ≥ 3` — la grille sépare une sortie
  holistique d'une sortie fragmentée par empilement de règles. *(prouvé : gap = 4)*
- **6b (LM1)** : un fix qui régresse un held-out jugement → gate **refuse** (`ship=false`) +
  **sur-généralisation nommée** (comme S4). *(prouvé)*

## Auditeur « jugements gelés »
Sous-tâche du classificateur (2 agents en V1, pas 3) : repère les règles du skill cible qui
figent un jugement en case-à-cocher → candidates à la **réduction**.

## Confidentialité
`grid_scores.json` : justif = `critere+score`, **jamais** de verbatim (lint `lint_pii.py`,
bloquant). Le corpus est lu en JIT, jamais recopié.
