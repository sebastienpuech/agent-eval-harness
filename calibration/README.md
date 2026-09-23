# Judge calibration — the number behind the README

This folder is the full material behind one sentence of the main README: the `juge-par-grille`
judge scores like one human annotator with **Cohen's kappa 0.27, 95 % CI [0.05 ; 0.49]**, and
the same model with no grid reaches 0.31 on the same set. Everything needed to recompute the
number, or to disagree with it, is here. The working language of the files is French; this page
is the English map.

## What is in here

| Path | What it is |
|---|---|
| `jeu-v3/RESULTAT.md` | **The report.** The number first, the table by subset, the exact protocol, what the number does not say, and what the measurement found (the grid saturates). |
| `jeu-v3/resultat.json` | Every figure of the report, plus one line per pair with the four readings (designer, human, judge, bare model). |
| `jeu-v3/paires.json` | The 40 pairs: situation, two replies, domain, designer's ground truth and the flaw of the weaker reply. Fictional scenarios. |
| `jeu-v3/validation.md` | How the set was validated before annotation by four independent readers (Claude Opus 5 sub-agents, each in a fresh context), version by version, pair by pair. |
| `jeu-v3/relectures/` | Those readers' raw outputs (choices, reasons, biases they noticed). |
| `jeu-v3/annotations/` | The human annotation: the CSV as downloaded from the annotation page, the shuffled order (seed 20260924), the page itself, and the human-vs-designer crossing. |
| `jeu-v3/notes-du-juge.json` | The judge's scores: 80 replies × 3 runs, per-criterion means, noise. The "justifications" are template strings produced by the harness aggregator from the scores (no quotes from the scored text, by rule); they explain nothing. |
| `jeu-v3/notes-modele-nu.json` | The bare-model baseline: 40 pairs × 3 runs, run 2 with the display order reversed, raw answers kept. |
| `calculer_accord.py` | Computes everything in the report: three-class Cohen's kappa, bootstrap CI (10 000 draws, seed 12345), by subset. `python calculer_accord.py --jeu jeu-v3` |
| `noter_par_le_juge_parallele.py` | Runs the judge on the 80 replies (N = 3, resumable). `--jeu jeu-v3` |
| `jeu-v3/noter_modele_nu.py` | Runs the bare-model baseline. |
| `preparer_comparaison.py`, `jeu-v3/construire_paires.py`, `jeu-v3/croiser_*.py` | Build the set, the annotation page, and the crossings. |

## Order of operations, as it happened

1. The set was written by a Claude session (Fable 5.1) working with the repository's author: 40 pairs, 3 domains, 13 clear-cut / 27 fine gaps. The clear-cut / fine label was set by the first reader, then confirmed by the next two.
2. Four independent readers (Claude Opus 5 sub-agents, fresh context) validated it (`validation.md`). The first pass refused the set because it agreed too well with the designer (28/28); the fine pairs were then revised (`validation.md` counts that pass as 27 in one place and 12 in another; the named list gives 12 substantive rewrites), then 3 more pairs after readers 2 and 3.
3. One human annotated all 40 pairs blind, without ever seeing a judge score. **The annotator is the repository's author.** He did not write the ground truth (the design session did), and the annotation is dated 22 September 2026, before any machine scoring (23 September). The number 20260924 in the file names is the seed of the display order, not a date.
4. The judge scored the 80 replies (model `claude-opus-4-8`, the one shipped in `meta/skills/iterer-sur-retours/scripts/llm_client.py`), and, at the same time, the bare model answered the human's question on the 40 pairs. Neither reads the other's output.
5. `calculer_accord.py` produced `RESULTAT.md`. From the start of the human annotation onward, nothing was changed after seeing a number: not the set, not the annotation, not the "equal" rule, not the model. Before that, the set was revised during validation, as described above.

## Reading guide for the number

- The thresholds were written before any measurement: under 0.4 the grid is ambiguous, above 0.6 acceptable. 0.27 is under the first one.
- The bare-model baseline is the question every judge grid should answer: does the grid add anything the model does not already have? Here the difference is 0.04 in the bare model's favour, with a paired bootstrap CI of [−0.17 ; +0.25] and P(bare model > grid) = 0.65: the grid cannot be shown to do better, and cannot be shown to do worse. What is established is that it abstains (12 "equal" calls) where the bare model decides (0).
- A large part of the explanation is in the data: 45 of the 80 replies get 12/12, so in 10 pairs both replies tie at the ceiling, and 10 of the judge's 12 "equal" calls come from there. Without those 10 pairs, kappa goes from 0.27 to 0.39, still under the 0.6 bar. The saturation is measured; that it is the main cause is an inference, and a partial one.
- One annotator, who is also the author; 40 pairs; three domains of short replies: read the interval, not the point. The raw agreement rates in the report (e.g. 19/22) are on subsets chosen by the rater being evaluated and do not compare across rows; only kappa on 40 does.

## Reproducing

The judge and the baseline need a Claude Code login (they call the model through the Agent SDK,
same client as the harness). `calculer_accord.py` needs nothing: the notes are in the folder.

```
cd calibration
python calculer_accord.py --jeu jeu-v3
```
