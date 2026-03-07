"""BeadStore tests for FindingBead, CycleBead, ProposalBead, and SuppressionBead.

Covers write/read/list round-trips for all four types using a temporary
directory, plus list_active_suppressions and list_suppressions filtering.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from beads import (
    CycleBead,
    FindingBead,
    ProposalBead,
    SuppressionBead,
)
from beads.store import BeadStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_finding(**kwargs) -> FindingBead:
    defaults: dict = dict(
        id="f-001",
        agent="repo-audit",
        timestamp=datetime.now(UTC),
        staleness_class="structural",
        confidence=0.85,
        evidence_chain=["README declares X", "X not found in AST"],
        reasoning="Gap between docs and code",
        severity="high",
        blast_radius={"modules_affected": ["executor.py"], "centrality": 0.7},
        repo="bread-forge/kiln",
        cycle_id="cycle-001",
    )
    defaults.update(kwargs)
    return FindingBead(**defaults)


def make_cycle(**kwargs) -> CycleBead:
    defaults: dict = dict(cycle_id="cycle-001", repo="bread-forge/kiln")
    defaults.update(kwargs)
    return CycleBead(**defaults)


def make_proposal(**kwargs) -> ProposalBead:
    defaults: dict = dict(
        proposal_id="prop-001",
        cycle_id="cycle-001",
        repo="bread-forge/kiln",
        spec_hash="abc123",
        spec_path="/tmp/spec.md",
    )
    defaults.update(kwargs)
    return ProposalBead(**defaults)


def make_suppression(**kwargs) -> SuppressionBead:
    defaults: dict = dict(
        suppression_id="sup-001",
        finding_class="repo-audit.integration-gap.executor",
        decision="deferred",
        reason="waiting for v0.2",
        created_by="human:bread",
    )
    defaults.update(kwargs)
    return SuppressionBead(**defaults)


@pytest.fixture
def store(tmp_path: Path) -> BeadStore:
    return BeadStore(beads_dir=tmp_path, repo="bread-forge/kiln")


# ---------------------------------------------------------------------------
# BeadStore — FindingBead
# ---------------------------------------------------------------------------


class TestBeadStoreFinding:
    def test_write_read_round_trip(self, store: BeadStore) -> None:
        f = make_finding()
        store.write_finding(f)
        f2 = store.read_finding("f-001")
        assert f2 is not None
        assert f2.id == f.id
        assert f2.agent == f.agent
        assert f2.blast_radius == f.blast_radius
        assert f2.evidence_chain == f.evidence_chain

    def test_read_missing_returns_none(self, store: BeadStore) -> None:
        assert store.read_finding("no-such-finding") is None

    def test_overwrite_replaces_record(self, store: BeadStore) -> None:
        store.write_finding(make_finding(severity="high"))
        store.write_finding(make_finding(severity="low"))
        f2 = store.read_finding("f-001")
        assert f2 is not None
        assert f2.severity == "low"

    def test_list_findings_empty(self, store: BeadStore) -> None:
        assert store.list_findings() == []

    def test_list_findings_all(self, store: BeadStore) -> None:
        store.write_finding(make_finding(id="f-001"))
        store.write_finding(make_finding(id="f-002"))
        findings = store.list_findings()
        assert len(findings) == 2
        ids = {f.id for f in findings}
        assert ids == {"f-001", "f-002"}

    def test_list_findings_filter_repo(self, store: BeadStore) -> None:
        store.write_finding(make_finding(id="f-001", repo="bread-forge/kiln"))
        store.write_finding(make_finding(id="f-002", repo="bread-forge/other"))
        findings = store.list_findings(repo="bread-forge/kiln")
        assert len(findings) == 1
        assert findings[0].id == "f-001"

    def test_list_findings_filter_repo_no_match(self, store: BeadStore) -> None:
        store.write_finding(make_finding(id="f-001", repo="bread-forge/kiln"))
        findings = store.list_findings(repo="bread-forge/nonexistent")
        assert findings == []


# ---------------------------------------------------------------------------
# BeadStore — CycleBead
# ---------------------------------------------------------------------------


class TestBeadStoreCycle:
    def test_write_read_round_trip(self, store: BeadStore) -> None:
        c = make_cycle()
        store.write_cycle(c)
        c2 = store.read_cycle("cycle-001")
        assert c2 is not None
        assert c2.cycle_id == c.cycle_id
        assert c2.repo == c.repo
        assert c2.phase == c.phase

    def test_read_missing_returns_none(self, store: BeadStore) -> None:
        assert store.read_cycle("no-such-cycle") is None

    def test_write_touches_updated_at(self, store: BeadStore) -> None:
        c = make_cycle()
        before = c.updated_at
        store.write_cycle(c)
        c2 = store.read_cycle("cycle-001")
        assert c2 is not None
        assert c2.updated_at >= before

    def test_list_cycles_empty(self, store: BeadStore) -> None:
        assert store.list_cycles() == []

    def test_list_cycles_all(self, store: BeadStore) -> None:
        store.write_cycle(make_cycle(cycle_id="c-001"))
        store.write_cycle(make_cycle(cycle_id="c-002"))
        cycles = store.list_cycles()
        assert len(cycles) == 2
        ids = {c.cycle_id for c in cycles}
        assert ids == {"c-001", "c-002"}

    def test_list_cycles_filter_repo(self, store: BeadStore) -> None:
        store.write_cycle(make_cycle(cycle_id="c-001", repo="bread-forge/kiln"))
        store.write_cycle(make_cycle(cycle_id="c-002", repo="bread-forge/other"))
        cycles = store.list_cycles(repo="bread-forge/kiln")
        assert len(cycles) == 1
        assert cycles[0].cycle_id == "c-001"

    def test_list_cycles_filter_phase(self, store: BeadStore) -> None:
        store.write_cycle(make_cycle(cycle_id="c-001", phase="analysis"))
        store.write_cycle(make_cycle(cycle_id="c-002", phase="synthesis"))
        store.write_cycle(make_cycle(cycle_id="c-003", phase="analysis"))
        analysis = store.list_cycles(phase="analysis")
        assert len(analysis) == 2
        ids = {c.cycle_id for c in analysis}
        assert ids == {"c-001", "c-003"}

    def test_list_cycles_filter_repo_and_phase(self, store: BeadStore) -> None:
        store.write_cycle(make_cycle(cycle_id="c-001", repo="bread-forge/kiln", phase="analysis"))
        store.write_cycle(make_cycle(cycle_id="c-002", repo="bread-forge/kiln", phase="complete"))
        store.write_cycle(make_cycle(cycle_id="c-003", repo="bread-forge/other", phase="analysis"))
        result = store.list_cycles(repo="bread-forge/kiln", phase="analysis")
        assert len(result) == 1
        assert result[0].cycle_id == "c-001"

    def test_list_cycles_filter_no_match(self, store: BeadStore) -> None:
        store.write_cycle(make_cycle(cycle_id="c-001", phase="analysis"))
        assert store.list_cycles(phase="complete") == []


# ---------------------------------------------------------------------------
# BeadStore — ProposalBead
# ---------------------------------------------------------------------------


class TestBeadStoreProposal:
    def test_write_read_round_trip(self, store: BeadStore) -> None:
        p = make_proposal()
        store.write_proposal(p)
        p2 = store.read_proposal("prop-001")
        assert p2 is not None
        assert p2.proposal_id == p.proposal_id
        assert p2.spec_hash == p.spec_hash
        assert p2.status == p.status

    def test_read_missing_returns_none(self, store: BeadStore) -> None:
        assert store.read_proposal("no-such-proposal") is None

    def test_overwrite_updates_status(self, store: BeadStore) -> None:
        store.write_proposal(make_proposal(status="pending"))
        store.write_proposal(make_proposal(status="approved"))
        p2 = store.read_proposal("prop-001")
        assert p2 is not None
        assert p2.status == "approved"

    def test_list_proposals_empty(self, store: BeadStore) -> None:
        assert store.list_proposals() == []

    def test_list_proposals_all(self, store: BeadStore) -> None:
        store.write_proposal(make_proposal(proposal_id="p-001"))
        store.write_proposal(make_proposal(proposal_id="p-002"))
        proposals = store.list_proposals()
        assert len(proposals) == 2
        ids = {p.proposal_id for p in proposals}
        assert ids == {"p-001", "p-002"}

    def test_list_proposals_filter_status(self, store: BeadStore) -> None:
        store.write_proposal(make_proposal(proposal_id="p-001", status="pending"))
        store.write_proposal(make_proposal(proposal_id="p-002", status="approved"))
        store.write_proposal(make_proposal(proposal_id="p-003", status="pending"))
        pending = store.list_proposals(status="pending")
        assert len(pending) == 2
        ids = {p.proposal_id for p in pending}
        assert ids == {"p-001", "p-003"}

    def test_list_proposals_filter_repo(self, store: BeadStore) -> None:
        store.write_proposal(make_proposal(proposal_id="p-001", repo="bread-forge/kiln"))
        store.write_proposal(make_proposal(proposal_id="p-002", repo="bread-forge/other"))
        proposals = store.list_proposals(repo="bread-forge/kiln")
        assert len(proposals) == 1
        assert proposals[0].proposal_id == "p-001"

    def test_list_proposals_filter_repo_and_status(self, store: BeadStore) -> None:
        store.write_proposal(
            make_proposal(proposal_id="p-001", repo="bread-forge/kiln", status="pending")
        )
        store.write_proposal(
            make_proposal(proposal_id="p-002", repo="bread-forge/kiln", status="approved")
        )
        store.write_proposal(
            make_proposal(proposal_id="p-003", repo="bread-forge/other", status="pending")
        )
        result = store.list_proposals(repo="bread-forge/kiln", status="pending")
        assert len(result) == 1
        assert result[0].proposal_id == "p-001"

    def test_list_proposals_filter_no_match(self, store: BeadStore) -> None:
        store.write_proposal(make_proposal(proposal_id="p-001", status="pending"))
        assert store.list_proposals(status="verified") == []


# ---------------------------------------------------------------------------
# BeadStore — SuppressionBead
# ---------------------------------------------------------------------------


class TestBeadStoreSuppression:
    def test_write_read_round_trip(self, store: BeadStore) -> None:
        s = make_suppression()
        store.write_suppression(s)
        s2 = store.read_suppression("sup-001")
        assert s2 is not None
        assert s2.suppression_id == s.suppression_id
        assert s2.finding_class == s.finding_class
        assert s2.decision == s.decision

    def test_read_missing_returns_none(self, store: BeadStore) -> None:
        assert store.read_suppression("no-such-suppression") is None

    def test_overwrite_updates_record(self, store: BeadStore) -> None:
        store.write_suppression(make_suppression(decision="deferred"))
        store.write_suppression(make_suppression(decision="rejected"))
        s2 = store.read_suppression("sup-001")
        assert s2 is not None
        assert s2.decision == "rejected"

    def test_list_suppressions_empty(self, store: BeadStore) -> None:
        assert store.list_suppressions() == []

    def test_list_suppressions_all(self, store: BeadStore) -> None:
        store.write_suppression(make_suppression(suppression_id="s-001"))
        store.write_suppression(make_suppression(suppression_id="s-002"))
        suppressions = store.list_suppressions()
        assert len(suppressions) == 2
        ids = {s.suppression_id for s in suppressions}
        assert ids == {"s-001", "s-002"}

    def test_list_suppressions_filter_finding_class(self, store: BeadStore) -> None:
        store.write_suppression(
            make_suppression(
                suppression_id="s-001",
                finding_class="repo-audit.integration-gap.executor",
            )
        )
        store.write_suppression(
            make_suppression(
                suppression_id="s-002",
                finding_class="repo-audit.missing-test.runner",
            )
        )
        result = store.list_suppressions(finding_class="repo-audit.integration-gap.executor")
        assert len(result) == 1
        assert result[0].suppression_id == "s-001"

    def test_list_suppressions_filter_no_match(self, store: BeadStore) -> None:
        store.write_suppression(make_suppression(finding_class="repo-audit.gap.foo"))
        assert store.list_suppressions(finding_class="other.class") == []

    def test_list_active_suppressions_empty(self, store: BeadStore) -> None:
        assert store.list_active_suppressions() == []

    def test_list_active_suppressions_permanent(self, store: BeadStore) -> None:
        """Permanent suppressions (no expiry) are always included."""
        store.write_suppression(make_suppression(suppression_id="s-001", expires_at=None))
        active = store.list_active_suppressions()
        assert len(active) == 1
        assert active[0].suppression_id == "s-001"

    def test_list_active_suppressions_future_expiry(self, store: BeadStore) -> None:
        store.write_suppression(
            make_suppression(
                suppression_id="s-001",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        active = store.list_active_suppressions()
        assert len(active) == 1

    def test_list_active_suppressions_filters_expired(self, store: BeadStore) -> None:
        store.write_suppression(make_suppression(suppression_id="s-active", expires_at=None))
        store.write_suppression(
            make_suppression(
                suppression_id="s-expired",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        active = store.list_active_suppressions()
        assert len(active) == 1
        assert active[0].suppression_id == "s-active"

    def test_list_active_suppressions_all_expired(self, store: BeadStore) -> None:
        store.write_suppression(
            make_suppression(
                suppression_id="s-001",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        assert store.list_active_suppressions() == []

    def test_list_active_suppressions_mixed(self, store: BeadStore) -> None:
        """Permanent + future-expiry included; past-expiry excluded."""
        store.write_suppression(make_suppression(suppression_id="s-permanent", expires_at=None))
        store.write_suppression(
            make_suppression(
                suppression_id="s-future",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        store.write_suppression(
            make_suppression(
                suppression_id="s-past",
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        active = store.list_active_suppressions()
        assert len(active) == 2
        ids = {s.suppression_id for s in active}
        assert ids == {"s-permanent", "s-future"}
