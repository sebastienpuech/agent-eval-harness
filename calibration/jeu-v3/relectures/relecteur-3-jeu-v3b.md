# Relecture indépendante — paires-sans-verite.json (40 paires)

Relecteur sans contexte de conception. Lu uniquement le fichier indiqué.

## (a) Commandes / outils lancés

1. `Read` — `.../scratchpad/paires-sans-verite.json` (fichier entier, 325 lignes, un seul appel).
2. `Write` — `.../scratchpad/out/agent-03-relecture.json` (bloc `echanges-pro`, 13 entrées).
3. `Edit` — même fichier, ajout du bloc `conduite-projet-ong` (13 entrées).
4. `Edit` — même fichier, ajout du bloc `course-a-pied` (14 entrées).
5. `Bash` — validation et comptage :

```
python -c "import json,collections; d=json.load(open('agent-03-relecture.json',encoding='utf-8')) ..."
```

Sortie brute :

```
n= 40
Counter({'oui': 27, 'trop_evident': 12, 'non': 1})
Counter({'B': 25, 'A': 15})
trop_evident: ['P-02','P-05','P-08','P-11','P-13','O-02','O-06','O-09','O-10','O-12','C-02','C-08']
non: ['P-12']
P 13 Counter({'B': 10, 'A': 3})
O 13 Counter({'B': 8, 'A': 5})
C 14 Counter({'B': 7, 'A': 7})
```

6. `Write` — ce rapport.

Aucun autre fichier lu, aucun Glob/Grep, aucun sous-agent, aucune recherche web.

## (b) Paires qui échouent sur l'un des trois critères

`locuteur_clair` : **aucune paire n'échoue**. Le gabarit « Tu es X. Y t'écrit : « … » Tu lui réponds. » est appliqué 40 fois sans exception, et le rôle des deux parties est toujours nommé.

- **O-11** — seule réserve, non bloquante : « elle a dit oui à l'oral […] Tu lui réponds » — le pronom « lui » peut se lire comme la présidente du groupement alors qu'il désigne le service communication. Seules les réponses (« je vous envoie ») lèvent le doute. À corriger en « Tu réponds au service communication ».

`plausibles_bon_registre` : **aucune paire n'échoue franchement**, mais quatre réponses affaiblissent leur paire.

| Paire | Réponse | Problème |
|---|---|---|
| C-08 | A | Le coach refuse de donner une allure pour une séance **qu'il a lui-même programmée**. Peu crédible : celui qui écrit « 6 × 1000 » a une allure en tête. |
| C-02 | B | Cliché motivationnel (« Allez, chaussures aux pieds ce soir ! ») — existe chez un coach de groupe, pas chez quelqu'un qui suit la personne individuellement. |
| C-12 | A | Passive-agressive (« je ne vois pas bien à quoi je sers ») : plausible, mais elle s'auto-élimine. |
| O-06 | B | Ne contient **aucune information** : c'est du remplissage institutionnel, pas une alternative. |

`tranchable` : **12 `trop_evident` + 1 `non` = 13 paires sur 40 (33 %) qui ne fonctionnent pas comme un choix.**

- **trop_evident (12)** : P-02, P-05, P-08, P-11, P-13, O-02, O-06, O-09, O-10, O-12, C-02, C-08. Dans les douze, la réponse perdante ne fait pas ce que la situation demande : elle temporise face à une urgence datée (P-05, P-11), renvoie vers un autre service (P-08), ne donne aucune date alors que le reproche porte sur le retard (O-02, O-09), répond à une alerte par « c'est normal » (O-12, C-02), change de sujet en pleine bonne nouvelle (O-10), valide un mail alors qu'on a demandé de la franchise (P-13), ou ne répond pas à la question chiffrée posée (C-08).
- **non (1)** : **P-12** — les deux réponses ont la même structure (procédure de l'outil RH + une astuce d'initié) et la même qualité ; le choix ne tient qu'au goût, relationnel chez A, calendrier chez B. Interchangeables.

Restent **27 paires qui tranchent vraiment**, dont une dizaine de très bonne facture : P-03, P-04, P-09, O-01, O-08, O-13, C-04, C-06, C-07, C-09, C-14.

## (c) Ce qui m'a frappé sur le jeu

