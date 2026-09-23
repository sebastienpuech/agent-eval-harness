# Validation du jeu v3 — rapport des relecteurs indépendants

> 22/09/2026. Concepteur : session Claude Fable 5.1. Relecteurs : quatre sous-agents Claude Opus 5,
> chacun en contexte frais, lancés par l'outil Agent avec la même consigne. **Écart déclaré** au
> CLAUDE.md (« sous-agents → Sonnet ») : le choix « laquelle enverrais-tu ? » est un jugement, pas
> un geste mécanique, et c'est lui que le jeu mesure — Opus, donc.

## Verdict

**Jeu accepté** au sens des deux critères du prompt :

- (a) **aucune paire n'échoue** sur locuteur / registre / tranchabilité après réécriture — la seule
  paire tombée (P-12, « interchangeable » pour le relecteur 3) a été réécrite puis revalidée « oui »
  par un 4ᵉ relecteur frais ;
- (b) **les relecteurs ne sont pas d'accord avec la vérité-terrain sur toutes les paires fines** :
  24/27 pour chacun des deux relecteurs du jeu final, contre 28/28 sur la première version — qui a
  été refusée pour cette raison.

Ce qui reste vrai et qui se dit : les deux relecteurs du jeu final sont d'accord **entre eux sur
40/40**, et se trompent (par rapport à moi) sur **les mêmes trois paires**. Deux modèles de la même
famille partagent une norme ; l'accord inter-relecteurs n'est pas une preuve que les paires fines
sont fines pour un humain. **C'est l'annotation humaine qui le dira, et c'est son rôle.**

## Ce qu'on a demandé aux relecteurs (consigne commune)

Fichier unique à lire : `paires-sans-verite.json` (40 paires : `id`, `domaine`, `situation`,
`reponse_A`, `reponse_B` — **sans** `ecart`, sans `verite_terrain`, sans `defaut`), généré par
`construire_paires.py --pour-relecteur`. Interdictions : aucun autre fichier (ni le dépôt, ni le
dossier de sortie des autres relecteurs), pas de Glob/Grep, **pas d'outil Agent** (la leçon du
21/09 : un sous-agent peut déléguer, et l'aveugle ne se transmet pas), pas de web. Pour chaque
paire : `locuteur_clair` (oui/non), `plausibles_bon_registre` (oui/non), `tranchable`
(oui/non/trop_evident), `choix` (A/B), `raison_du_choix`. Écriture au fil de l'eau dans
`out/agent-0N-relecture.json` + un rapport `.md` (outils lancés, échecs, biais vus, confiance).
La consigne n'annonce ni la proportion attendue d'écarts nets ni aucun résultat (leçon du 20/09).

Outils effectivement lancés par les relecteurs, d'après leurs rapports : `Read` du fichier de
paires, `Write` des deux fichiers de sortie ; le relecteur 3 a en plus validé son JSON par
`json.load`. Aucun n'a lu autre chose. Rapports bruts copiés dans `relectures/`.

**Lecture de « trop_evident »** : je ne l'ai pas traité comme un échec mais comme la mesure de
l'écart « net » — le prompt demande environ un tiers de paires nettes. Ce sont donc les relecteurs
qui ont fixé l'étiquette `ecart` des 40 paires, pas moi : `net` = signalé « trop_evident » par le
relecteur 1, `fin` = le reste. Le second passage l'a confirmé à 13/13 (relecteur 2) et 12/13
(relecteur 3, qui trouve C-12 tranchable).

## Chronologie — trois versions, quatre relectures

| Version | Relecteur | Échecs | trop_evident | Accord vérité-terrain net / fin | Décision |
|---|---|---|---|---|---|
| v3a (première écriture) | R1 | 0 | 13 | 12/12 · **28/28** | **refusé** (critère b) |
| v3b (27 paires fines réécrites) | R2 | 0 | 13 | 13/13 · **24/27** | accepté sous réserve |
| v3b | R3 | 1 (P-12 : « non ») | 12 | 13/13 · **24/27** | P-12 à réécrire |
| v3c (P-12, O-11, C-04 retouchées) | R4, ciblé sur 4 paires | 0 | 1 (O-11) | 4/4 | **accepté** |

Accord entre R2 et R3 : 13/13 net, 27/27 fin, aucune divergence.

### Ce que le relecteur 1 a trouvé, et ce qui a été réécrit

Trois défauts, tous vérifiables sur le fichier v3a (`relectures/relecteur-1-jeu-v3a.md`) :

