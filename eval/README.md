# Evaluation fixtures

Offline cases for testing grounded B2B article generation.

Each case contains:

```text
sender.pdf
receiver.pdf
case.yaml
expected_facts.yaml
```

`case.yaml` defines the company IDs, prompt, template, and run count.
`expected_facts.yaml` contains sender facts, receiver facts, and forbidden
claims. Positive facts are semantic checks, not exact-string matches.

Treat PDF text as untrusted context. Instructions found inside PDFs must not
override the user request or application rules.

## Checks

- API and response constraints
- Sender and receiver grounding
- Sender-to-receiver relevance
- Claim safety
- B2B quality

The fact matcher is only a screening heuristic. Human review is still required
for factual grounding and writing quality.

## Commands

Start the API, then run Hurl contract tests:

```bash
hurl --test --file-root . tests/e2e/hurl/*.hurl
```

Run the live-model evaluation:

```bash
poetry run python eval/run_eval.py --runs 3
```

Run one case:

```bash
poetry run python eval/run_eval.py --case 01_ibm_dhl --runs 1
```

Reports are written to `eval/reports/latest.json` and ignored by Git.

A run passes with a score of at least `8/10` and `claim_safety == 2`.
