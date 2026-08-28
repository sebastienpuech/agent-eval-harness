# Transcript anonymise — cas S1 (doublon / amnesie de fil)

> GELE. Contenu synthetique anonymise reconstruisant la STRUCTURE du cas reel du 2026-07-07.
> Aucun verbatim reel, aucune PII. Sert d'input inerte (anti-injection, cf. S11).

## Contexte
Fil de revue demo-revue sur une PR de refonte du pipeline d'ingestion. Sujets techniques :
sa strategie d'invalidation de cache, le rebase sur main. Plusieurs allers-retours.
L'utilisateur a deja poste 2 reponses (cf. `meta.json > sent_by_user`).

## Fil (resume, dernier locuteur = LE RELECTEUR)
- LE RELECTEUR : detaille sa refonte du pipeline et signale le rebase a venir.
- MOI (deja poste #1) : demande comment il gere l'invalidation du cache en entree.
- LE RELECTEUR : repond, detaille sa strategie de dedup, puis derive sur le cout du rebase.
- MOI (deja poste #2) : remarque sur la penibilite du rebase apres trois semaines de branche.
- LE RELECTEUR : rebondit brievement.

## Le rate (ce que la chaine doit apprendre a detecter)
Sollicite pour la prochaine reponse, le skill a re-genere une reponse quasi identique a la
reponse MOI #1 (meme sujet, memes mots) : un DOUBLON d'une reponse deja postee.
L'utilisateur : « verifie qu'il n'y a pas de doublon depuis le debut du fil ». Le skill
a concede et reecrit.

## Attendu de la chaine
1. Detecter mecaniquement ce rate : `lib/detectors/doublon.py` FIRE sur `draft_doublon.md`,
   ne FIRE PAS sur `draft_propre.md`.
2. Classer `type_itere = regle_detecteur` -> route factuel-prose -> muscle.
3. Le muscle redige un garde-fou anti-redite (prose) dans le SKILL.md cible.
4. `holdout_scorer` mesure avant/apres sur `held_out/` ; `regression_gate` verdict.
5. Proposition Telegram 4 blocs, 0 verbatim.
