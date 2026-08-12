from __future__ import annotations

import hashlib

from label_consensus_fence import Decision, LabelConsensusFence, LabelConsensusFenceRequest


def prov(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def rating(rater: str, label: str, group: str, *, confidence=0.9, calibration=0.9, contaminated=False):
    return {"rater_id": rater, "label": label, "source_group": group, "provenance_digest": prov(rater), "confidence": confidence, "calibration": calibration, "contaminated": contaminated}


def evaluate(ratings, config=None):
    return LabelConsensusFence().evaluate(LabelConsensusFenceRequest("item-a", {"ratings": ratings, "config": config or {"min_raters": 3, "min_consensus": 0.70, "min_independent_groups": 2, "max_group_weight_share": 0.70, "min_confidence": 0.5, "min_calibration": 0.5}}, 1.0))


def test_promotes_only_weighted_consensus_with_independent_provenance() -> None:
    receipt = evaluate([rating("r1", "cat", "g1"), rating("r2", "cat", "g2"), rating("r3", "cat", "g3")])
    assert receipt.decision is Decision.ALLOW
    result = receipt.metrics["result"]
    assert result["status"] == "PROMOTE"
    assert result["label"] == "cat"
    assert result["weighted_consensus"] == 1.0


def test_ambiguous_labels_are_quarantined() -> None:
    receipt = evaluate([rating("r1", "cat", "g1"), rating("r2", "dog", "g2"), rating("r3", "bird", "g3")])
    assert receipt.decision is Decision.REFUSE
    assert "consensus_below_threshold" in receipt.reasons
    assert receipt.metrics["result"]["status"] == "QUARANTINE"


def test_contaminated_rating_forces_quarantine() -> None:
    receipt = evaluate([rating("r1", "cat", "g1"), rating("r2", "cat", "g2"), rating("r3", "cat", "g3", contaminated=True), rating("r4", "cat", "g4")])
    assert receipt.decision is Decision.REFUSE
    assert "contaminated_rating_present" in receipt.reasons
    assert "r3" in receipt.metrics["result"]["contaminated_raters"]


def test_duplicate_rater_identity_fails_closed() -> None:
    receipt = evaluate([rating("same", "cat", "g1"), rating("same", "cat", "g2"), rating("r3", "cat", "g3")])
    assert receipt.decision is Decision.REFUSE
    assert "duplicate_rater_id" in receipt.reasons


def test_bad_provenance_digest_fails_closed() -> None:
    rows = [rating("r1", "cat", "g1"), rating("r2", "cat", "g2"), rating("r3", "cat", "g3")]
    rows[0]["provenance_digest"] = "fake"
    receipt = evaluate(rows)
    assert receipt.decision is Decision.REFUSE
    assert "rating_0_provenance_invalid" in receipt.reasons


def test_low_confidence_or_calibration_removes_rater_from_eligible_set() -> None:
    receipt = evaluate([rating("r1", "cat", "g1"), rating("r2", "cat", "g2"), rating("r3", "cat", "g3", confidence=0.2), rating("r4", "cat", "g4", calibration=0.2)])
    assert receipt.decision is Decision.REFUSE
    assert "insufficient_eligible_raters" in receipt.reasons


def test_single_provenance_group_cannot_manufacture_consensus() -> None:
    receipt = evaluate([rating("r1", "cat", "same"), rating("r2", "cat", "same"), rating("r3", "cat", "same")])
    assert receipt.decision is Decision.REFUSE
    assert "insufficient_independent_provenance_groups" in receipt.reasons
    assert "provenance_group_dominates_consensus" in receipt.reasons


def test_evidence_digest_changes_when_rater_evidence_changes() -> None:
    first = evaluate([rating("r1", "cat", "g1"), rating("r2", "cat", "g2"), rating("r3", "cat", "g3")])
    second_rows = [rating("r1", "cat", "g1"), rating("r2", "cat", "g2"), rating("r3", "cat", "g3", confidence=0.8)]
    second = evaluate(second_rows)
    assert first.metrics["result"]["evidence_digest"] != second.metrics["result"]["evidence_digest"]
