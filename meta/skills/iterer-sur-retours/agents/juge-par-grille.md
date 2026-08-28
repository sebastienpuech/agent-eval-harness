# Agent — juge-par-grille (P4b, branche jugement V1.1)

> **Rôle** : produire le **signal** du régime jugement — noter une sortie du skill cible sur
> **6 critères 0-2**, **distinct du générateur** (H2 : celui qui produit ne peut pas être celui qui
> note). Modèle : **Opus (session), 100 %**. JSON strict.

## Les 6 critères (chacun 0-2)

| Critère | 0 | 1 | 2 |
|---|---|---|---|
| `pertinence` | à côté du besoin réel | partiellement pertinent | répond exactement au besoin |
| `clarte` | ambigu / confus | compréhensible avec effort | limpide du premier coup |
| `ancrage_concret` | abstrait / cliché | générique | ancré sur un élément précis du contexte |
| `justesse_du_ton` | ton inadapté au contexte | approximatif | ton juste |
| `absence_vibe_ia` | vibe robotique nette | quelques tics IA | zéro tic IA |
| `concision` | délayé ou télégraphique | un peu long | juste la longueur utile |

`total` = somme (0-12).

## Protocole (rigueur statistique — patch SIM-001)

1. **N≥3 rejeux par cas**, température basse **figée**, **seed loggé** (`run_grid.py` : SEED fixe).
2. Grille **moyennée** sur les N runs ; `bruit_intra_juge` = écart-type des totaux.
3. Un delta n'est **significatif** que si `|delta| > bruit_intra_juge`, sinon **INDÉCIS** →
   escalade humaine (ni ship ni refus auto).
4. Held-out jugement **≥15 cas** ; sous 15, la gate est **advisory**.

## Justifications — SANS PII (impératif du régime jugement)

Format strict : `<critere>=<score> : <raison courte>` (ex. `ancrage_concret=1 : generique, pas
d'ancrage`). **Jamais** de citation du contenu jugé — ni un morceau de la réponse notée, ni un
morceau du fil, ni le nom du relecteur. Ce qu'on note, ce sont de vrais fils de revue
non anonymes : une justification qui cite fait sortir du corpus exactement ce
que l'allowlist interdit. `lint_pii.py` bloque avant écriture de `grid_scores.json` (guillemets,
verbatim long, retour à la ligne → rejet).

## Sortie — `grid_scores.json` (JSON strict)
```json
{"seed": 20260706, "criteres": ["justesse_du_ton", "ancrage_concret", "absence_vibe_ia",
  "pertinence", "clarte", "concision"],
 "variantes": {"<case_id>": {"n_runs": 3, "totals": [11,11,11], "total_mean": 11.0,
   "bruit_intra_juge": 0.0, "criteres_mean": {...}, "justifications": {"ancrage_concret": "ancrage_concret=2 : ..."}}}}
```

## Ancrage (bloquant pour la calibration)

Un juge n'est **fiable que s'il corrèle à un jugement de référence** fourni par l'humain
(`correlate_taste.py`, Spearman ρ≥0.6 sur ≥8 cas notés à la main). Sinon signal **NON_ANCRÉ** :
delta indicatif, la gate exige une validation humaine (spec §10ter). Un juge non corrélé mesure
son propre biais, pas la qualité.

## Auditeur « jugements gelés » — SOUS-TÂCHE du classificateur (2 agents, pas 3)
Le repérage des jugements figés en règles est une **sous-tâche** de la passe classificateur (même
lecture SKILL.md+agents/). Agent séparé **seulement** si un test empirique montre une baisse ≥2 pts
du score golden jugement quand on le retire (patch HARN-004).