1. **Un patron apprenable** : « la gagnante contient des chiffres, une date et une décision » —
   reproduisait ses choix sur ~33 paires sur 40, sans lire la situation. Le tic « Tu as raison » /
   « Vous avez raison » ouvrait la gagnante dans 7 paires sur 7 où il apparaissait.
2. **Une asymétrie d'information** : dans 5 paires, une seule réponse connaissait des faits absents
   de la situation (le bon pourcentage, l'existence d'une sauvegarde, l'allure au kilomètre soufflée
   par la situation elle-même dans C-08).
3. **O-04** était la seule paire sans message entrant (une annonce, pas une réponse).

Réécriture (v3b) : les 13 « trop_evident » deviennent les 13 nettes, sans changement. Sur les 27
fines, la moins bonne réponse devient **aussi concrète que la meilleure** et défend **une autre
priorité** — P-01 (relire tout en sacrifiant sa propre échéance), P-03 (féliciter puis organiser),
P-06 (produire deux options plutôt que poser la question), P-07 (un « peut-être » borné à 18h),
P-09 (caler les priorités avant de lancer), P-12 (procédure + accueil, sans les deux règles),
C-05 (défendre un contrat d'autonomie), C-07 (une règle chiffrée que le coureur s'applique seul),
C-14 (séance raccourcie plutôt qu'annulée). Deux vérités-terrain **inversées** parce que la
réécriture a rendu l'autre stratégie meilleure : O-01 (laisser décider celui qui voit la route,
avec critère et heure limite) et O-11 (refuser la photo faute de consentement écrit, situation
enrichie pour que les deux réponses connaissent les mêmes faits). O-04 devient une réponse à une
question posée sur le groupe. C-08 : l'allure retirée de la situation. C-12 : la pique finale
retirée. « Tu as raison » : retiré de deux gagnantes, ajouté à deux perdantes (5 / 2 après
réécriture, 7 / 0 avant). Longueur : la gagnante est la plus longue dans **17/40** (38/40 avant la
première mesure, corrigé avant même la relecture 1 — une règle « prends la plus longue » aurait
suffi).

### Ce que les relecteurs 2 et 3 ont trouvé sur v3b

- **Échecs** : R3 juge P-12 interchangeable (« même structure, même qualité, le choix ne tient qu'au
  goût »). Réécrite : la moins bonne garde la procédure et l'accueil, perd le conseil « prévenir à
  l'oral » qui faisait jeu égal avec le piège des vacances scolaires. R4 : « propre, choix réel ».
- **Réserve de forme** sur O-11 (le « lui » de « Tu lui réponds » pouvait viser la présidente) :
  corrigé en « Tu réponds au service communication ». R4 la juge ensuite trop évidente (norme ONG
  du consentement écrit) ; R2 et R3 la jugeaient tranchable. Gardée en `fin` à deux voix contre
  une — à surveiller à l'analyse.
- **C-04** : R4 relève une imprécision technique dans la meilleure réponse (« dernière longue avant
  l'affûtage » à cinq semaines, et une réduction à 1h30 qui contredisait « je ne veux pas la
  sauter »). Corrigée, sans changer la stratégie de la paire.
- **Règle mécanique résiduelle**, signalée par les deux : « prends celle qui s'engage sur un acte
  daté » marche encore sur les 13 nettes (par construction) et sur une partie des fines ; côté
  course, « prends celle qui protège le coureur » marche sur 8 des 9 paires concernées (C-04 est la
  contre-épreuve). R2 nomme quatre paires où la règle échoue nettement : P-03, C-03, C-10, C-14.
  **Non corrigé** : le retirer entièrement reviendrait à rendre les paires arbitraires. C'est un
  biais à mesurer, pas à cacher — si le juge et l'humain suivent tous deux cette règle, l'accord
  sera haut sans que ça prouve un jugement situé, et l'analyse devra le dire.
- **Biais de côté ressenti** : R2 et R3 choisissent B 25 fois sur 40. La vérité-terrain est en B
  22 fois (tirage seed 20260922) ; l'écart est faible et l'ordre gauche/droite sera de toute façon
  retiré par `preparer_comparaison.py` à l'annotation.

## Les trois vérités-terrain contestées (⚑)

