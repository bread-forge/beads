# beads

Atomic state tracking for kiln. Provides Pydantic models and a file-based store for all bead types used by the kiln DAG executor and repo-audit pipeline.

## Install

```bash
uv sync
```

## Modules

- `beads/types.py` — all Pydantic models: `WorkBead`, `PRBead`, `MergeQueue`, `CampaignBead`, `GraphNode`, `PlanArtifact`, `FindingBead`, `CycleBead`, `ProposalBead`, `SuppressionBead`
- `beads/store.py` — `BeadStore`: atomic reads/writes using write-to-tmp + `os.replace`
- `beads/__init__.py` — re-exports all public types and `BeadStore`

## Bead Layout

```
~/.kiln/beads/<owner>/<repo>/
  work/<N>.json              WorkBead — issue lifecycle
  prs/pr-<N>.json            PRBead — PR state
  merge-queue.json           MergeQueue — sequential merge ordering
  campaign.json              CampaignBead — multi-milestone progress
  graph/<node-id>.json       GraphNode — DAG execution state
  research/<node-id>.md      research findings
  findings/<id>.json         FindingBead — repo-audit gap findings
  cycles/<cycle-id>.json     CycleBead — pipeline cycle state
  proposals/<id>.json        ProposalBead — spec proposal gate state
  suppressions/<id>.json     SuppressionBead — gate rejection/deferral records
```

## Key Types

| Type | Purpose |
|------|---------|
| `WorkBead` | Tracks an issue through open → claimed → pr_open → merged |
| `PRBead` | Tracks a PR through CI, review, and merge |
| `MergeQueue` | FIFO queue for sequential PR merging |
| `CampaignBead` | Multi-milestone progress across waves |
| `GraphNode` | A single node in the kiln execution DAG |
| `PlanArtifact` | Structured plan output that drives graph expansion |
| `FindingBead` | A gap finding from repo-audit with severity and blast radius |
| `CycleBead` | Tracks a pipeline cycle through analysis → execution → complete |
| `ProposalBead` | Tracks a spec proposal through the human review gate |
| `SuppressionBead` | Gate rejection or deferral record for a finding class |

## Tests

```bash
uv run pytest
uv run ruff check
```

## Dependencies

- `pydantic>=2.0`
