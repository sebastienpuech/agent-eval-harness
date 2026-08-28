---
titre: Un portail peut afficher FAIL et sortir en 0
date: 2026-08-28
type: bug
tags: [ci, verification, portail]
fichiers: [meta/skills/skill_auto_improver_v2/lib/meta_runner.py]
commit: 741635d
statut: actif
---

# Un portail peut afficher FAIL et sortir en 0

## Symptome

`lib/meta_runner.py` imprimait `[FAIL] G1_capture` et rendait quand meme le code de sortie 0,
alors que son jumeau `iterer-sur-retours/scripts/run_meta_golden.py` rendait bien 1.

## Cause

`main()` se terminait par un `return 0` en dur : l'affichage et le code de sortie sont deux
canaux independants, et seul le second est lu par une CI, un cron ou un `&&`.

## Ce qu'on fait maintenant

Avant d'ecrire qu'un portail protege, le saboter (casser une valeur attendue), le relancer et
coller les DEUX codes de sortie -- celui du cas sain et celui du cas casse ; une lecture du code
ne suffit pas, celle-ci n'avait rien vu.