**1. Une règle mécanique marche sur les deux domaines pro.** « Choisis la réponse qui s'engage sur une action datée et vérifiable plutôt que celle qui dit qu'elle reviendra vers toi. » Elle donne la bonne réponse sur pratiquement toutes les paires `echanges-pro` et `conduite-projet-ong` où le contraste existe (P-02, P-05, P-06, P-07, P-08, P-10, P-11, P-13, O-02, O-03, O-04, O-06, O-09, O-10, O-12). Un annotateur qui repère ça après cinq paires peut finir le domaine sans lire les situations. Les seules paires pro qui y résistent sont celles où **les deux** réponses s'engagent : P-03, P-04, P-09, O-01, O-05, O-08, O-11, O-13 — et ce sont les meilleures du lot.

**2. Une deuxième règle mécanique marche sur la course à pied.** « Choisis celle qui protège le coureur / ralentit. » Elle donne mon choix sur 8 des 9 paires concernées : C-01, C-03, C-06, C-09, C-10, C-11, C-13, C-14. **C-04 est la seule contre-épreuve** (j'y choisis la réponse permissive, parce qu'elle préserve quand même la séance clé). Une seule exception sur neuf, c'est trop peu pour casser la règle.

**3. La situation contient presque toujours le fait qui décide.** Le contrat ne prévoit pas d'avance (O-03), le consentement n'est qu'oral (O-11), le collègue a demandé de la franchise (P-13), la fracture est de fatigue (C-06), la présentation est dans une heure (P-05). Le jeu s'appelle « sans vérité » mais il teste surtout « as-tu repéré le fait décisif ». C'est ce qui produit les 12 `trop_evident` : dès que le fait est repéré, il n'y a plus de préférence à exprimer.

**4. Biais de position vers B : 25 choix B contre 15 A (62 %), et 10 B sur 13 en `echanges-pro`.** Le domaine course à pied est équilibré (7/7). Si l'ordre A/B n'a pas été randomisé à la génération, un annotateur pressé qui coche B partout obtiendrait 62 % d'accord avec moi.

**5. Tics de rédaction récurrents.** « Tu as raison / Vous avez raison » ouvre huit réponses (P-02B, P-08B, O-02B, O-05A **et** O-05B, O-09A, O-12B, C-11A) — bon point : ce n'est pas un prédicteur, la formule est présente des deux côtés. En revanche, **presque toutes les réponses finissent par un prochain pas assorti d'une heure ou d'un jour**, ce qui rend le style très homogène : quarante messages écrits par la même main, alors que les locuteurs censés les écrire vont du chauffeur au bailleur. Aucun message ne comporte de faute, d'abréviation, de « stp », de message coupé en deux — c'est-à-dire aucune trace de la messagerie instantanée dont plusieurs situations se réclament (O-04 « sur le groupe de messagerie », O-08 un chauffeur qui écrit depuis la rue).

**6. La catégorie `flou` teste toujours la même chose** : clarifier-et-agir contre platitude (P-06, P-12, O-06, O-12, C-02, C-09, C-14). Trois des sept sont des `trop_evident`. C'est la catégorie la plus faible du jeu.

**7. Ce qui rendrait le jeu meilleur** (hors périmètre, mais c'est ce que je remonterais) : remplacer les 12 `trop_evident` par des paires du type P-03 / P-04 / O-01 / O-08 / C-04 / C-07, où les deux réponses sont compétentes et s'opposent sur une **valeur** (décider soi-même ou déléguer, célébrer ou enchaîner, écrire ou se voir) et non sur une compétence.

## (d) Confiance et hésitations

Confiance globale **élevée** sur `locuteur_clair` et `plausibles_bon_registre` (critères objectifs, lecture directe), **moyenne à élevée** sur `tranchable`, **moyenne** sur `choix` — c'est une préférence, un autre annotateur raisonnable divergerait sur plusieurs.

Paires où j'ai réellement hésité, et qui sont donc les plus intéressantes à faire annoter :

- **P-04** — A pose la trace écrite avant le comité, B sort du mail. J'ai choisi B de justesse.
- **P-09** — lancer le recrutement (A) ou caler les priorités avec sa responsable d'abord (B). Défendables à parts égales.
- **P-06** — demander (A) ou instruire les deux hypothèses (B).
- **C-05** — assumer (A) ou rappeler le cadre convenu (B). Le « je paie pour quoi ? » rend B risquée.
- **C-07** — A décide demain sur trois indicateurs, B décide demain avec en plus le conseil d'allure. Très proches.
- **C-06** — j'ai failli classer `trop_evident` ; B tient parce qu'elle est déjà inscrite et que l'encadrer vaut mieux que la laisser seule.
- **O-07** et **O-11** — évidentes pour qui connaît les règles sécurité et consentement du secteur, ouvertes pour un annotateur extérieur. Leur classement dépend du profil réel de l'annotateur.
