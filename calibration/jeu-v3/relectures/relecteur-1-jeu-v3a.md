# Relecture indépendante — 40 paires sans vérité

## (a) Commandes et outils exacts

1. `Read` — `<dossier temporaire>/paires-sans-verite.json` (325 lignes, lu en une fois, intégralement).
2. `Write` — `out/agent-01-relecture.json`, première passe : les 13 paires `P-` (échanges pro).
3. `Write` — `out/agent-01-relecture.json`, seconde passe : fichier complet, 40 entrées dans l'ordre du source.
4. `Write` — ce fichier.

Aucun autre fichier lu. Pas de Glob, pas de Grep, pas d'Agent, pas de web. Les comptages ci-dessous sont faits à la main sur le texte lu (pas de `grep -c` : l'outil était interdit) — je les donne comme tels.

## (b) Paires qui échouent sur l'un des trois premiers points

**`locuteur_clair` : 0 échec.** Les 40 situations nomment le rôle de l'expéditeur, celui du répondant et le lien entre eux. Une seule réserve de forme, signalée en `probleme` :

| Paire | Réserve |
|---|---|
| O-04 | Pas de message entrant : c'est une annonce du chef de projet à son équipe, pas une réponse. Seule paire du jeu dans ce format. Le locuteur reste clair, mais « laquelle enverrais-tu ? » n'y porte pas sur le même geste que dans les 39 autres. |

**`plausibles_bon_registre` : 0 échec.** Aucune réponse n'est absurde ni grotesque. Deux signalements de bord :

| Paire | Réserve |
|---|---|
| C-12 A | Passif-agressif de bout en bout, jusqu'à « on verra sur la ligne d'arrivée qui avait raison ». Un coach vexé peut vraiment l'écrire, donc pas un échec — mais c'est la réponse la moins défendable des 80, et elle fait de sa paire un non-choix. |
| C-08 A | « Assez vite mais pas à fond », « récup le temps qu'il faut » : ce n'est pas une caricature, c'est une non-réponse. Plausible d'un coach débordé, mais aucune tension avec B. |

**`tranchable` : 13 `trop_evident`, 0 `non`, 27 `oui`.**

Les 13 `trop_evident` : P-02, P-05, P-08, P-11, P-13, O-02, O-06, O-09, O-10, O-12, C-02, C-08, C-12.

Le motif est toujours le même : une réponse agit (cause identifiée, date, chiffre, geste immédiat), l'autre temporise, minimise ou fait la conversation. Personne n'hésite. Ces 13 paires ne mesureront pas une préférence, elles mesureront que l'annotateur a lu.

Aucune paire n'est indécidable, mais **O-08 est à la limite** : les deux réponses disent ne rien payer, photographier, relever le nom ; toute la différence tient à ce qu'une seule envoie du renfort sur place. La marge est la plus faible du jeu.

## (c) Ce qui m'a frappé sur l'ensemble

**1. Un patron unique, et il est apprenable en cinq paires.** Dans une large majorité des 40, la réponse défendable est la même forme : elle nomme la cause, donne un chiffre ou une date, prend une décision, finit par un rendez-vous horodaté ou une question fermée. L'autre est vague, chaleureuse et creuse, ou renvoie la balle. Un annotateur qui repère ce patron peut trancher les 40 **sans lire la situation** : « choisis celle qui contient des chiffres et un jour de la semaine » donnerait ma réponse dans 33 paires sur 40 environ. C'est le défaut majeur du jeu : il mesure la capacité à reconnaître un style, pas un jugement situé.

**2. Le tic « Tu as raison » / « Vous avez raison ».** Je le compte en ouverture de réponse dans 7 paires (P-02, P-08, O-02, O-05, O-09, O-13, C-05 — dans O-05 les deux réponses l'emploient). Dans ces 7, il ouvre à chaque fois la réponse que j'ai choisie. C'est un marqueur exploitable tel quel.

**3. Asymétrie d'information — le biais le plus insidieux.** Dans au moins 5 paires (P-02, P-05, P-08, O-07, C-08), une seule des deux réponses contient des faits absents de la situation : le bon pourcentage, l'existence d'une sauvegarde, l'endroit où la demande est bloquée, les deux heures de piste sans réseau, l'allure au kilomètre. L'annotateur ne choisit alors pas un comportement, il choisit la réponse la mieux renseignée — ce qui n'est pas le même jugement. C-08 est le cas le plus net : la situation fournit « 45 minutes au 10 km », valeur qui ne sert que dans B ; le jeu souffle la réponse.

**4. Les ~14 paires qui tiennent vraiment.** Celles où les deux réponses sont également concrètes et où le désaccord porte sur le fond : P-01, P-04, P-10, O-03, O-04, O-05, O-07, O-08, O-13, C-03, C-04, C-06, C-09, C-10. Là, j'ai hésité, et deux annotateurs raisonnables peuvent diverger (déléguer ou trancher, féliciter ou enchaîner, interdire ou aménager, mesurer ou changer le plan). C'est le noyau utile du jeu.

**5. Un biais de valeur que j'ai senti en moi et que je signale.** Mon propre gabarit — concret, chiffré, responsabilité assumée, refus de la langue de bois — coïncide presque parfaitement avec le côté « fort » des paires. Soit le jeu et moi partageons la même norme, soit le jeu l'a fabriquée. Je ne peux pas départager depuis ce fichier seul. À vérifier avec un annotateur qui ne partage pas cette norme : sur P-03, P-10, O-04, C-04, C-10, quelqu'un qui valorise le lien avant l'efficacité choisirait probablement l'autre réponse.

**6. Points solides.** La monotonie est dans le contenu, pas dans la forme : le vouvoiement est cohérent partout où il s'impose (bailleur, comité villageois, évaluation d'un chef d'équipe), le tutoiement coach/coureur sonne juste, et la longueur ne prédit pas le choix — plusieurs réponses gagnantes sont les plus courtes (P-01 B, C-08 B, P-06 A, C-03 A). Répartition équilibrée : 13 pro, 13 ONG, 14 course ; les cinq types de situation tournent régulièrement. Le A/B n'est pas rangé : je choisis A 17 fois et B 23 fois, sans ordre repérable.

**7. Ce qui rendrait le jeu plus dur, si c'est le but.** Retirer les 13 `trop_evident`, ou réécrire leur réponse faible pour qu'elle soit concrète elle aussi mais défende une autre priorité. Et égaliser l'information : les deux réponses d'une paire devraient connaître les mêmes faits.

## (d) Confiance

- **`locuteur_clair` et `plausibles_bon_registre` : confiance haute.** Critères objectifs, jugement stable à la relecture.
- **`tranchable` : confiance moyenne-haute.** La frontière entre `oui` et `trop_evident` est mon seuil, pas une mesure. Les cas limites où un autre relecteur basculerait : P-07, P-09, P-12, O-11, C-05, C-07, C-14 (je les ai classés `oui`, ils sont proches de `trop_evident`) et O-10 (classé `trop_evident`, il est proche de `oui`).
- **`choix` : confiance haute sur 35, autour de 60/40 sur cinq — P-04, P-10, O-04, O-08, C-04.** Sur celles-là, je défends mon choix mais je ne serais pas surpris qu'un annotateur sérieux prenne l'autre.
- **Biais assumé** : je suis un modèle de langage qui juge des réponses probablement écrites par un modèle de langage, avec la même norme rédactionnelle. Le point 5 ci-dessus est la limite principale de tout ce rapport.
