# Evaluation of classification

How good is `classification` on real Reviews? A person decides the right Topics and sentiment for 100 to 200 Reviews once; the command asks the models, compares and prints accuracy per Topic and sentiment, with the change since the last report.

It runs by hand or as a nightly job, never in CI, and calls paid models (a few cents for 200 Reviews; the Gateway Budget applies, run cap 1 USD). It lives outside `app/`, so it does not count toward coverage. The scoring, loading and report code has fast tests in `tests/evaluation/` that use fakes only.

## Run

```bash
export OPENROUTER_API_KEY=... ANTHROPIC_API_KEY=...   # never commit them; the command prints no key
make evaluate                    # prints the table and the change since evaluation/reports/last.json
make evaluate ARGS=--save        # the same, and stores this report as the new last one
make evaluate ARGS="--data evaluation/data/sample.jsonl --taxonomy evaluation/data/sample-taxonomy.json"
```

The sample files are eight invented Reviews, only to try the command and to feed the tests. Numbers from them mean nothing.

**Money:** the command's Call log is in memory, so the spend of a run is not added to the monthly 30 USD total and is not in the stored Call log (ADR-0005, ADR-0006). The run cap of 1 USD still applies to each run. Keep the month's other spend in mind before running it often.

## What the numbers mean

Per Topic: **recall** (of the Reviews that expect the Topic, how many got it), **precision** (of the Reviews that got it, how many expect it), **sentiment accuracy** (of the Reviews that got an expected Topic, how many have the expected sentiment). Overall: sentiment accuracy over all found Topics and the share of Reviews that ended `unclassified`. A fall of more than 5 percentage points against the last report is marked `DROP`. Definitions: `evaluation/_score.py`.

## Data (the owner makes this by hand)

- `evaluation/data/taxonomy.json`: the frozen Taxonomy the set was labelled against (`industry`, `topics` with `key`, `name`, `description`). `unclassified` is added if missing. Change it only together with re-checking the whole set.
- `evaluation/data/reviews.jsonl`: one Review per line:

```json
{"id": "e001", "text": "...", "rating": 2, "language": "cs",
 "expected": [{"topic": "waiting", "sentiment": "negative"}, {"topic": "staff", "sentiment": "positive"}]}
```

`id` is a new `e001`, `e002`, ... (never the id of a Source). `rating` and `language` are optional. `expected` holds 1 to 3 Topics from the Taxonomy, each once, with `positive`, `neutral` or `negative`. A Review that fits no Topic expects `unclassified` with `neutral`.

### Steps

1. Collect 100 to 200 real Reviews from both Sources, spread over Topics, sentiments and ratings; include short, mixed and off-topic ones. Raw exports stay outside the repository.
2. Anonymize each text (below).
3. Write the expected Topics and sentiment. Label by what the Review says, not by its star rating. Look at about 20 again a few days later to check you are consistent.
4. Save both files, run `make evaluate ARGS=--save` once for the first baseline and commit `evaluation/reports/last.json` (numbers only, no text).

### Anonymization

Remove or replace: reviewer name, photo and profile link, the owner's reply, the Source's own ids, URLs, phone numbers, e-mails, street addresses, names of employees or other people, order and ID numbers. Use a neutral word ("pracovnice", "pan u pokladny") or drop the sentence. Keep spelling, slang and tone otherwise; do not tidy the text, the set must look like real input.

The loader rejects a Review whose text `sanitize` would change or Flag (contacts, hidden characters, instruction-like text) and names its line. That check catches slips; it does not find a person's name, so read each text yourself.

Review texts reach a model only through `classification`, between its data delimiters. This command builds no prompt of its own.
