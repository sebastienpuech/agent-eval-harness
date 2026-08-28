# failure_signals.md — lexique des signaux d'échec (FR/EN)

> Utilisé par `lib/extractor.py` pour détecter, dans un transcript, qu'une proposition du skill
> a raté. Détection sur les **messages `role=user` uniquement** (le rejet vient de l'humain).
> Un transcript ayant ≥1 signal = 1 `Raté` (un seul, avec le signal de plus haute priorité).
> Les patterns sont des regex insensibles à la casse. **Aucun texte brut n'est persisté** : le
> résumé est un template par signal (cf. extractor), jamais une citation.

## Priorité (du plus informatif au moins informatif)

1. `reformulation_manuelle`
2. `refais`
3. `bof_explicite`
4. `abandon`
5. `tag_rejete`

## Signaux

### `reformulation_manuelle` — l'utilisateur réécrit lui-même la proposition
Le signal le plus fort : la proposition était assez fausse pour qu'il la corrige à la main.
- FR : `je reformule`, `je (le )?réécris`, `je (le )?fais moi[- ]?même`, `je corrige moi`, `voilà ce que j'aurais mis`
- EN : `i'll rewrite`, `let me redo it myself`, `here's what i'd say instead`

### `refais` — rejet + demande d'une autre proposition
- FR : `\brefais\b`, `recommence`, `une autre (proposition|idée|version)`, `propose (moi )?autre chose`, `t'as autre chose`
- EN : `redo`, `try again`, `give me another`, `something else`

### `bof_explicite` — jugement négatif explicite
- FR : `\bbof\b`, `\bmoyen\b`, `(fait|c'est) (trop )?génériqu`, `(un peu|trop|ça fait) ia\b`, `pas terrible`
- EN : `meh`, `generic`, `sounds like ai`, `not great`

### `abandon` — l'utilisateur laisse tomber la piste
- FR : `laisse tomber`, `j'abandonne`, `tant pis`, `oublie (ça|ca)`
- EN : `never mind`, `forget it`, `giving up`

### `tag_rejete` — résultat taggé rejeté
Vient de `memory/verdicts.md` du skill cible (pas du transcript), rapproché par `run_id`. Au MVP,
`verdicts.md` du skill cible est vide → ce signal est inactif sur les fixtures.
- pattern (prod) : ligne `verdicts.md` avec `résultat = rejete`