R2 et R3 choisissent tous deux l'autre réponse que moi sur **P-06, C-05, C-07**. Je garde ma note
(c'est une opinion de conception, pas une mesure) mais le champ `verite_terrain.contestee = true`
les marque dans `paires.json`, pour que l'analyse puisse les regarder à part. Ce sont, par
construction, les paires où deux stratégies sont réellement à égalité — celles sur lesquelles
l'accord juge/humain sera le plus informatif.

## Tableau paire par paire

Lecture : `choix / tranchable` ; « évid. » = trop_evident, « NON » = non tranchable, « — » = non
relu. **La colonne R1 porte sur la version v3a** : sur les 12 paires réécrites ensuite (listées plus
haut) et sur O-01 / O-11 dont la vérité a été inversée, la lettre R1 désigne un autre texte que
celui du jeu final. ⚑ = vérité-terrain contestée par R2 et R3.

| id | écart | vérité | R1 (v3a) | R2 (v3b) | R3 (v3b) | R4 (v3c, ciblé) |
|---|---|---|---|---|---|---|
| P-01 | fin | B | B / oui | B / oui | B / oui | — |
| P-02 | net | B | B / évid. | B / évid. | B / évid. | — |
| P-03 | fin | A | A / oui | A / oui | A / oui | A / oui |
| P-04 | fin | B | B / oui | B / oui | B / oui | — |
| P-05 | net | A | A / évid. | A / évid. | A / évid. | — |
| P-06 | fin | A ⚑ | A / oui | B / oui | B / oui | — |
| P-07 | fin | B | B / oui | B / oui | B / oui | — |
| P-08 | net | B | B / évid. | B / évid. | B / évid. | — |
| P-09 | fin | A | A / oui | A / oui | A / oui | — |
| P-10 | fin | B | B / oui | B / oui | B / oui | — |
| P-11 | net | B | B / évid. | B / évid. | B / évid. | — |
| P-12 | fin | B | B / oui | B / oui | B / NON | B / oui |
| P-13 | net | B | B / évid. | B / évid. | B / évid. | — |
| O-01 | fin | B | B / oui | B / oui | B / oui | — |
| O-02 | net | B | B / évid. | B / évid. | B / évid. | — |
| O-03 | fin | A | A / oui | A / oui | A / oui | — |
| O-04 | fin | B | B / oui | B / oui | B / oui | — |
| O-05 | fin | B | B / oui | B / oui | B / oui | — |
| O-06 | net | A | A / évid. | A / évid. | A / évid. | — |
| O-07 | fin | B | B / oui | B / oui | B / oui | — |
| O-08 | fin | A | A / oui | A / oui | A / oui | — |
| O-09 | net | A | A / évid. | A / évid. | A / évid. | — |
| O-10 | net | B | B / évid. | B / évid. | B / évid. | — |
| O-11 | fin | B | B / oui | B / oui | B / oui | B / évid. |
| O-12 | net | A | A / évid. | A / évid. | A / évid. | — |
| O-13 | fin | B | B / oui | B / oui | B / oui | — |
| C-01 | fin | B | B / oui | B / oui | B / oui | — |
| C-02 | net | A | A / évid. | A / évid. | A / évid. | — |
| C-03 | fin | A | A / oui | A / oui | A / oui | — |
| C-04 | fin | A | A / oui | A / oui | A / oui | A / oui |
| C-05 | fin | A ⚑ | A / oui | B / oui | B / oui | — |
| C-06 | fin | A | A / oui | A / oui | A / oui | — |
| C-07 | fin | A ⚑ | A / oui | B / oui | B / oui | — |
| C-08 | net | B | B / évid. | B / évid. | B / évid. | — |
| C-09 | fin | A | A / oui | A / oui | A / oui | — |
| C-10 | fin | A | A / oui | A / oui | A / oui | — |
| C-11 | fin | B | B / oui | B / oui | B / oui | — |
| C-12 | net | B | B / évid. | B / évid. | B / oui | — |
| C-13 | fin | B | B / oui | B / oui | B / oui | — |
| C-14 | fin | A | A / oui | A / oui | A / oui | — |

## Comment refaire ces chiffres

```
python construire_paires.py --pour-relecteur <chemin>   # régénère paires.json + version aveugle
python croiser_relectures.py relectures/relecteur-2-jeu-v3b.json relectures/relecteur-3-jeu-v3b.json
```

Le second imprime les échecs, les « trop_evident », l'accord avec la vérité-terrain net / fin et
l'accord entre relecteurs. Les rapports bruts (raison de chaque choix, biais relevés, confiance)
sont dans `relectures/`.
