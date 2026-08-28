# agent-eval-harness

*(English version: [README.md](README.md))*

Un moteur d'amélioration continue pour skills d'agents qui **refuse ses propres correctifs
quand ils font régresser**. Transformer une plainte d'utilisateur en retouche de prompt est
courant. Mesurer si la retouche a vraiment aidé, sur des cas que l'auteur du correctif n'a
jamais vus, l'est beaucoup moins.

Une seule régression sur un cas réservé suffit à rejeter un correctif, quel que soit le gain
sur les autres.

## La boucle

```
retour  →  classement  →  patch scopé  →  mesure sur held-out  →  validation humaine
           factuel /       réécriture     une seule régression
           jugement        append-only    bloque la livraison
```

Chaque étage est un skill distinct, et chacun se lit seul :

| Dossier | Ce qu'il fait |
|---|---|
| `meta/skills/amelioration_continue` | L'orchestrateur : détection, routage, mesure, proposition. |
| `meta/skills/iterer-sur-retours` | Normalisation, fork factuel/jugement, jeux réservés, deux lentilles de revue à froid. |
| `meta/skills/skill_auto_improver_v2` | La réécriture append-only et le juge gelé. |

## Trois choix peu courants

Daté du 28/08/2026 et vérifié ce jour-là contre la documentation de chaque outil cité, parce
qu'une affirmation sur ce qui est peu courant vieillit plus vite que le code qu'elle décrit.

Rien de ce qui suit n'est une idée neuve, et la section serait plus faible à prétendre le
contraire. Les plateformes d'évals épinglent déjà une référence et signalent les régressions cas
par cas par rapport à elle (LangSmith, Braintrust), et promptfoo fait déjà échouer un build quand
un seuil n'est pas tenu. La documentation de DSPy avertit elle-même que ses optimiseurs
surapprennent et recommande de garder un jeu de test réservé. Ce qui est peu courant, c'est
qu'ici ce sont des propriétés du run et non des habitudes de l'opérateur, et que l'issue par
défaut est le refus.

**Le jeu réservé est caché à ce qui a écrit le correctif**, pas seulement à la métrique. Un
optimiseur qui choisit son candidat en le notant contre un jeu de validation a utilisé ce jeu
comme signal d'apprentissage : GEPA est conçu pour suivre sa frontière de Pareto sur un jeu de
validation distinct de celui contre lequel il mute, et pour sélectionner dessus.
Ici `G12_golden_holdout` et le contrôle d'isolation sont rejoués à chaque
passage, donc la séparation ne peut pas cesser de tenir en silence.

**Les tâches factuelles et de jugement sont routées séparément.** Une tâche dont la vérité se
vérifie mécaniquement reçoit une matrice déterministe et un détecteur. Une tâche subjective reçoit
une grille ancrée, des exemples contrastés, et délibérément *moins* de règles, parce qu'empiler des
règles sur un problème de goût est la façon dont un skill se dégrade. Le fork est tranché avant
toute mesure, et la machinerie diverge presque entièrement après lui.

**Le refus est démontré, pas affirmé.** `whack_a_mole_attrape` est un correctif planté : il répare
ce qu'on lui a demandé de réparer et casse discrètement le cas réservé `C67`. Laisser passer ce
correctif fait virer la suite au rouge. Un garde-fou que personne n'a essayé de contourner est
décoratif, donc celui-là est attaqué à chaque passage.

Les limites de ces trois choix sont dans `Ce que ça ne fait pas`, plus bas. Cette section est courte
et précise à dessein : l'alternative est une affirmation que personne ne peut vérifier.

## Ce qui est réellement vérifié

Trois suites, relancées le 28/08/2026 sur un clone nu. Les commandes sont ci-dessous : lancez-les
et contestez les chiffres plutôt que de les croire.

Python 3.10+ et `pip install -r requirements.txt` (deux paquets : `pytest`, `PyYAML`). Rien
d'autre n'est nécessaire ; vérifié sur 3.12. Chaque commande sort en code non nul si sa suite
échoue.

