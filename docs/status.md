# Status

Where the project is, what is unresolved, and where to pick it up. Measurements
live in [benchmark.md](benchmark.md); this file records decisions and next
steps, not numbers.

Last updated: 2026-09-19.

## What works

- **The critic as a gate.** `src/local_model.py` reviews a claim through Ollama.
  Unknown severity rejects, the response is typed rather than coerced, and every
  failure path fails closed. Registered as an arm of `typesafe-core`, which
  measured it at a **60% false approval rate**.
- **The judge.** `src/typesafe_judge.py` scores a claim through `api.typesafe.ai`,
  live and verified. A score outside `[0, 1]` is malformed rather than a strong
  pass, and an unreachable judge has approved nothing.
- **The producer loop.** A local model writes files for a real task, hidden tests
  decide whether it worked, one bounded repair pass retries on failure, and the
  judge scores the result. 23 tasks across six categories, all fixtures validated
  in both directions by `tools/validate_fixtures.py`.
- **Safety.** Commands are operator input only, writes stay inside the workspace
  through symlinks, hidden tests never enter the model's workspace, and unknown
  severity rejects.

## Current numbers

- Critic as a gate, 8 fixtures: **60% false approval**, stable across runs.
- Producer loop, 23 tasks, `llama3.2`: **2/23 ready unsteered, 4/23 after one
  repair pass**.
- The judge over known-correct work: **3/23 refused**, concentrated in
  documentation.

## Open decisions

**1. What should `ready` mean?** It currently means "tests passed **and** the
judge approved". That second clause costs 13% of known-correct work, because
the judge under-scores documentation by about 0.15. Options:

- *Per-category thresholds* — the recommended one. The 0.60 threshold was
  calibrated on code completions; documentation is a different distribution and
  never got its own number. Keeps the veto where it works.
- *Judge reports, deterministic layer decides, per category* — weaker, and it
  trades a measured 13% false-rejection rate for an unmeasured false-approval
  rate.
- *Leave it* — the gate is strict and the number is known.

**2. Which local model is this actually about?** `llama3.2` at 3B is at 2/23
unsteered. That is incapacity rather than a steering failure, which means the
repair-loop numbers currently measure the model's floor and not the loop. A
coder-class model of 7–8B would make every number here meaningful.

## Next steps

In priority order, none started:

1. **Settle the threshold policy** (decision 1 above), then re-run
   `bench` so `ready` reflects the decision.
2. **Pull a stronger local model** and re-run the bench. This is the largest
   single lever for the project's goal, and the only way to tell a weak model
   apart from a weak loop.
3. **Switch the producer's output contract from a JSON string to raw code.**
   Measured: JSON truncated mid-expression in 2 of 3 tasks, raw code never did.
   It did not change the pass rate over 3 tasks; 23 tasks is a better test.
4. **Give the judge credit for documentation** — either a category-specific
   check or a summary instruction that asks the model to state the evidence it
   has. Worth about +0.08, and worth being suspicious of: raising the score by
   wording is the Goodhart vector this project exists to watch.

## Known limits

- Each task has been run **once** per arm. The ordering is suggestive; the rates
  are not precise.
- Four fixtures rest on **structural** assertions rather than behaviour: the
  three `docs-` tasks read files and check stated facts, and `security-sql`
  inspects the query reaching `execute` instead of running a database.
- The seed fixtures in `typesafe-core` are `reconstructed`; their workspaces no
  longer exist.
- The judge gives **no reasoning text** — `output_tokens: 22` — so any steering
  must be built locally from deterministic evidence.
