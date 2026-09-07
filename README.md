# C13b0 Indexer

C13b0 Indexer is the durable routing/indexing tool used before working across the Infinity GitHub collection.

It is deliberately separate from any single Infinity application. Its job is to scan the repository collection, identify useful existing capabilities, distinguish implemented work from intended work, and produce a compact index so an AI builder can retrieve only the pieces relevant to the repository currently being worked on.

## Run

```bash
python3 c13b0.py
```

Quick scan:

```bash
python3 c13b0.py --limit 10
```

One repository:

```bash
python3 c13b0.py --repo TV-Database
```

The scanner is Python standard-library only. A `GITHUB_TOKEN` environment variable is optional and only increases GitHub API capacity; the scanner can inspect public repositories without it.

## Generated index

The scan writes `phi-index/` containing:

- `catalog.json` — repository/capability overview
- `frontend-index.json` — compact routing input for an AI/frontend builder
- `search-index.jsonl` — useful file/chunk records
- `repos/*.json` — repository-specific scan records
- `categories/*.json` — capability groupings

Large repositories are inspected through GitHub trees and selected useful text files rather than cloned wholesale.

## Infinity carry-forward contract

When an Infinity webpage is built or substantially repaired, the working process should automatically account for established common infrastructure rather than waiting for it to be requested again later:

- project-specific preview/share artwork
- Open Graph metadata
- X/Twitter large-card metadata
- Share/Post
- unified Infinity wallet
- Star Coin integration where the project uses rewards
- share/reward progress where applicable
- durable ledger/history where applicable
- mobile-first presentation
- canonical/deployment identity
- Infinity scanner/index manifest

This list is expandable. Once a component becomes an established reusable Infinity requirement, it belongs in the carry-forward contract and scanner rules.

The scanner reports whether these features appear to be present; it does **not** blindly inject them into every repository. The builder uses the report to select the correct implementation for the framework and project.

## Capability maturity

The index distinguishes intent from working implementation:

- `CAN_DO` — runtime/test evidence confirms the capability (reserved for verified results)
- `NEEDS_TEST` — implementation, dependencies and tests were discovered but have not been executed by this scanner
- `PARTIAL` — implementation exists but is incomplete or not fully evidenced
- `SHOULD_DO` — declared/intended capability without sufficient implementation
- `BLOCKED` — scan or implementation is blocked
- `ABSENT` — no useful evidence found

C13b0 should never promote README promises to `CAN_DO` merely because they are described well.

## Phi routing states

The generated capability records can use the Infinity Phi computational routing vocabulary:

`RED index/source -> YELLOW extraction/analysis -> ORANGE decision/routing -> BLUE transfer/transformation -> WHITE generation/composition -> RED re-index`

These are software routing states. They allow a builder to find a short useful path through the repository collection without loading unrelated projects.

## Goal

When work begins on a repository, the index should answer three questions immediately:

1. What does this repository already do?
2. Which standing Infinity pieces are missing or incomplete?
3. Which existing repositories/files contain the best reusable capabilities needed to finish the job?

That turns the full GitHub collection into a reusable capability network rather than hundreds of isolated repositories.
