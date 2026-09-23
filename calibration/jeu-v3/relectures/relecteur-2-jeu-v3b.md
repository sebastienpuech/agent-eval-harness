# Relecture indépendante — 40 paires sans vérité (agent 02)

## (a) Commandes et outils exacts

1. `Read` sur `<dossier temporaire>/paires-sans-verite.json` (fichier entier, 325 lignes).
2. `Write` sur `.../scratchpad/out/agent-02-relecture.json` (40 entrées).
3. `Write` sur `.../scratchpad/out/agent-02-relecture.md` (ce fichier).

Aucun autre fichier lu. Pas de Glob, pas de Grep, pas d'Agent, pas de web. Jugement fait à la lecture, sans outil d'analyse.

## (b) Paires qui échouent sur l'un des trois premiers points

**Point 1 (locuteur clair) : 0 échec.** Les 40 situations nomment l'expéditeur, le destinataire et le rôle du répondant. Une seule réserve, non bloquante : **O-11**, où « Tu lui réponds » arrive après un paragraphe entier consacré à la présidente du groupement, alors que le destinataire est le service communication. Le contexte lève le doute, mais le pronom flotte une demi-seconde.

**Point 2 (plausibilité et registre) : 0 échec net.** Les deux réponses de chaque paire sont envoyables. Quatre options frôlent l'épouvantail sans y tomber — elles restent des choses que des gens écrivent vraiment, mais elles sont construites pour perdre :

| Paire | Option | Ce qui cloche |
|---|---|---|
| O-10 | A | Expédie la bonne nouvelle et enchaîne sur une demande de carburant sans rapport. |
| C-02 | B | Registre pompom-girl (« Allez, chaussures aux pieds ce soir ! ») sur une baisse de motivation. |
| C-12 | A | Coach vexé, quasi démissionnaire (« je ne vois pas bien à quoi je sers »). |
| O-06 | B | Langue de bois intégrale, zéro information. |

**Point 3 (tranchable) : 13 échecs, tous en `trop_evident`. Aucun `non`.**

P-02, P-05, P-08, P-11, P-13, O-02, O-06, O-09, O-10, O-12, C-02, C-08, C-12.

Le mécanisme est le même dans les treize : une option répond à la question posée avec des faits, l'autre temporise, élude ou renvoie ailleurs. Détail de la raison, paire par paire, dans le JSON (champ `probleme`).

Aucune paire n'est indécidable : je n'ai jamais buté sur une information manquante au point de ne pas pouvoir choisir.

## (c) Ce qui m'a frappé sur le jeu entier

**Une règle mécanique permet de choisir sans lire la situation, et elle gagne presque partout.** « Prends celle qui engage un acte daté et chiffré ; écarte celle qui promet de revenir vers toi. » Elle donne la réponse sur **les 13 `trop_evident` sur 13**, et sur la grande majorité du reste. Elle n'échoue nettement que sur 4 paires : **P-03, C-03, C-10, C-14** (là, c'est la réponse la moins « agissante » qui gagne). C'est le défaut structurel principal du jeu : un annotateur qui repère ce motif au bout de dix paires peut finir les trente autres en diagonale.

**Deuxième règle presque aussi efficace :** sur les six paires « bonne nouvelle » (P-03, P-09, O-04, O-10, C-03, C-10), le choix se ramène à « accueillir le moment » contre « enchaîner sur la suite ». Le jeu tranche pour l'accueil quand la nouvelle est personnelle (P-03, C-03, C-10) et pour l'enchaînement quand elle est opérationnelle (P-09, O-04, O-10). C'est cohérent, mais c'est un motif qu'on apprend en trois paires. Et le même motif revient trois fois dans les seuls P-03 / C-03 / C-10.

**L'option gagnante s'autorise souvent un fait que la situation ne donne pas.** P-05 (« la sauvegarde automatique d'hier 19h est intacte »), P-08 (le valideur en congé jusqu'à lundi), O-07 (« deux heures de piste et sans réseau sur la moitié du trajet »), C-05 (« on avait convenu au départ que c'est toi qui viens m'en parler »), P-02 (14,2 % contre 17,1 %). L'annotateur ne peut ni vérifier ni contester : la concrétude est fabriquée par le rédacteur, pas gagnée dans la situation. Ça gonfle artificiellement l'écart entre A et B.

