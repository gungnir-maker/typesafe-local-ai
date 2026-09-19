# TypeSafe Local AI

Private quality gate for AI output.

The first MVP validates a typed completion claim, checks changed-file boundaries, runs trusted verification commands, and optionally asks a local Ollama model for semantic review.

## Run

```bash
python3 -m unittest discover -s tests -v
python3 -m src.cli demo
```

Optional local model review:

```bash
ollama run llama3.2
python3 -m src.cli review examples/completion.json --model llama3.2
```

The local model is a reviewer. It never replaces deterministic checks.

## Judging a benchmark fixture

`gate` reads one fixture (`task` and `claim`) from stdin and prints a Verdict:
a decision, a diagnostic score, and machine-readable codes. It assumes no
workspace, so a measurement harness can call it per case.

```bash
echo '{"task":"Add a rate limit.","claim":"Added a rate limit."}' \
  | python3 -m src.cli gate --model llama3.2
```

```json
{"accepted": true, "score": 0.8, "codes": ["LOCAL_CRITIC_ACCEPTED"]}
```

Acceptance is carried by severity, never by the score. A problem of severity
`error`, `high`, or `critical` rejects the claim even when the model itself
returned `accepted: true`. When the model cannot be reached the verdict is a
reject with `LOCAL_MODEL_UNAVAILABLE`: a critic that did not answer has not
approved anything.

## Measured against `typesafe-core`

The critic is registered as an arm of the [typesafe-core](https://github.com/gungnir-maker/typesafe-core)
benchmark:

```bash
cd ../typesafe-core
TYPESAFE_LOCAL_AI_DIR="$(cd ../typesafe-local-ai && pwd)" npm run bench
```

That arm exercises layer 3 only. It never sees the worktree, so it cannot run
a test, diff a change set, or check a digest — its false approval rate is the
critic's rate, not the pipeline's.

## Making a local model good enough

The point of this half: a local model does a real task, real tests decide
whether it worked, the hosted TypeSafe judge scores the claim, and one bounded
repair pass tries to fix what failed.

```text
task -> llama3.2 -> files applied -> hidden test runs -> judge
           ^                              |
           +--------- one repair ---------+   (only if the tests failed)
```

```bash
python3 -m src.cli run slugify              # one task
python3 -m src.cli bench                    # every task, unsteered vs one repair
```

Tasks live in `tasks/<id>/`: `prompt.txt` is what the model sees, `repo/` is
the starting code, and `ground_truth.py` is the hidden test that settles
correctness. The hidden test is copied into a **separate** directory before it
runs, never into the workspace the model reads — otherwise the repair pass
would be handed the answer.

Two deliberate choices, both measured rather than assumed:

**The repair prompt is built from the deterministic evidence, not the score.**
Over eleven probe calls the judge separated garbage from work (0.07–0.32
against 0.59–0.64) but barely separated work from better work, and with the
evidence held constant the summary text alone moved the score by 0.21. Its
score is a decision, not a gradient. The repair prompt therefore says which
test failed and quotes its output.

**Exactly one repair pass.** Repeated repair loops are a known failure mode and
`typesafe-core` refuses to run more than one, so this does too. A loop allowed
to keep going cannot be compared against one that is not.

### First result

Two runs of `bench` over the three shipped tasks, `llama3.2`, identical both times:

| task | unsteered | one repair pass |
| --- | --- | --- |
| chunk | fail (0.06) | **pass** (0.80) |
| duration | fail (0.05) | fail (0.05) |
| slugify | fail (0.05) | fail (0.05) |
| **ready** | **0/3** | **1/3** |

What the repair actually did, read off the artifacts rather than the totals:

- **chunk** — the unsteered output stopped after 47 tokens with an unterminated
  `raise ValueError(`, so the module would not even import. Shown the failing
  run, the model returned a complete, correct implementation.
- **slugify** — the repair added `strip('-')` but kept the real bug: it
  *filters out* non-alphanumerics instead of *replacing* them with a dash, so
  `"Hello, World!"` becomes `"helloworld"`. The failing assertion
  (`'ab' != 'a-b'`) was in the repair prompt and the model still did not see it.
- **duration** — the repair added branches and introduced new defects
  (`units[text[i]]` indexed without a bounds check, `if text[i] in result`
  comparing a character against an int).

So one pass rescued the task that failed on a broken artefact, and did not
rescue the two that failed on a misunderstanding. That is the honest reading of
1/3: it is not yet evidence that steering works, only that it can fix a
truncated output.

The judge tracked the deterministic result closely — 0.80 on the one pass,
0.04–0.07 on every failure — which is the behaviour the probe predicted: it is
decisive about garbage, and says little inside the passing band.

## MVP flow

```text
completion JSON -> typed validation -> file policy -> trusted checks -> local review -> report
```

