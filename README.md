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

## MVP flow

```text
completion JSON -> typed validation -> file policy -> trusted checks -> local review -> report
```

