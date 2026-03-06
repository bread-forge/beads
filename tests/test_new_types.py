"""Tests for FindingBead, CycleBead, ProposalBead, SuppressionBead."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

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
    defaults = dict(
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
    defaults = dict(cycle_id="cycle-001", repo="bread-forge/kiln")
    defaults.update(kwargs)
    return CycleBead(**defaults)


def make_proposal(**kwargs) -> ProposalBead:
    defaults = dict(
        proposal_id="prop-001",
        cycle_id="cycle-001",
        repo="bread-forge/kiln",
        spec_hash="abc123",
        spec_path="/tmp/spec.md",
    )
    defaults.update(kwargs)
    return ProposalBead(**defaults)


def make_suppression(**kwargs) -> SuppressionBead:
    defaults = dict(
        suppression_id="sup-001",
        finding_class="repo-audit.integration-gap.executor",
        decision="deferred",
        reason="waiting for v0.2",
        created_by="human:bread",
    )
    defaults.update(kwargs)
    return SuppressionBead(**defaults)


@pytest.fixture
def store() -> BeadStore:
    with tempfile.TemporaryDirectory() as tmp:
        yield BeadStore(beads_dir=Path(tmp), repo="bread-forge/kiln")


# ---------------------------------------------------------------------------
# FindingBead
# ---------------------------------------------------------------------------


class TestFindingBead:
    def test_instantiate(self):
        f = make_finding()
        assert f.id == "f-001"
        assert f.staleness_class == "structural"
        assert f.confidence == 0.85
        assert f.severity == "high"

    def test_round_trip(self):
        f = make_finding()
        data = f.model_dump()
        f2 = FindingBead.model_validate(data)
        assert f2.id == f.id
        assert f2.blast_radius == f.blast_radius
        assert f2.evidence_chain == f.evidence_chain

    def test_optional_fields_default_none(self):
        f = make_finding()
        assert f.reasoning_extended is None
        assert f.remediation_sketch is None
        assert f.enrichment_cost_usd is None

    def test_optional_fields_set(self):
        f = make_finding(
            reasoning_extended="extended", remediation_sketch="fix it", enrichment_cost_usd=0.05
        )
        assert f.reasoning_extended == "extended"
        assert f.remediation_sketch == "fix it"
        assert f.enrichment_cost_usd == 0.05

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            make_finding(confidence=1.5)
        with pytest.raises(ValidationError):
            make_finding(confidence=-0.1)

    def test_staleness_class_literal(self):
        for cls in ("critical", "dependency", "structural", "architectural"):
            f = make_finding(staleness_class=cls)
            assert f.staleness_class == cls

    def test_severity_literal(self):
        for sev in ("critical", "high", "medium", "low"):
            f = make_finding(severity=sev)
            assert f.severity == sev


# ---------------------------------------------------------------------------
# CycleBead
# ---------------------------------------------------------------------------


class TestCycleBead:
    def test_instantiate(self):
        c = make_cycle()
        assert c.cycle_id == "cycle-001"
        assert c.phase == "analysis"
        assert c.finding_count == 0
        assert c.proposal_count == 0
        assert c.total_cost_usd == 0.0

    def test_round_trip(self):
        c = make_cycle()
        data = c.model_dump()
        c2 = CycleBead.model_validate(data)
        assert c2.cycle_id == c.cycle_id
        assert c2.phase == c.phase

    def test_all_phases(self):
        for phase in ("analysis", "synthesis", "gate", "execution", "verification", "complete"):
            c = make_cycle(phase=phase)
            assert c.phase == phase

    def test_touch_updates_updated_at(self):
        c = make_cycle()
        before = c.updated_at
        c.touch()
        assert c.updated_at >= before

    def test_optional_fields(self):
        c = make_cycle(trigger="manual", completed_at=datetime.now(UTC))
        assert c.trigger == "manual"
        assert c.completed_at is not None


# ---------------------------------------------------------------------------
# ProposalBead
# ---------------------------------------------------------------------------


class TestProposalBead:
    def test_instantiate(self):
        p = make_proposal()
        assert p.proposal_id == "prop-001"
        assert p.status == "pending"

    def test_round_trip(self):
        p = make_proposal()
        data = p.model_dump()
        p2 = ProposalBead.model_validate(data)
        assert p2.proposal_id == p.proposal_id
        assert p2.status == p.status

    def test_all_statuses(self):
        for status in (
            "pending",
            "approved",
            "rejected",
            "deferred",
            "dispatched",
            "verified",
            "failed",
        ):
            p = make_proposal(status=status)
            assert p.status == status

    def test_touch_updates_updated_at(self):
        p = make_proposal()
        before = p.updated_at
        p.touch()
        assert p.updated_at >= before

    def test_optional_fields(self):
        now = datetime.now(UTC)
        p = make_proposal(
            gate_decision_at=now,
            decision_by="human:bread",
            human_diff_hash="deadbeef",
            review_seconds=42.5,
        )
        assert p.gate_decision_at == now
        assert p.decision_by == "human:bread"
        assert p.human_diff_hash == "deadbeef"
        assert p.review_seconds == 42.5


# ---------------------------------------------------------------------------
# SuppressionBead
# ---------------------------------------------------------------------------


class TestSuppressionBead:
    def test_instantiate(self):
        s = make_suppression()
        assert s.suppression_id == "sup-001"
        assert s.decision == "deferred"
        assert s.expires_at is None

    def test_round_trip(self):
        s = make_suppression()
        data = s.model_dump()
        s2 = SuppressionBead.model_validate(data)
        assert s2.suppression_id == s.suppression_id
        assert s2.is_active() == s.is_active()

    def test_is_active_permanent(self):
        s = make_suppression(expires_at=None)
        assert s.is_active() is True

    def test_is_active_future_expiry(self):
        s = make_suppression(expires_at=datetime.now(UTC) + timedelta(days=7))
        assert s.is_active() is True

    def test_is_active_past_expiry(self):
        s = make_suppression(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        assert s.is_active() is False

    def test_decision_literal(self):
        for decision in ("rejected", "deferred"):
            s = make_suppression(decision=decision)
            assert s.decision == decision

    def test_conditions_optional(self):
        s = make_suppression(conditions="Re-surface if: integration tests exist")
        assert s.conditions == "Re-surface if: integration tests exist"


# ---------------------------------------------------------------------------
# BeadStore — FindingBead
# ---------------------------------------------------------------------------


class TestBeadStoreFinding:
    def test_write_read_round_trip(self, store):
        f = make_finding()
        store.write_finding(f)
        f2 = store.read_finding("f-001")
        assert f2 is not None
        assert f2.id == f.id
        assert f2.agent == f.agent
        assert f2.blast_radius == f.blast_radius

    def test_read_missing_returns_none(self, store):
        assert store.read_finding("no-such-finding") is None

    def test_list_findings_all(self, store):
        store.write_finding(make_finding(id="f-001"))
        store.write_finding(make_finding(id="f-002"))
        findings = store.list_findings()
        assert len(findings) == 2

    def test_list_findings_filter_repo(self, store):
        store.write_finding(make_finding(id="f-001", repo="bread-forge/kiln"))
        store.write_finding(make_finding(id="f-002", repo="bread-forge/other"))
        findings = store.list_findings(repo="bread-forge/kiln")
        assert len(findings) == 1
        assert findings[0].id == "f-001"


# ---------------------------------------------------------------------------
# BeadStore — CycleBead
# ---------------------------------------------------------------------------


class TestBeadStoreCycle:
    def test_write_read_round_trip(self, store):
        c = make_cycle()
        store.write_cycle(c)
        c2 = store.read_cycle("cycle-001")
        assert c2 is not None
        assert c2.cycle_id == c.cycle_id
        assert c2.repo == c.repo

    def test_read_missing_returns_none(self, store):
        assert store.read_cycle("no-such-cycle") is None

    def test_write_updates_updated_at(self, store):
        c = make_cycle()
        before = c.updated_at
        store.write_cycle(c)
        c2 = store.read_cycle("cycle-001")
        assert c2.updated_at >= before


# ---------------------------------------------------------------------------
# BeadStore — ProposalBead
# ---------------------------------------------------------------------------


class TestBeadStoreProposal:
    def test_write_read_round_trip(self, store):
        p = make_proposal()
        store.write_proposal(p)
        p2 = store.read_proposal("prop-001")
        assert p2 is not None
        assert p2.proposal_id == p.proposal_id

    def test_read_missing_returns_none(self, store):
        assert store.read_proposal("no-such-proposal") is None

    def test_list_proposals_all(self, store):
        store.write_proposal(make_proposal(proposal_id="p-001"))
        store.write_proposal(make_proposal(proposal_id="p-002"))
        proposals = store.list_proposals()
        assert len(proposals) == 2

    def test_list_proposals_filter_status(self, store):
        store.write_proposal(make_proposal(proposal_id="p-001", status="pending"))
        store.write_proposal(make_proposal(proposal_id="p-002", status="approved"))
        store.write_proposal(make_proposal(proposal_id="p-003", status="pending"))
        pending = store.list_proposals(status="pending")
        assert len(pending) == 2
        approved = store.list_proposals(status="approved")
        assert len(approved) == 1
        assert approved[0].proposal_id == "p-002"

    def test_list_proposals_filter_repo(self, store):
        store.write_proposal(make_proposal(proposal_id="p-001", repo="bread-forge/kiln"))
        store.write_proposal(make_proposal(proposal_id="p-002", repo="bread-forge/other"))
        proposals = store.list_proposals(repo="bread-forge/kiln")
        assert len(proposals) == 1

    def test_list_proposals_filter_repo_and_status(self, store):
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


# ---------------------------------------------------------------------------
# BeadStore — SuppressionBead
# ---------------------------------------------------------------------------


class TestBeadStoreSuppression:
    def test_write_read_round_trip(self, store):
        s = make_suppression()
        store.write_suppression(s)
        s2 = store.read_suppression("sup-001")
        assert s2 is not None
        assert s2.suppression_id == s.suppression_id

    def test_read_missing_returns_none(self, store):
        assert store.read_suppression("no-such-suppression") is None

    def test_list_active_suppressions_all_active(self, store):
        store.write_suppression(make_suppression(suppression_id="s-001"))
        store.write_suppression(
            make_suppression(
                suppression_id="s-002", expires_at=datetime.now(UTC) + timedelta(days=1)
            )
        )
        active = store.list_active_suppressions()
        assert len(active) == 2

    def test_list_active_suppressions_filters_expired(self, store):
        store.write_suppression(make_suppression(suppression_id="s-active"))
        store.write_suppression(
            make_suppression(
                suppression_id="s-expired",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        active = store.list_active_suppressions()
        assert len(active) == 1
        assert active[0].suppression_id == "s-active"

    def test_list_active_suppressions_empty(self, store):
        assert store.list_active_suppressions() == []

    def test_list_active_suppressions_all_expired(self, store):
        store.write_suppression(
            make_suppression(
                suppression_id="s-001",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        active = store.list_active_suppressions()
        assert active == []