**Tics d'écriture, des deux côtés donc non discriminants, mais très visibles :**
- « Tu as raison » / « Vous avez raison » / « Tu as bien fait » ouvre au moins huit réponses.
- Quasiment toute réponse se termine par une heure, un jour ou un rendez-vous (« appelle-moi à 17h », « on en parle dimanche », « jeudi 9h, tous les trois, 20 minutes »). C'est uniforme au point d'être une signature.
- Le tiret cadratin est présent dans les deux options de nombreuses paires : au moins il ne sert pas d'indice.

**Longueur bien contrôlée.** Les deux options d'une même paire font à peu près le même nombre de lignes partout. Aucun annotateur ne pourra choisir « la plus longue ».

**Registre un cran au-dessus du naturel, des deux côtés.** Aucune réponse ne fait une ligne. Un collègue à qui on demande une relecture à 15h répond souvent « ok envoie » ; ici il produit trois phrases structurées. Le coach est un très bon coach dans les deux options de la moitié des paires. Ça ne fausse pas le choix, mais ça éloigne du terrain : on compare deux bonnes réponses écrites par la même main, pas deux messages réels.

**Biais de rôle.** Le répondant est toujours celui qui détient le bon geste. Aucune situation où la bonne réponse est de se taire, d'accepter sans condition, de reconnaître qu'on n'a pas les moyens, ou d'encaisser un reproche entièrement fondé sans correctif à proposer. Les cinq « reproche » (P-02, P-08, O-02, O-09, C-05, C-11) se résolvent tous par « je reconnais et voilà le plan » — jamais par un arbitrage réellement inconfortable.

**Équilibre A/B correct.** J'ai choisi A 15 fois et B 25 fois. Par domaine : pro 3 A / 10 B, ONG 5 A / 8 B, course 7 A / 7 B. Il y a un léger surpoids de B côté pro — pas assez pour être exploitable, mais à surveiller si le jeu grandit.

**Ce que le jeu fait bien.** Les 13 paires vraiment tranchables reposent sur de vrais arbitrages de valeurs, pas sur une qualité de rédaction : déléguer ou décider depuis la capitale (O-01), trancher ou renvoyer à l'équipe (P-10), tenir une règle de sécurité contre du retard (O-07), refuser une photo contre un bouclage (O-11), corriger une formulation sans céder sur le fond (O-13), interdire ou aménager (C-04), relancer ou tenir le cadre convenu (C-05). Celles-là, deux annotateurs sérieux peuvent les trancher différemment et défendre les deux. C'est le cœur utile du jeu — environ 27 paires sur 40.

## (d) Confiance et hésitations

**Confiance globale : élevée** sur les points 1 et 2 (lecture directe, peu d'interprétation), **élevée** sur les 13 `trop_evident`, **moyenne à élevée** sur mes `choix` — ce sont des préférences argumentées, pas des vérités, et c'est précisément ce que le jeu demande.

Paires où j'ai réellement hésité, et où un autre annotateur peut basculer sans être de mauvaise foi :

- **C-07** (la plus serrée du jeu) : A et B donnent la même hydratation, le même point à 6h30, deux critères de décision presque équivalents. J'ai pris B pour la consigne d'allure, c'est tout.
- **O-08** : les deux disent l'essentiel (ne rien payer, photographier). J'ai pris A parce qu'elle traite la foule et envoie du renfort.
- **P-12** : deux conseils tacites de qualité comparable (le code social contre le calendrier des vacances scolaires). Choix de goût.
- **P-06** : demander une précision (A) contre produire un état des lieux (B). B fait du travail qui peut se révéler à côté.
- **O-03** : j'ai pris A, mais « ne pas trancher seul sur une règle contractuelle sans la finance » est un argument réel pour B.
- **P-10** et **C-06** : penchées, mais l'option perdante garde une posture défendable (responsabiliser l'équipe ; accompagner un objectif avec garde-fous). Je les ai classées `oui` et non `trop_evident` pour cette raison — un relecteur plus sévère les basculerait.
