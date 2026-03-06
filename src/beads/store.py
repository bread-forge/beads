"""BeadStore — atomic reads/writes for all bead types.

Layout:
  ~/.kiln/beads/<owner>/<repo>/work/<N>.json       WorkBead
  ~/.kiln/beads/<owner>/<repo>/prs/pr-<N>.json     PRBead
  ~/.kiln/beads/<owner>/<repo>/merge-queue.json    MergeQueue
  ~/.kiln/beads/<owner>/<repo>/campaign.json       CampaignBead
  ~/.kiln/beads/<owner>/<repo>/graph/<node-id>.json  GraphNode
  ~/.kiln/beads/<owner>/<repo>/research/<node-id>.md findings

All writes use write-to-tmp + os.replace (atomic on POSIX).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from beads.types import (
    CampaignBead,
    CycleBead,
    FindingBead,
    GraphNode,
    MergeQueue,
    MergeQueueItem,
    NodeState,
    NodeType,
    PRBead,
    ProposalBead,
    PRState,
    SuppressionBead,
    WorkBead,
    WorkState,
)


class BeadStore:
    """Atomic bead reads/writes using write-to-tmp + os.replace."""

    def __init__(self, beads_dir: Path, repo: str) -> None:
        owner, name = repo.split("/", 1)
        self._root = beads_dir / owner / name
        self._work_dir = self._root / "work"
        self._prs_dir = self._root / "prs"
        self._graph_dir = self._root / "graph"
        self._research_dir = self._root / "research"
        self._findings_dir = self._root / "findings"
        self._cycles_dir = self._root / "cycles"
        self._proposals_dir = self._root / "proposals"
        self._suppressions_dir = self._root / "suppressions"
        self._root.mkdir(parents=True, exist_ok=True)
        self._work_dir.mkdir(exist_ok=True)
        self._prs_dir.mkdir(exist_ok=True)
        self._graph_dir.mkdir(exist_ok=True)
        self._research_dir.mkdir(exist_ok=True)
        self._findings_dir.mkdir(exist_ok=True)
        self._cycles_dir.mkdir(exist_ok=True)
        self._proposals_dir.mkdir(exist_ok=True)
        self._suppressions_dir.mkdir(exist_ok=True)

    # --- Work beads ---

    def _work_path(self, issue_number: int) -> Path:
        return self._work_dir / f"{issue_number}.json"

    def write_work_bead(self, bead: WorkBead) -> None:
        bead.touch()
        self._atomic_write(self._work_path(bead.issue_number), bead.model_dump(mode="json"))

    def read_work_bead(self, issue_number: int) -> WorkBead | None:
        path = self._work_path(issue_number)
        if not path.exists():
            return None
        return WorkBead.model_validate(self._read_json(path))

    def list_work_beads(
        self,
        state: WorkState | None = None,
        milestone: str | None = None,
    ) -> list[WorkBead]:
        beads = []
        for p in self._work_dir.glob("*.json"):
            try:
                b = WorkBead.model_validate(self._read_json(p))
                if state and b.state != state:
                    continue
                if milestone and b.milestone != milestone:
                    continue
                beads.append(b)
            except Exception:
                pass
        return beads

    # --- PR beads ---

    def _pr_path(self, pr_number: int) -> Path:
        return self._prs_dir / f"pr-{pr_number}.json"

    def write_pr_bead(self, bead: PRBead) -> None:
        bead.touch()
        self._atomic_write(self._pr_path(bead.pr_number), bead.model_dump(mode="json"))

    def read_pr_bead(self, pr_number: int) -> PRBead | None:
        path = self._pr_path(pr_number)
        if not path.exists():
            return None
        return PRBead.model_validate(self._read_json(path))

    def list_pr_beads(self, state: PRState | None = None) -> list[PRBead]:
        beads = []
        for p in self._prs_dir.glob("pr-*.json"):
            try:
                b = PRBead.model_validate(self._read_json(p))
                if state and b.state != state:
                    continue
                beads.append(b)
            except Exception:
                pass
        return beads

    # --- Merge queue ---

    def _mq_path(self) -> Path:
        return self._root / "merge-queue.json"

    def read_merge_queue(self) -> MergeQueue:
        path = self._mq_path()
        if not path.exists():
            repo = str(self._root.parent.name) + "/" + str(self._root.name)
            return MergeQueue(repo=repo)
        return MergeQueue.model_validate(self._read_json(path))

    def write_merge_queue(self, queue: MergeQueue) -> None:
        self._atomic_write(self._mq_path(), queue.model_dump(mode="json"))

    def enqueue_merge(self, item: MergeQueueItem) -> None:
        q = self.read_merge_queue()
        q.enqueue(item)
        self.write_merge_queue(q)

    # --- Campaign bead ---

    def _campaign_path(self) -> Path:
        return self._root / "campaign.json"

    def read_campaign_bead(self) -> CampaignBead | None:
        path = self._campaign_path()
        if not path.exists():
            return None
        return CampaignBead.model_validate(self._read_json(path))

    def write_campaign_bead(self, bead: CampaignBead) -> None:
        bead.touch()
        self._atomic_write(self._campaign_path(), bead.model_dump(mode="json"))

    # --- Graph nodes ---

    def _node_path(self, node_id: str) -> Path:
        return self._graph_dir / f"{node_id}.json"

    def write_node(self, node: GraphNode) -> None:
        self._atomic_write(self._node_path(node.id), node.model_dump(mode="json"))

    def claim_node(self, node: GraphNode) -> bool:
        """Atomically transition a node from pending → running on disk.

        Uses fcntl.flock to serialize concurrent claimants (multiple executor
        instances or a running executor + manual dispatch).  Returns True if the
        claim succeeded (node was pending on disk and is now written as running).
        Returns False if the node was already claimed by another process.
        """
        import fcntl

        path = self._node_path(node.id)
        lock_path = path.with_suffix(".lock")
        lock_path.touch()
        with lock_path.open() as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                if not path.exists():
                    # Node not yet on disk — newly created in-memory; write it directly.
                    self._atomic_write(path, node.model_dump(mode="json"))
                    return True
                on_disk = self._read_json(path)
                if on_disk.get("state") != "pending":
                    return False  # already claimed by another process
                self._atomic_write(path, node.model_dump(mode="json"))
                return True
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def read_node(self, node_id: str) -> GraphNode | None:
        path = self._node_path(node_id)
        if not path.exists():
            return None
        return GraphNode.model_validate(self._read_json(path))

    def list_nodes(
        self,
        type: NodeType | None = None,
        state: NodeState | None = None,
    ) -> list[GraphNode]:
        nodes = []
        for p in self._graph_dir.glob("*.json"):
            try:
                n = GraphNode.model_validate(self._read_json(p))
                if type and n.type != type:
                    continue
                if state and n.state != state:
                    continue
                nodes.append(n)
            except Exception:
                pass
        return nodes

    # --- Research findings ---

    def store_research_findings(self, node_id: str, markdown: str) -> Path:
        """Write research findings markdown. Returns path written."""
        path = self._research_dir / f"{node_id}.md"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(markdown, encoding="utf-8")
        os.replace(tmp, path)
        return path

    def read_research_findings(self, node_id: str) -> str | None:
        path = self._research_dir / f"{node_id}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    # --- Findings ---

    def write_finding(self, finding: FindingBead) -> None:
        path = self._findings_dir / f"{finding.id}.json"
        self._atomic_write(path, finding.model_dump(mode="json"))

    def read_finding(self, finding_id: str) -> FindingBead | None:
        path = self._findings_dir / f"{finding_id}.json"
        if not path.exists():
            return None
        return FindingBead.model_validate(self._read_json(path))

    def list_findings(self, repo: str | None = None) -> list[FindingBead]:
        findings = []
        for p in self._findings_dir.glob("*.json"):
            try:
                f = FindingBead.model_validate(self._read_json(p))
                if repo and f.repo != repo:
                    continue
                findings.append(f)
            except Exception:
                pass
        return findings

    # --- Cycles ---

    def write_cycle(self, cycle: CycleBead) -> None:
        cycle.touch()
        path = self._cycles_dir / f"{cycle.cycle_id}.json"
        self._atomic_write(path, cycle.model_dump(mode="json"))

    def read_cycle(self, cycle_id: str) -> CycleBead | None:
        path = self._cycles_dir / f"{cycle_id}.json"
        if not path.exists():
            return None
        return CycleBead.model_validate(self._read_json(path))

    # --- Proposals ---

    def write_proposal(self, proposal: ProposalBead) -> None:
        proposal.touch()
        path = self._proposals_dir / f"{proposal.proposal_id}.json"
        self._atomic_write(path, proposal.model_dump(mode="json"))

    def read_proposal(self, proposal_id: str) -> ProposalBead | None:
        path = self._proposals_dir / f"{proposal_id}.json"
        if not path.exists():
            return None
        return ProposalBead.model_validate(self._read_json(path))

    def list_proposals(
        self,
        repo: str | None = None,
        status: str | None = None,
    ) -> list[ProposalBead]:
        proposals = []
        for p in self._proposals_dir.glob("*.json"):
            try:
                proposal = ProposalBead.model_validate(self._read_json(p))
                if repo and proposal.repo != repo:
                    continue
                if status and proposal.status != status:
                    continue
                proposals.append(proposal)
            except Exception:
                pass
        return proposals

    # --- Suppressions ---

    def write_suppression(self, suppression: SuppressionBead) -> None:
        path = self._suppressions_dir / f"{suppression.suppression_id}.json"
        self._atomic_write(path, suppression.model_dump(mode="json"))

    def read_suppression(self, suppression_id: str) -> SuppressionBead | None:
        path = self._suppressions_dir / f"{suppression_id}.json"
        if not path.exists():
            return None
        return SuppressionBead.model_validate(self._read_json(path))

    def list_active_suppressions(self, repo: str | None = None) -> list[SuppressionBead]:
        suppressions = []
        for p in self._suppressions_dir.glob("*.json"):
            try:
                s = SuppressionBead.model_validate(self._read_json(p))
                if not s.is_active():
                    continue
                suppressions.append(s)
            except Exception:
                pass
        return suppressions

    # --- Internal helpers ---

    def _atomic_write(self, path: Path, data: dict) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))
