# beads

Atomic state tracking for kiln. Provides Pydantic models and a file-based store for all bead types used by the kiln DAG executor.

## Modules

- `beads/types.py` — all Pydantic models: `WorkBead`, `PRBead`, `MergeQueue`, `CampaignBead`, `GraphNode`, `PlanArtifact`
- `beads/store.py` — `BeadStore`: atomic reads/writes using write-to-tmp + `os.replace`

## Bead Layout

```
~/.kiln/beads/<owner>/<repo>/
  work/<N>.json          WorkBead — issue lifecycle
  prs/pr-<N>.json        PRBead — PR state
  merge-queue.json       MergeQueue — sequential merge ordering
  campaign.json          CampaignBead — multi-milestone progress
  graph/<node-id>.json   GraphNode — DAG execution state
  research/<node-id>.md  research findings
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

## Dependencies

- `pydantic>=2.0`
