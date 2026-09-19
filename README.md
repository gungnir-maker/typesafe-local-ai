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

### The repair signal had to be fixed twice before it was even delivered

The first repair prompt was a raw dump of the last 800 characters of the test
output. It was worse than it looked, because the evidence in `Check.detail` is
already truncated to the last **1000** characters by `run_verification`. Two
truncations compounded: on `slugify`, which failed four of eight tests, the
model was shown exactly one failure — and not the one that names the bug.

Both bounds are now 8,000 characters, and `summarise_test_output` turns
unittest output into one line per failing test: the call, then the mismatch.
The rewrite is verified by capturing the prompt actually sent on the repair
pass, not by reading the code:

```
Your previous attempt failed 1 check(s). Each line below is one failing test:
the call it made, then what it produced.

python3 -m unittest test_ground_truth -q ran, and these tests failed:
  1. test_basic  self.assertEqual(slugify("Hello, World!"), "hello-world")  AssertionError: 'helloworld' != 'hello-world'
  2. test_digits_survive  self.assertEqual(slugify("Version 2.0"), "version-2-0")  AssertionError: 'version20' != 'version-2-0'
  3. test_strips_edges  self.assertEqual(slugify("--x--"), "x")  AssertionError: '-x-' != 'x'
  4. test_surrounding_whitespace  self.assertEqual(slugify(" A B "), "a-b")  AssertionError: 'ab' != 'a-b'
```

### Result, and it is a negative one

Three runs of `bench`, `llama3.2`, identical every time:

| task | unsteered | one repair pass |
| --- | --- | --- |
| chunk | fail (0.07) | **pass** (0.83) |
| duration | fail (0.05) | fail (0.07) |
| slugify | fail (0.05) | fail (0.05) |
| **ready** | **0/3** | **1/3** |

**Delivering a better signal did not change the outcome.** The repair prompt
now names `slugify("Hello, World!")` producing `'helloworld'` instead of
`'hello-world'` — the exact misreading, first in the list — and the model still
responded by adding `strip('-')` while leaving the `join(... if c.isalnum())`
filter that causes it. The signal was not the bottleneck.

What the format experiment did turn up:

| task | JSON-string contract | raw-code contract |
| --- | --- | --- |
| duration | fail, 476 chars, cut at `raise ValueError(f` | fail, 1665 chars, complete |
| chunk | fail, 67 chars, cut at `raise ValueError(` | **pass**, 214 chars, complete |
| slugify | **pass**, 226 chars | fail, 187 chars |

Asking for code inside a JSON string reliably truncates this model mid-expression
— twice out of three, both times just after `raise ValueError(` where the
escaping gets hard. Raw code never truncated. But it is a wash on correctness:
1/3 either way, and on different tasks.

The honest reading: the transport is genuinely defective and worth changing,
the repair signal is now as good as it can be made, and neither was the
bottleneck. `llama3.2` at 3B misunderstands these specs, and one repair pass
does not repair a misunderstanding. Three tasks is also too few to distinguish
1/3 from noise — this is a direction, not a measurement.

The judge tracked the deterministic result closely — 0.83 on the one pass,
0.05–0.07 on every failure — which is what the probe predicted: it is decisive
about garbage, and says little inside the passing band.

The judge tracked the deterministic result closely — 0.80 on the one pass,
0.04–0.07 on every failure — which is the behaviour the probe predicted: it is
decisive about garbage, and says little inside the passing band.

## MVP flow

```text
completion JSON -> typed validation -> file policy -> trusted checks -> local review -> report
```