```bash
cd meta/skills/skill_auto_improver_v2 && python lib/meta_runner.py       # golden META
cd meta/skills/iterer-sur-retours     && python scripts/run_meta_golden.py
cd meta/skills/amelioration_continue  && python -m pytest tests/ -q
```

- **81 tests passent** dans `amelioration_continue`.
- **`capability_pass_rate = 1.00`, `regression_pass_rate = 1.00`** dans `iterer-sur-retours`,
  dont un cas `whack_a_mole_attrape` : un correctif qui répare une chose et casse le cas `C67`
  est attrapé et refusé (`ship=False`).
- **Le golden META passe tous ses portails**, dont `G8_anti_gaming`, `G9_circuit_breaker`,
  `G11_confidentialite`, `G12_golden_holdout`, `G13_judge_calibration`, `G16_red_team`.
  `G13` est plus étroit que son nom : il prouve que la mesure d'accord distingue une fixture
  calibrée d'une qui ne l'est pas. Aucun jeu annoté par des humains n'y est passé, donc le juge
  lui-même reste non prouvé. Voir plus bas.

Les portails sont du Python déterministe, pas des appels au modèle. Compter, dédupliquer,
valider un format et vérifier une régression sont des tâches mécaniques ; les confier à un
modèle de langage ajoute du coût et de la variance pour rien.

## Ce que ça ne fait pas

Cette section existe parce qu'un dépôt qui ne liste que ses forces n'est pas une preuve.

- **Le juge est gelé, pas étalonné.** Sa grille est figée pour que les runs restent comparables,
  mais elle n'a jamais été confrontée à des annotateurs humains. Tant que ce chiffre n'existe
  pas, toute mesure de qualité produite ici est cohérente en interne et non prouvée en externe.
  L'établir est le prochain chantier, et le résultat sera publié quel qu'il soit.
- **La mesure tourne en mode `recorded`.** Les sorties des cas réservés sont figées dans des
  fixtures, ce qui rend la suite déterministe et sans appel au modèle. Le mode `live`, où le
  skill cible est réellement exécuté sur chaque cas, est différé. La note honnête est dans le
  code lui-même, en tête de `lib/holdout_scorer.py`.
- **Ce n'est pas encore un harnais qu'on branche sur ses propres agents.** Le moteur tourne sur
  ses fixtures gelées. Des portails composables utilisables par un tiers sont le prochain jalon,
  et le nom du dépôt est autant une destination qu'une description.
- **Aucun chiffre de coût ni de latence.** Jetons par tâche et temps de relecture ne sont
  mesurés nulle part ici.

## Ce dépôt est un extrait

Il publie le moteur, pas l'atelier autour. Les documents de conception, les journaux de chaque
skill et l'arbre `demo/` des skills cibles restent privés, et le resteront.

Une conséquence est visible dans le code : des commentaires portent des renvois comme
`data_model §4` ou `archi §2.3` vers des documents que vous ne pouvez pas lire. Ce sont des
notes de provenance, qui disent d'où vient une décision. Rien n'en a besoin pour lire, faire
tourner ou modifier le code, et les vérifications ci-dessus tournent sur un clone nu. Là où un
raisonnement comptait vraiment, il est écrit en clair dans le fichier plutôt que cité.

Ce qui se branche sur une cible réelle (registre de skills, allowlist de confidentialité) est
optionnel. Par défaut le moteur tourne sur ses propres valeurs gelées et ses fixtures neutres,
sans rien à fournir.

## Hook anti-fuite

Le dépôt embarque deux hooks fail-closed qui scannent contre une liste de motifs locale :
`pre-commit` couvre le contenu indexé et l'identité de l'auteur, `commit-msg` couvre le message.
La séparation n'est pas cosmétique : un hook `pre-commit` ne reçoit aucun argument et ne peut
donc pas lire le message.

```bash
git config core.hooksPath .githooks
cp .githooks/denylist.example.txt .githooks/denylist.local.txt   # puis mets-y tes motifs
```

Le fichier `.local` est gitignoré volontairement : la liste de ce qu'on cache le révèle.

## Licence

MIT. Voir [LICENSE](LICENSE).
