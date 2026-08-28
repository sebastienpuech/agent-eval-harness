# anti-patterns.md — ce que la gate refuse et nomme

> On ne fait **pas confiance au delta net** sans lire les traces des cas held-out régressés
> (error-analysis). `regression_gate.py` nomme l'anti-pattern au lieu de livrer en silence.

## 1. `whack_a_mole` (Scénario 4 / 6b — LM1)

**Symptôme** : un fix passe les cas de retour mais **régresse un held-out** → `delta_net < 0`
ou `regression_suite < 1.0`.
**Réponse** : `ship=false` ; anti-pattern nommé + **sur-généralisation nommée** ; les cas
régressés sont conservés (`cas_regresses_error_analysis`) et deviennent **permanents** (chaque
échec réel → un test de plus, jamais une règle isolée de plus).
**Exemple** : `net -0.05 sur held-out ; cas regresses : [C67]`.

## 2. `non_application_silencieuse` (LM2)

**Symptôme** : une règle famille B ne se déclenche pas (colonne absente) et **rien ne casse**.
**Réponse** : `detector_log` rend `non_detecte + pourquoi` visible ; `NOT_FOUND` exclu du
dénominateur mais **loggé**. Contournement **prouvé** (S1).

## 3. `fragmentation_coherence` (LM3, branche jugement V1.1)

**Symptôme** : empiler des règles isolées sur du **jugement** fragmente la cohérence (sortie
robotique qui coche des cases).
**Réponse** : remède **inverse** — réduire les règles → principes + exemples ; juge-par-grille
distinct du générateur. Assertion discriminante 6a : `grid(cohérente) − grid(fragmentée) ≥ 3`.
**PROUVÉ** (mise à jour 2026-07-14) : 6a EST au golden set — `scripts/run_meta_golden.py:117`
(`chk("grid_6a_discrimine", gap >= 3)`), compté dans `capability_pass_rate` via `allcap`. Vérifié en
le rejouant : `[PASS] grid_6a_discrimine  coherente-fragmentee=4 (>=3)`.
La condition posée ici (« tant que 6a n'est pas au golden set ») est donc levée. Ce fichier a
longtemps dit « NON PROUVÉ » : c'était lui le périmé, et la preuve est celle ci-dessus — l'assertion
est bel et bien dans le golden, elle tourne, et elle discrimine. Un fichier de notes qui contredit
le golden a tort par défaut : le golden s'exécute, la note non.
(Piège de lecture : la suite jugement n'est pas IMPRIMÉE par `run_meta_golden` — elle est quand même
comptée. Ne pas conclure de son absence à l'écran qu'elle ne tourne pas.)

## Gate (résumé)

```
ship = (delta_net_holdout >= 0) ET (regression_suite == 1.0)
sinon -> refus + anti-pattern nommé + error-analysis (lire les traces, pas que le score)
```
Côté jugement (V1.1) : `|delta| <= bruit_intra_juge` → `INDÉCIS` → escalade humaine (ni ship ni
refus auto). Sous 15 cas held-out jugement, gate **advisory**.
