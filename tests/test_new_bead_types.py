"""Unit tests for FindingBead, CycleBead, ProposalBead, and SuppressionBead.

Covers instantiation, JSON round-trip, and SuppressionBead.is_active() for
both expired and active cases.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from beads import (
    CycleBead,
    FindingBead,
    ProposalBead,
    SuppressionBead,
)

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


# ---------------------------------------------------------------------------
# FindingBead
# ---------------------------------------------------------------------------


class TestFindingBead:
    def test_instantiate_required_fields(self) -> None:
        f = make_finding()
        assert f.id == "f-001"
        assert f.agent == "repo-audit"
        assert f.staleness_class == "structural"
        assert f.confidence == 0.85
        assert f.severity == "high"
        assert f.repo == "bread-forge/kiln"
        assert f.cycle_id == "cycle-001"

    def test_json_round_trip(self) -> None:
        f = make_finding()
        data = f.model_dump(mode="json")
        f2 = FindingBead.model_validate(data)
        assert f2.id == f.id
        assert f2.agent == f.agent
        assert f2.staleness_class == f.staleness_class
        assert f2.confidence == f.confidence
        assert f2.severity == f.severity
        assert f2.blast_radius == f.blast_radius
        assert f2.evidence_chain == f.evidence_chain
        assert f2.repo == f.repo
        assert f2.cycle_id == f.cycle_id

    def test_evidence_chain_preserved(self) -> None:
        f = make_finding(evidence_chain=["a", "b", "c"])
        data = f.model_dump(mode="json")
        f2 = FindingBead.model_validate(data)
        assert f2.evidence_chain == ["a", "b", "c"]

    def test_blast_radius_preserved(self) -> None:
        blast = {"modules_affected": ["foo.py", "bar.py"], "centrality": 0.9}
        f = make_finding(blast_radius=blast)
        data = f.model_dump(mode="json")
        f2 = FindingBead.model_validate(data)
        assert f2.blast_radius == blast

    def test_optional_fields_default_none(self) -> None:
        f = make_finding()
        assert f.reasoning_extended is None
        assert f.remediation_sketch is None
        assert f.enrichment_cost_usd is None

    def test_optional_fields_set(self) -> None:
        f = make_finding(
            reasoning_extended="deep reasoning",
            remediation_sketch="add missing test",
            enrichment_cost_usd=0.05,
        )
        assert f.reasoning_extended == "deep reasoning"
        assert f.remediation_sketch == "add missing test"
        assert f.enrichment_cost_usd == 0.05

    def test_optional_fields_round_trip(self) -> None:
        f = make_finding(reasoning_extended="extended", enrichment_cost_usd=0.10)
        data = f.model_dump(mode="json")
        f2 = FindingBead.model_validate(data)
        assert f2.reasoning_extended == "extended"
        assert f2.enrichment_cost_usd == 0.10

    def test_confidence_upper_bound_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(confidence=1.01)

    def test_confidence_lower_bound_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(confidence=-0.01)

    def test_confidence_boundary_values_accepted(self) -> None:
        assert make_finding(confidence=0.0).confidence == 0.0
        assert make_finding(confidence=1.0).confidence == 1.0

    def test_all_staleness_classes(self) -> None:
        for cls in ("critical", "dependency", "structural", "architectural"):
            f = make_finding(staleness_class=cls)
            assert f.staleness_class == cls

    def test_invalid_staleness_class_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(staleness_class="unknown")

    def test_all_severity_levels(self) -> None:
        for sev in ("critical", "high", "medium", "low"):
            f = make_finding(severity=sev)
            assert f.severity == sev

    def test_invalid_severity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(severity="info")

    def test_empty_evidence_chain(self) -> None:
        f = make_finding(evidence_chain=[])
        assert f.evidence_chain == []


# ---------------------------------------------------------------------------
# CycleBead
# ---------------------------------------------------------------------------


class TestCycleBead:
    def test_instantiate_defaults(self) -> None:
        c = make_cycle()
        assert c.cycle_id == "cycle-001"
        assert c.repo == "bread-forge/kiln"
        assert c.phase == "analysis"
        assert c.finding_count == 0
        assert c.proposal_count == 0
        assert c.total_cost_usd == 0.0
        assert c.trigger is None
        assert c.completed_at is None

    def test_json_round_trip(self) -> None:
        c = make_cycle(phase="synthesis", finding_count=5, total_cost_usd=0.25)
        data = c.model_dump(mode="json")
        c2 = CycleBead.model_validate(data)
        assert c2.cycle_id == c.cycle_id
        assert c2.repo == c.repo
        assert c2.phase == c.phase
        assert c2.finding_count == c.finding_count
        assert c2.total_cost_usd == c.total_cost_usd

    def test_all_phases(self) -> None:
        for phase in ("analysis", "synthesis", "gate", "execution", "verification", "complete"):
            c = make_cycle(phase=phase)
            assert c.phase == phase

    def test_invalid_phase_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_cycle(phase="unknown-phase")

    def test_touch_updates_updated_at(self) -> None:
        c = make_cycle()
        before = c.updated_at
        c.touch()
        assert c.updated_at >= before

    def test_optional_trigger(self) -> None:
        c = make_cycle(trigger="manual-push")
        assert c.trigger == "manual-push"
        data = c.model_dump(mode="json")
        c2 = CycleBead.model_validate(data)
        assert c2.trigger == "manual-push"

    def test_completed_at_round_trip(self) -> None:
        now = datetime.now(UTC)
        c = make_cycle(completed_at=now)
        data = c.model_dump(mode="json")
        c2 = CycleBead.model_validate(data)
        assert c2.completed_at is not None

    def test_cost_accumulation_round_trip(self) -> None:
        c = make_cycle(finding_count=3, proposal_count=1, total_cost_usd=1.50)
        data = c.model_dump(mode="json")
        c2 = CycleBead.model_validate(data)
        assert c2.finding_count == 3
        assert c2.proposal_count == 1
        assert c2.total_cost_usd == 1.50


# ---------------------------------------------------------------------------
# ProposalBead
# ---------------------------------------------------------------------------


class TestProposalBead:
    def test_instantiate_defaults(self) -> None:
        p = make_proposal()
        assert p.proposal_id == "prop-001"
        assert p.cycle_id == "cycle-001"
        assert p.repo == "bread-forge/kiln"
        assert p.spec_hash == "abc123"
        assert p.spec_path == "/tmp/spec.md"
        assert p.status == "pending"
        assert p.gate_decision_at is None
        assert p.decision_by is None
        assert p.human_diff_hash is None
        assert p.review_seconds is None

    def test_json_round_trip(self) -> None:
        p = make_proposal()
        data = p.model_dump(mode="json")
        p2 = ProposalBead.model_validate(data)
        assert p2.proposal_id == p.proposal_id
        assert p2.cycle_id == p.cycle_id
        assert p2.repo == p.repo
        assert p2.spec_hash == p.spec_hash
        assert p2.status == p.status

    def test_all_statuses(self) -> None:
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

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_proposal(status="unknown")

    def test_touch_updates_updated_at(self) -> None:
        p = make_proposal()
        before = p.updated_at
        p.touch()
        assert p.updated_at >= before

    def test_optional_decision_fields_round_trip(self) -> None:
        now = datetime.now(UTC)
        p = make_proposal(
            gate_decision_at=now,
            decision_by="human:bread",
            human_diff_hash="deadbeef",
            review_seconds=42.5,
        )
        data = p.model_dump(mode="json")
        p2 = ProposalBead.model_validate(data)
        assert p2.decision_by == "human:bread"
        assert p2.human_diff_hash == "deadbeef"
        assert p2.review_seconds == 42.5
        assert p2.gate_decision_at is not None


# ---------------------------------------------------------------------------
# SuppressionBead
# ---------------------------------------------------------------------------


class TestSuppressionBead:
    def test_instantiate_defaults(self) -> None:
        s = make_suppression()
        assert s.suppression_id == "sup-001"
        assert s.finding_class == "repo-audit.integration-gap.executor"
        assert s.decision == "deferred"
        assert s.reason == "waiting for v0.2"
        assert s.created_by == "human:bread"
        assert s.expires_at is None
        assert s.conditions is None

    def test_json_round_trip(self) -> None:
        s = make_suppression()
        data = s.model_dump(mode="json")
        s2 = SuppressionBead.model_validate(data)
        assert s2.suppression_id == s.suppression_id
        assert s2.finding_class == s.finding_class
        assert s2.decision == s.decision
        assert s2.expires_at == s.expires_at
        assert s2.is_active() == s.is_active()

    def test_json_round_trip_with_expiry(self) -> None:
        future = datetime.now(UTC) + timedelta(days=30)
        s = make_suppression(expires_at=future)
        data = s.model_dump(mode="json")
        s2 = SuppressionBead.model_validate(data)
        assert s2.expires_at is not None
        assert s2.is_active() is True

    def test_both_decision_values(self) -> None:
        for decision in ("rejected", "deferred"):
            s = make_suppression(decision=decision)
            assert s.decision == decision

    def test_invalid_decision_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_suppression(decision="ignored")

    def test_is_active_permanent_suppression(self) -> None:
        """Permanent suppressions (no expiry) are always active."""
        s = make_suppression(expires_at=None)
        assert s.is_active() is True

    def test_is_active_future_expiry(self) -> None:
        """Suppressions with a future expiry are still active."""
        s = make_suppression(expires_at=datetime.now(UTC) + timedelta(days=7))
        assert s.is_active() is True

    def test_is_active_past_expiry(self) -> None:
        """Suppressions whose expiry is in the past are no longer active."""
        s = make_suppression(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        assert s.is_active() is False

    def test_is_active_far_past_expiry(self) -> None:
        s = make_suppression(expires_at=datetime.now(UTC) - timedelta(days=365))
        assert s.is_active() is False

    def test_conditions_optional(self) -> None:
        s = make_suppression(conditions="Re-surface if: integration tests added")
        assert s.conditions == "Re-surface if: integration tests added"

    def test_conditions_round_trip(self) -> None:
        s = make_suppression(conditions="Re-surface if: dependency ships")
        data = s.model_dump(mode="json")
        s2 = SuppressionBead.model_validate(data)
        assert s2.conditions == "Re-surface if: dependency ships"

    def test_rejected_decision_permanent(self) -> None:
        s = make_suppression(decision="rejected", expires_at=None)
        assert s.is_active() is True
