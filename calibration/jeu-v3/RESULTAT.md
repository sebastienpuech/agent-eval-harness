# Étalonnage du juge sur le jeu v3 — accord humain ↔ juge : kappa +0.27 [+0.05 ; +0.49]

> Calculé le 2026-09-23 par `calculer_accord.py --jeu jeu-v3`. 40 paires, un seul annotateur humain. Kappa de Cohen sur trois classes (A / B / les deux se valent), intervalle de confiance à 95 % par bootstrap (10000 tirages, graine 12345). Le CADRE dit : sous 0,4 la grille est ambiguë, au-dessus de 0,6 acceptable — et **on publie le chiffre quel qu'il soit**.

## En une ligne

- **Humain ↔ juge (LE chiffre)** : kappa **+0.27 [+0.05 ; +0.49]**, accord brut sur les paires tranchées par les deux 19/22 (86%), accord sur trois classes 52% [38% ; 68%].
- **Humain ↔ modèle nu (baseline b)** : kappa +0.31 [+0.08 ; +0.54], brut 24/32 (75%), trois classes 60% [45% ; 75%].
- **Juge ↔ vérité-terrain du concepteur** : kappa +0.46 [+0.29 ; +0.63], brut 26/28 (93%).
- **Juge ↔ modèle nu** : kappa +0.41 [+0.24 ; +0.59], brut 25/28 (89%).
- Les taux « brut » ci-dessus ont des dénominateurs différents (chaque notateur choisit les paires qu'il tranche) : ils ne se comparent pas entre eux, seuls les kappas se comparent.
- Bruit intra-juge (baseline a) : 0.20 point sur 12 en moyenne par réponse, 51/80 réponses à bruit nul. « Égales » : humain 8, juge 12, modèle nu 0 (sur 40).

## Les mesures — net / fin et par domaine

Lecture : kappa [IC95] · brut = accords / paires tranchées par les deux · 3 cl. = accord en comptant « égales » comme une classe. Sous-ensembles de 13 ou 14 paires : l'intervalle y est très large, c'est indicatif. **Les taux « brut » ne se comparent pas d'une ligne à l'autre** : leurs dénominateurs diffèrent (le juge s'abstient sur 12 paires, le modèle nu sur 0), et le sous-ensemble est choisi par le notateur qu'on évalue. Seul le kappa, sur les 40 paires, se compare.

| Accord | tout (40) | net (13) | fin (27) | pro (13) | ONG (13) | course (14) |
|---|---|---|---|---|---|---|
| juge ↔ vérité-terrain du concepteur | +0.46 [+0.29 ; +0.63]<br>brut 26/28 (93%)<br>3 cl. 65% | +0.72 [+0.40 ; +1.00]<br>brut 11/11 (100%)<br>3 cl. 85% | +0.35 [+0.15 ; +0.56]<br>brut 15/17 (88%)<br>3 cl. 56% | +0.22 [+0.00 ; +0.52]<br>brut 6/8 (75%)<br>3 cl. 46% | +0.72 [+0.39 ; +1.00]<br>brut 11/11 (100%)<br>3 cl. 85% | +0.48 [+0.20 ; +0.75]<br>brut 9/9 (100%)<br>3 cl. 64% |
| humain ↔ juge — LE CHIFFRE | +0.27 [+0.05 ; +0.49]<br>brut 19/22 (86%)<br>3 cl. 52% | +0.58 [+0.14 ; +1.00]<br>brut 10/11 (91%)<br>3 cl. 77% | +0.11 [-0.17 ; +0.39]<br>brut 9/11 (82%)<br>3 cl. 41% | +0.18 [-0.23 ; +0.56]<br>brut 4/4 (100%)<br>3 cl. 46% | +0.39 [+0.09 ; +0.73]<br>brut 8/10 (80%)<br>3 cl. 62% | +0.25 [-0.12 ; +0.60]<br>brut 7/8 (88%)<br>3 cl. 50% |
| humain ↔ modèle nu | +0.31 [+0.08 ; +0.54]<br>brut 24/32 (75%)<br>3 cl. 60% | +0.68 [+0.16 ; +1.00]<br>brut 11/13 (85%)<br>3 cl. 85% | +0.18 [-0.07 ; +0.43]<br>brut 13/19 (68%)<br>3 cl. 48% | +0.02 [-0.18 ; +0.21]<br>brut 5/7 (71%)<br>3 cl. 38% | +0.46 [+0.13 ; +0.85]<br>brut 9/12 (75%)<br>3 cl. 69% | +0.47 [+0.09 ; +0.86]<br>brut 10/13 (77%)<br>3 cl. 71% |
| juge ↔ modèle nu | +0.41 [+0.24 ; +0.59]<br>brut 25/28 (89%)<br>3 cl. 62% | +0.72 [+0.40 ; +1.00]<br>brut 11/11 (100%)<br>3 cl. 85% | +0.29 [+0.11 ; +0.50]<br>brut 14/17 (82%)<br>3 cl. 52% | +0.11 [-0.05 ; +0.38]<br>brut 5/8 (62%)<br>3 cl. 38% | +0.72 [+0.39 ; +1.00]<br>brut 11/11 (100%)<br>3 cl. 85% | +0.47 [+0.21 ; +0.75]<br>brut 9/9 (100%)<br>3 cl. 64% |
| humain ↔ vérité-terrain (rappel, déjà connu) | +0.28 [+0.05 ; +0.51]<br>brut 23/32 (72%)<br>3 cl. 57% | +0.68 [+0.16 ; +1.00]<br>brut 11/13 (85%)<br>3 cl. 85% | +0.14 [-0.11 ; +0.39]<br>brut 12/19 (63%)<br>3 cl. 44% | +0.18 [-0.07 ; +0.47]<br>brut 6/7 (86%)<br>3 cl. 46% | +0.46 [+0.13 ; +0.85]<br>brut 9/12 (75%)<br>3 cl. 69% | +0.27 [-0.03 ; +0.62]<br>brut 8/13 (62%)<br>3 cl. 57% |

## Le modèle nu et la position

- Rejeux dans l'ordre A-B (80) : première choisie 28, seconde 51, égales 1. Rejeu inversé B-A (40) : première 21, seconde 19, égales 0.
- Paires aux trois votes unanimes (donc stables sous l'inversion, c'est la même quantité avec un seul rejeu inversé sur trois) : 34/40.

## Ce que la mesure a trouvé en route (à documenter, pas à corriger)

- **La grille sature sur ce jeu.** 45/80 réponses reçoivent 12/12 en moyenne ; dans 10/40 paires les deux réponses sont à 12, et 10 des 12 « égales » du juge viennent de là. Les deux réponses de chaque paire ont été écrites pour être envoyables : une grille qui note une qualité absolue ne sépare pas deux bonnes réponses. La saturation est mesurée ; qu'elle soit la cause principale est une inférence, et elle n'explique qu'une partie : sans les 10 paires au plafond, le kappa humain ↔ juge passe de +0.27 à +0.39 (30 paires ; sur les fines, +0.25), toujours sous 0,6.
- **Le modèle nu tranche toujours** (0 égales sur 40). Son kappa avec l'humain dépasse celui de la grille de +0.04, mais l'écart apparié (mêmes 40 paires, mêmes tirages) a pour IC95 [-0.17 ; +0.25] et P(nu > juge) = 0.65 : **on ne voit pas la grille faire mieux que le modèle nu, et on ne peut pas non plus dire qu'elle fait moins bien.** Ce qui est établi, c'est qu'elle s'abstient là où lui tranche.
- **Position, modèle nu** : B est choisie 64% du temps quand elle est montrée en second (80 rejeux), 52% quand elle est montrée en premier (40 rejeux). Écart non distinguable de zéro à cette taille (z ≈ 1,2, rejeux groupés par paire) ; le dispositif le mesurerait s'il était grand, il ne l'est pas.

## Les trois vérités-terrain contestées (P-06, C-05, C-07)

| paire | concepteur | humain | juge | modèle nu |
|---|---|---|---|---|
| C-05 | A | B | egales | B |
| C-07 | A | B | egales | B |
| P-06 | A | A | A | B |

## Protocole exact

- Jeu : `jeu-v3/paires.json (40 paires, seed_cotes 20260922)`, écrit par une session Claude (Fable 5.1) avec l'auteur du dépôt, validé par quatre relecteurs indépendants qui sont des sous-agents Claude Opus 5 en contexte frais (`validation.md`). Les étiquettes net / fin ont été posées par le premier relecteur sur la version v3a, puis confirmées 13/13 et 12/13 par les deux suivants sur v3b.
- Annotation humaine : `annotations/comparaison-20260924.csv (1 annotateur, ordre seed 20260924)`. **L'annotateur est l'auteur du dépôt** ; il n'a pas écrit la vérité-terrain (elle vient de la session de conception) et n'a jamais vu une note du juge. Le nombre 20260924 est la graine de l'ordre d'affichage, pas une date : l'annotation est du 22/09/2026 (commit `c445db5` du dépôt privé), la notation machine du 23/09/2026.
- Juge `juge-par-grille` (6 critères 0-2) : modèle `claude-opus-4-8` (celui du harnais publié, `llm_client.DEFAULT_MODEL`), N = 3 rejeux par réponse, 80 réponses, 240 appels, du 2026-09-23 au 2026-09-23. Le juge n'a reçu que la situation et la réponse notée. Préférence par paire : |total_A - total_B| <= max(bruit_A, bruit_B) -> egales (ecrite avant la mesure).
- Seed : `20260706` est la seed nominale du harnais, loguée pour la traçabilité ; **l'appel par l'Agent SDK n'expose ni température ni seed**, donc elle ne fige rien — le non-déterminisme réel est ce que mesure le bruit intra-juge.
- Juge et modèle nu ont tourné en même temps (juge 2026-09-23 07:51 → 08:32 UTC, nu 07:58 → 08:34 UTC) : aucun des deux ne lit les sorties de l'autre, l'ordre n'a pas d'importance.
- Modèle nu : même modèle `claude-opus-4-8`, sans grille ni sentinelles, consigne système « Tu lis une situation et deux reponses possibles. On te pose une question de choix. Reponds par un seul mot, sans rien d'autre : PREMIERE, SECONDE ou EGALES. », question « Laquelle enverrais-tu, toi, dans cette situation ? », N = 3 rejeux par paire dont le rejeu [2] avec l'ordre d'affichage inversé, 40 paires, 120 appels, du 2026-09-23 au 2026-09-23. Préférence : majorite des 3 votes ; 'egales' si les trois different.
- Bootstrap : 10000 tirages avec remise sur les paires, graine 12345 ; percentiles 2,5 et 97,5 du kappa recalculé à chaque tirage.
- Règles d'« égales » et de préférence écrites avant de voir un résultat. **Depuis le début de l'annotation humaine**, rien n'a été retouché : ni le jeu, ni l'annotation, ni le modèle, ni les règles. Avant elle, le jeu a été réécrit deux fois pendant sa validation (`validation.md`), et une version a été refusée précisément parce qu'un chiffre (28/28) était trop bon.
- Seuils de lecture (0,4 ambiguë / 0,6 acceptable) : écrits dans le cadre de l'étalonnage le 28/08/2026 (commit `e6c2b7f` du dépôt privé), avant tout jeu et toute mesure. Le fichier n'est pas public ; la date l'est par ce hash.
- Bruit intra-juge = écart-type de population (ddof = 0) des 3 totaux, comme dans le harnais. Avec n = 3 il est biaisé vers le bas, donc le seuil d'« égales » est plutôt serré ; sur ces données, 11 des 12 égales du juge sont des égalités exactes, la règle n'a joué que sur P-11.

## Ce que le chiffre ne dit pas

- **Un seul annotateur humain.** Le chiffre dit « le juge préfère comme cet humain », pas « comme les humains ». Un désaccord peut venir du juge, de la grille, ou de l'annotateur ; sans second annotateur on ne peut pas départager. Un kappa inter-annotateurs reste à faire.
- **Trois domaines de messages courts** (échanges pro, conduite de projet ONG, course à pied), réponses de 10 à 60 mots. Ce n'est pas de la revue de code, domaine du skill de démonstration du dépôt public : le chiffre ne se transporte pas tel quel.
- **Trois vérités-terrain contestées** (P-06, C-05, C-07) par deux relecteurs sur deux : la colonne « juge ↔ vérité-terrain » porte une opinion de conception sur ces trois paires, pas une mesure. Le tableau ci-dessus les isole.
- **Une règle mécanique résiduelle** vue par les relecteurs (`validation.md`) : « prends celle qui s'engage sur un acte daté » prédit une partie des vérités-terrain, surtout les 13 nettes. Si juge et humain suivent tous deux cette règle, l'accord monte sans prouver un jugement situé. La colonne « fin (27) » est celle qui en dépend le moins.
- **40 paires** : l'intervalle est large par construction. Les sous-ensembles (13-14 paires) ne tranchent rien seuls.
- **Le taux brut 19/22 n'est pas un score.** Il porte sur les paires que le juge a bien voulu trancher ; le juge choisit lui-même son dénominateur. Le kappa sur 40 est le chiffre.
- **Les justifications du juge sont des gabarits**, pas du texte libre : trois formules canoniques produites par l'agrégateur du harnais à partir des scores. Elles garantissent l'absence de verbatim, elles n'expliquent rien.
- **Deux chiffres de `validation.md` ne se recoupent pas** : « 12/12 · 28/28 » pour le premier relecteur sur v3a a des dénominateurs (12, 28) qui ne correspondent pas à la répartition 13 / 27, et la même passe de réécriture y est comptée « 27 paires fines réécrites » à un endroit et « 12 paires réécrites » à un autre (la liste nominative donne 12 réécritures de fond). La version v3a n'est pas conservée. C'est un document d'historique de la session de conception ; il est laissé tel quel et signalé ici.
- **La seed ne fige rien** (voir protocole) : deux relances de ce script sur de nouvelles notations donneraient des totaux différents, dans la marge du bruit publié.

Détail paire par paire : `resultat.json` (clé `detail`).
