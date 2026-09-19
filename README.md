# TypeSafe Local AI

A local gate for AI output: a typed completion claim, a deterministic layer
that runs real tests, a local Ollama critic, and an optional hosted semantic
judge. Plus a loop that puts a local model to work on real tasks and measures
whether it can be made good enough.

**Measured results, including the negative ones, live in
[docs/benchmark.md](docs/benchmark.md). Current state and open decisions are in
[docs/status.md](docs/status.md).**

## Install

Python 3.11+ and no dependencies. For the local critic and the task loop, a
running Ollama with a model pulled:

```bash
ollama pull llama3.2
```

For the semantic judge, a TypeSafe API key. It is read from `TYPESAFE_API_KEY`
if set, otherwise from the DeepSeek Harness credential store at
`~/.dsh/.credentials.yaml`. Without a key the judge fails closed rather than
being skipped.

## Architecture

Three interchangeable layers, in this order. A later layer never rescues an
earlier one.

```text
claim -> type check -> deterministic checks -> judge -> decision
```

| module | job |
| --- | --- |
| `src/core.py` | `Completion` validation, path policy, command execution, `verify()` |
| `src/local_model.py` | the Ollama critic and its severity rules |
| `src/typesafe_judge.py` | the hosted TypeSafe judge |
| `src/producer.py` | asks a local model to write files for a task |
| `src/loop.py` | one bounded repair pass over a real task |
| `src/cli.py` | `demo`, `review`, `gate`, `run`, `bench` |

The two flows:

```text
# review one claim
completion JSON -> typed validation -> file policy -> trusted checks -> critic -> report

# put a local model to work
task -> llama3.2 -> files applied -> hidden test runs -> judge
           ^                              |
           +--------- one repair ---------+   (only if the tests failed)
```

## Usage

```bash
python3 -m unittest discover -s tests -v

python3 -m src.cli demo                                  # offline smoke test
python3 -m src.cli review examples/completion.json       # review one claim
python3 -m src.cli gate < fixture.json                   # one benchmark fixture, from stdin
python3 -m src.cli run slugify                           # one task end to end
python3 -m src.cli bench                                 # every task, unsteered vs one repair
```

Tasks live in `tasks/<id>/`: `prompt.txt` is what the model sees, `repo/` is
the starting code, and `ground_truth.py` (or `.js`) is the hidden test that
decides correctness. The id prefix is the category.

| category | tasks | what it covers |
| --- | --- | --- |
| `python-` | 5 | string, sequence, parsing, numeral work |
| `js-` | 4 | the same kind of work in JavaScript, graded by `node --test` |
| `jsonapi-` | 3 | pagination, response envelopes, error documents |
| `bugfix-` | 4 | real defects: an off-by-one, in-place mutation, a shared default, late binding |
| `docs-` | 3 | making documentation agree with the code |
| `security-` | 4 | path traversal, HTML escaping, SQL parameterisation, constant-time comparison |

Every fixture is checked in both directions by `tools/validate_fixtures.py`:
the starter must **fail** its hidden test — otherwise the task is not actually
undone — and a reference solution must **pass** it, otherwise the fixture is
unsatisfiable and every model failure would be the benchmark's fault. Both
halves matter; a fixture that always fails looks exactly like a weak model.

```bash
python3 tools/validate_fixtures.py
```

The `docs-` and `security-sql` tasks are graded by structural assertions
rather than by exercising behaviour — the documentation tests read the file
and check the stated facts, and the SQL test inspects the query that reaches
`execute` instead of running a database. That is weaker ground truth than a
test that runs the code, and it is recorded as such rather than presented as
equivalent.

## Safety

**Commands are operator input, never model input.** `run_verification` executes
through a shell, so a command string is code. Commands come only from the CLI,
configuration, or a module constant; `verify` refuses anything that is not a
non-empty string, and the loop builds its command from `TEST_COMMAND` rather
than from a proposal. `parse_proposal` drops every key except `summary` and
`files`, so a model cannot name a command even if it tries.

**Unknown severity rejects.** The critic may use `low`, `medium`, `error`,
`high`, or `critical`. Anything else — `INFO`, `warning`, a typo, a missing
field — blocks acceptance. An unrecognised severity is not a mild one; it is a
response the gate cannot interpret.

**Typing is checked, never coerced.** `accepted` must be a real boolean
(`bool("false")` is `True`, which would read a refusal as approval), `score`
must be a finite number in `[0, 1]`, and every claim field is checked for what
it is.

**Writes stay inside the workspace.** Claims reject `..` lexically, and
`apply_proposal` resolves the parent directory before writing so a symlink
inside the workspace cannot redirect a write outside it.

**Hidden tests never enter the model's workspace.** The ground-truth test is
copied into a separate directory before it runs; otherwise the repair pass
would be handed the answer.

**Everything fails closed.** An unreachable model, an unreadable response, a
missing key, or a command that cannot run all produce a refusal, never a pass.

## Benchmark

`npm run bench` in [typesafe-core](https://github.com/gungnir-maker/typesafe-core)
measures this critic as a gate, and `python3 -m src.cli bench` measures the
repair loop.

Headline, over 23 tasks with `llama3.2`: **2/23 ready unsteered, 4/23 after one
repair pass** — and the judge refused one task whose tests passed and whose
work was correct. All of it, with the caveats, is in
[docs/benchmark.md](docs/benchmark.md).
