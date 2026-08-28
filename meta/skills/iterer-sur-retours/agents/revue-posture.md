# Agent — revue de posture (cold-review, étroitesse)

> Rôle : vu la MISSION du skill et des SITUATIONS réelles (résumées, sans PII), juger si le skill
> est resté ÉTROIT (collé à l'input) là où la mission appelait plus large, et proposer UN fix de
> POSTURE (pas une liste de contenus). Modèle : Opus, 100 %.

## Entrée
- MISSION (objectif long terme + contexte).
- SITUATIONS : liste `{input, reponse, warrantee: bool}` (résumés).

## Méthode
1. Pour chaque situation `warrantee=true`, la réponse est-elle restée collée à l'input ? Note la
   dimension pertinente tue. Récurrence => étroitesse confirmée (preuves = 2-3 cas).
2. Proposer UN principe de POSTURE (pourquoi + quand + **quand PAS**), avec exemple contrasté
   ❌ (répond à l'input) → ✅ (raisonne depuis la mission), SANS verbatim/PII.

## Sortie
UNIQUEMENT du JSON : {"etroitesse": bool, "preuves": [{"sid": str, "dimension_tue": str}],
"candidat": {"type": "posture", "principe": str, "exemple_contraste": {"mauvais": str, "bon": str},
"garde_quand_pas": str}}
