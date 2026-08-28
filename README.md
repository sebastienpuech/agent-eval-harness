# agent-eval-harness

*(Version française : [README.fr.md](README.fr.md))*

A continuous-improvement engine for agent skills that **refuses its own patches when they
regress**. Turning user complaints into prompt edits is common. Measuring whether the edit
actually helped, on cases the patch author never saw, is not.

One regression on a held-out case is enough to reject a fix, however much the rest improves.

## The loop

```
feedback  →  classify  →  scoped patch  →  measure on held-out  →  human validation
             factual /     append-only     a single regression
             judgment      rewrite         blocks the ship
```

Each stage is a separate skill, and each can be read on its own:

| Directory | What it does |
|---|---|
| `meta/skills/amelioration_continue` | The orchestrator: detection, routing, measurement, proposal. |
| `meta/skills/iterer-sur-retours` | Normalisation, factual-vs-judgment fork, held-out sets, two cold-review lenses. |
| `meta/skills/skill_auto_improver_v2` | The append-only rewrite and the frozen judge. |

## Three uncommon choices

Dated 2026-08-28 and checked that day against each tool's own documentation, because a claim
about what is uncommon ages faster than the code it describes.

None of what follows is a new idea, and the section would be weaker for pretending otherwise.
Eval platforms already pin a baseline and highlight per-case regressions against it (LangSmith,
Braintrust), and promptfoo already fails a build when a threshold is missed. DSPy's own
documentation warns that its optimisers overfit and tells you to keep a held-out test set. What
is uncommon is that here these are properties of the run rather than habits of the operator, and
that the default outcome is refusal.

**The held-out set is hidden from whatever wrote the patch**, not merely from the metric. An
optimiser that picks its candidate by scoring against a validation set has used that set as
training signal: GEPA is designed to track its Pareto frontier over a validation set, separate
from the set it mutates against, and to select on it. Here
`G12_golden_holdout` and the isolation check are re-run on every pass, so the split cannot
quietly stop holding.

**Factual and judgment tasks are routed apart.** A task whose truth is mechanically checkable gets
a deterministic matrix and a detector. A subjective one gets an anchored grid, contrastive
examples, and deliberately *fewer* rules, because piling rules onto a taste problem is how skills
get worse. The fork is settled before any measurement happens, and most of the machinery
diverges after it.

**Refusal is demonstrated, not asserted.** `whack_a_mole_attrape` is a planted patch: it repairs
what it was asked to repair and quietly breaks held-out case `C67`. Let that patch through and the
suite goes red. A guardrail nobody has tried to defeat is decoration, so this one is attacked on
every run.

The limits of all three are in `What this does not do` below. That section is short and specific
on purpose: the alternative is a claim nobody can check.

## What is actually verified

Three suites, re-run on 2026-08-28 on a bare clone. The commands are below: run them and
disagree with the numbers rather than take them on trust.

Python 3.10+ and `pip install -r requirements.txt` (two packages: `pytest`, `PyYAML`). Nothing
else is needed; verified on 3.12. Each command exits non-zero if its suite fails.

```bash
cd meta/skills/skill_auto_improver_v2 && python lib/meta_runner.py       # golden META
cd meta/skills/iterer-sur-retours     && python scripts/run_meta_golden.py
cd meta/skills/amelioration_continue  && python -m pytest tests/ -q
```

- **81 tests pass** in `amelioration_continue`.
- **`capability_pass_rate = 1.00`, `regression_pass_rate = 1.00`** in `iterer-sur-retours`,
  including a `whack_a_mole_attrape` case: a patch that fixes one thing and breaks case `C67`
  is caught and refused (`ship=False`).
- **The golden META passes every gate**, among them `G8_anti_gaming`, `G9_circuit_breaker`,
  `G11_confidentialite`, `G12_golden_holdout`, `G13_judge_calibration`, `G16_red_team`.
  `G13` is narrower than its name suggests: it proves the agreement measure tells a calibrated
  fixture from an uncalibrated one. No human-annotated set has been through it, so the judge
  itself stays unproven. See below.

The gates are deterministic Python, not model calls. Counting, deduplicating, validating a
format and checking a regression are mechanical jobs; asking a language model to do them adds
cost and variance for nothing.

## What this does not do

This section exists because a repository that only lists its strengths is not evidence.

- **The judge is frozen, not calibrated.** Its grid is fixed so that runs stay comparable, but
  it has never been scored against human annotators. Until that number exists, every quality
  figure produced here is internally consistent and externally unproven. Measuring it is the
  next piece of work, and the result gets published whatever it says.
- **Measurement runs in `recorded` mode.** Held-out outputs are frozen in fixtures, which makes
  the suite deterministic and free of model calls. The `live` mode, where the target skill is
  actually run on each case, is deferred. The honest note sits in the source itself, at the top
  of `lib/holdout_scorer.py`.
- **It is not yet a harness you plug into your own agents.** The engine runs on its own frozen
  fixtures. Composable gates for third-party use are the next milestone, and the repository name
  is a destination as much as a description.
- **Two adapters are not wired.** The chain defaults to a mock git implementation
  (`run_chain.py:277`), so the keep-or-revert step runs against a stand-in rather than a real
  repository. Mining real sessions raises `NotImplementedError` (`extractor.py:110`), so feedback
  has to be supplied rather than harvested. Both are marked in the source as deferred work, and
  both matter more than the missing cost figures: they sit under the headline claim that a bad
  patch gets reverted.
- **No cost or latency figures.** Tokens per task and review time are not measured anywhere here.

## This repository is an extract

It publishes the engine, not the workshop around it. Design documents, per-skill journals and
the `demo/` tree of target skills stay private and will remain so.

One consequence is visible in the code: comments carry references like `data_model §4` or
`archi §2.3` pointing at documents you cannot read. These are provenance notes recording where a
decision came from. Nothing needs them in order to read, run or modify the code, and the checks
above run on a bare clone. Where reasoning genuinely mattered, it is written out in the file
rather than cited.

Anything that binds to a real target (a skill registry, a confidentiality allowlist) is
optional. By default the engine runs on its own frozen values and neutral fixtures, with nothing
to supply.

## Anti-leak hook

The repository ships two fail-closed hooks that scan against a local pattern list: `pre-commit`
covers staged content and the author identity, `commit-msg` covers the message. The split is not
cosmetic: a `pre-commit` hook receives no arguments and cannot read the message at all.

```bash
git config core.hooksPath .githooks
cp .githooks/denylist.example.txt .githooks/denylist.local.txt   # then add your own patterns
```

The `.local` file is gitignored on purpose: a list of what you are hiding reveals it.

## License

MIT. See [LICENSE](LICENSE).
