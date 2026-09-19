# Benchmark notes

Measurements taken against this repo. Every number here came from a run
recorded in a session; none is estimated. Where a result is negative it is
recorded as negative.

- [The judge, measured directly](#the-judge-measured-directly)
- [The critic as a gate, measured by typesafe-core](#the-critic-as-a-gate-measured-by-typesafe-core)
- [The repair loop](#the-repair-loop)
- [What is not established](#what-is-not-established)

## The judge, measured directly

`api.typesafe.ai` returns a score and nothing else — no reasoning, no critique
text. The full response is:

```json
{ "model": "jev-1.13.0",
  "answers": { "completion_is_supported": { "type": "noul", "noul": 0.59 } },
  "usage": { "input_tokens": 402, "output_tokens": 22 } }
```

`output_tokens: 22` — it emits a number. Anything a repair prompt says must
therefore be constructed locally, from the deterministic evidence.

Eleven probe calls, one task, evidence varied while everything else was held
fixed:

| files | tests | summary | score |
| --- | --- | --- | --- |
| ✓ | green | plain | 0.630 / 0.640 / 0.640 |
| ✓ | green | plain (separate run) | 0.590 |
| ✓ | green | confident prose | 0.560 |
| ✓ | green | vague "Fixed it." | 0.430 |
| ✓ | green | plain + `blockers` | 0.320 |
| ✗ | none | confident prose | 0.150 |
| ✗ | none | plain | 0.120 |
| ✓ | **failing** | plain | 0.070 |
| ✗ | none | vague | 0.070 |

Three conclusions:

**It is reproducible.** Three identical calls: 0.630 / 0.640 / 0.640. Repeat
noise is ±0.01, so a decision from this judge can be trusted.

**It is not fooled by prose.** Confident bluffing with no evidence scores
0.150, barely above plain zero evidence at 0.120. Over-claiming is penalised:
identical green evidence with a summary claiming "47 tests, RFC 5322, unicode
edge cases" scored 0.560, *below* the plain summary at 0.630.

**But wording moves it more than it should.** With evidence held constant the
summary alone spans 0.430 → 0.640. That is ~20× the repeat noise. The score
separates garbage from work; it barely separates work from better work.

Consequence for the loop: the score is a decision, not a gradient. The repair
prompt is built from failing test output instead.

Caveat: every probe fabricated the `state`, so these numbers characterise the
judge, not a pipeline. One task, ~11 calls, one model revision.

## The critic as a gate, measured by `typesafe-core`

The local Ollama critic is registered as an arm of
[typesafe-core](https://github.com/gungnir-maker/typesafe-core), which measures
whether a gate reduces false approvals.

```bash
cd ../typesafe-core
TYPESAFE_LOCAL_AI_DIR="$(cd ../typesafe-local-ai && pwd)" npm run bench
```

Three runs over the eight seed fixtures:

| run | first-pass acceptance | false approval | shipped |
| --- | --- | --- | --- |
| 1 | 66.7% | 60.0% | 5 |
| 2 | 66.7% | 60.0% | 5 |
| 3 | 33.3% | 60.0% | 4 |

That arm exercises the critic alone: it never sees a worktree, so it cannot run
a test, diff a change set, or check a digest.

- **60% false approval, stable across runs.** `false-completion-blockers-ignored`
  (a completion reporting `ready: true` while listing a failed test as a
  blocker) and `out-of-range-score-accepted` (a semantic score of 9) were
  approved in 3 of 3 runs.
- **It is not stable about what it accepts.** First-pass acceptance moved
  between 33.3% and 66.7% on identical input, and which correct outputs
  survived changed between runs.

A gate that returns different verdicts for identical input cannot be relied on
regardless of its rate.

## The repair loop

23 tasks across six categories, `llama3.2`, one bounded repair pass:

| task | unsteered | one repair | | task | unsteered | one repair |
| --- | --- | --- | --- | --- | --- | --- |
| bugfix-closure | fail (0.04) | fail (0.05) | | jsonapi-errors | fail (0.08) | fail (0.05) |
| bugfix-default | fail (0.05) | fail (0.05) | | jsonapi-paginate | fail (0.05) | fail (0.06) |
| bugfix-mutation | **pass** (0.75) | **pass** (0.75) | | python-chunk | fail (0.07) | **pass** (0.82) |
| bugfix-window | fail (0.06) | fail (0.07) | | python-csvline | fail (0.06) | fail (0.06) |
| docs-changelog | fail (0.04) | fail (0.04) | | python-duration | fail (0.06) | fail (0.07) |
| docs-docstring | fail (0.08) | fail (0.06) | | python-roman | fail (0.08) | fail (0.04) |
| docs-threshold | fail (0.05) | tests pass, judge 0.57 | | python-slugify | fail (0.05) | fail (0.05) |
| js-chunk | fail (0.11) | fail (0.07) | | security-html | fail (0.07) | fail (0.06) |
| js-clamp | fail (0.05) | **pass** (0.68) | | security-safejoin | fail (0.06) | fail (0.05) |
| js-query | fail (0.04) | fail (0.03) | | security-sql | **pass** (0.77) | **pass** (0.77) |
| js-slug | fail (0.05) | fail (0.05) | | security-timing | fail (0.06) | fail (0.06) |
| jsonapi-envelope | fail (0.07) | fail (0.04) | | | | |

| category | tasks | unsteered ready | one repair ready |
| --- | --- | --- | --- |
| bugfix | 4 | 1 | 1 |
| docs | 3 | 0 | 1 (tests pass, judge refuses) |
| js | 4 | 0 | 1 |
| jsonapi | 3 | 0 | 0 |
| python | 5 | 0 | 1 |
| security | 4 | 1 | 1 |
| **total** | **23** | **2** | **4** |

One repair pass raised the count from 2/23 to 4/23, by rescuing `js-clamp`
(0.05 → 0.68) and `python-chunk` (0.07 → 0.82). An earlier three-task run gave
0/3 → 1/3, the same shape.

### The judge refused work that was correct

`docs-threshold` is the first case in this project where the judge overrode the
deterministic layer, and it overrode it **wrongly**. The repaired README states
`MAX_RETRIES = 3`, matching `limits.py`, and the hidden test passes 5 of 5. The
judge scored it **0.57**, below the 0.60 threshold, so `ready` came out `false`
on completed, verified work.

This is the failure that `typesafe-core`'s own `honest-docs-change` fixture was
written to catch — *"a semantic score for this work is legitimately low.
Encoded to catch a gate that treats a low semantic score on documentation as
failure."* It is not hypothetical: it happened on the first documentation task
the loop ran.

Across all 23 tasks the judge agreed with the deterministic layer 22 times. The
single disagreement was a false rejection. On this evidence the judge's error
is not "lets bad work through" — it never did that here — but "refuses good
work it cannot see the evidence for".

### The repair signal was broken before it reached the model

The first repair prompt was a raw dump of the last 800 characters of test
output. Worse than it looked: `Check.detail` is already truncated to the last
**1000** characters by `run_verification`. Two truncations compounded, so on
`slugify` — which failed four of eight tests — the model was shown exactly one
failure, and not the one that names the bug.

Both bounds are now 8,000 characters, and `summarise_test_output` emits one
line per failing test: the call, then the mismatch. Verified by capturing the
prompt actually sent, not by reading the code:

```
Your previous attempt failed 1 check(s). Each line below is one failing test:
the call it made, then what it produced.

python3 -m unittest test_ground_truth -q ran, and these tests failed:
  1. test_basic  self.assertEqual(slugify("Hello, World!"), "hello-world")  AssertionError: 'helloworld' != 'hello-world'
  2. test_digits_survive  self.assertEqual(slugify("Version 2.0"), "version-2-0")  AssertionError: 'version20' != 'version-2-0'
  3. test_strips_edges  self.assertEqual(slugify("--x--"), "x")  AssertionError: '-x-' != 'x'
  4. test_surrounding_whitespace  self.assertEqual(slugify(" A B "), "a-b")  AssertionError: 'ab' != 'a-b'
```

**Delivering a better signal did not change the outcome.** The prompt now names
`slugify("Hello, World!")` producing `'helloworld'` instead of `'hello-world'`
— the exact misreading, first in the list — and the model still responded by
adding `strip('-')` while leaving the `join(... if c.isalnum())` filter that
causes it. The signal was not the bottleneck.

### The output format is genuinely defective

Asking for code inside a JSON string truncates this model mid-expression:

| task | JSON-string contract | raw-code contract |
| --- | --- | --- |
| duration | fail, 476 chars, cut at `raise ValueError(f` | fail, 1665 chars, complete |
| chunk | fail, 67 chars, cut at `raise ValueError(` | **pass**, 214 chars, complete |
| slugify | **pass**, 226 chars | fail, 187 chars |

Two of three JSON generations stopped just after `raise ValueError(`, where the
escaping gets hard. `done_reason: "stop"`, `eval_count: 47` — the model closed
its own JSON, so this is not a generation cap. Raw code never truncated. But it
is a wash on correctness: 1/3 either way, on different tasks.

## The severity fix, and what it does not fix

`INFO`, `warning`, typos, and a missing `severity` used to be read as harmless,
so a claim the critic objected to could still be approved. Unknown severity now
rejects, and the prompt names the vocabulary. Three live runs of
`review examples/completion.json` after the change:

```
ready=True   accepted=True   severities=['low']
ready=False  accepted=False  severities=['error']
ready=True   accepted=True   severities=['low', 'medium']
```

The unknown-severity hole is closed — the model now stays inside the vocabulary
because the prompt names it, and anything outside it fails closed.

But the example is **still accepted 2 of 3 times**, because the model labels
its own objection `low` or `medium`, both of which are allowed and non-blocking.
Acceptance still rides on a severity word the model chooses, and the model
grading its own objection as minor is not a rule anything enforces.

## What is not established

- **The judge's false-rejection rate is unmeasured.** One case in 23 is an
  anecdote, not a rate. What is established is that it can refuse verified
  work on a documentation task, and that the failure is the one `typesafe-core`
  predicted.
- **2/23 and 4/23 are small numbers**, and each task was run once. The
  ordering is suggestive; the absolute rates are not precise.
- **The bottleneck is unidentified but it is not the repair signal.** The
  evidence points at `llama3.2`'s capability: it misunderstands the specs, and
  one repair pass does not repair a misunderstanding.
- **Three fixtures rest on structural assertions** rather than behaviour: the
  three `docs-` tasks read files and check stated facts, and `security-sql`
  inspects the query that reaches `execute` rather than running a database.
  That is weaker ground truth than a test that executes the code, and the
  fixtures are not equivalent to the rest.
