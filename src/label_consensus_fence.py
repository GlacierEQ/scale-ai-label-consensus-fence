"""Label Consensus Fence.

Promotes a label only when independently sourced raters with valid provenance
reach a configurable weighted consensus. Ambiguous, contaminated, correlated,
or under-evidenced labels are quarantined with explicit reasons.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REFUSE = "REFUSE"


@dataclass(frozen=True)
class LabelConsensusFenceRequest:
    subject_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    budget: float = 1.0
    grant_id: str | None = None
    not_after: float | None = None


@dataclass(frozen=True)
class LabelConsensusFenceReceipt:
    decision: Decision
    reasons: tuple[str, ...]
    digest: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"decision": self.decision.value, "reasons": list(self.reasons), "digest": self.digest, "metrics": self.metrics}


class ConsensusError(ValueError):
    pass


class LabelConsensusFence:
    MIN_BUDGET = 0.0

    @staticmethod
    def _num(value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConsensusError(f"{label}_invalid")
        value = float(value)
        if not math.isfinite(value):
            raise ConsensusError(f"{label}_not_finite")
        if minimum is not None and value < minimum:
            raise ConsensusError(f"{label}_below_minimum")
        if maximum is not None and value > maximum:
            raise ConsensusError(f"{label}_above_maximum")
        return value

    @classmethod
    def _config(cls, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ConsensusError("config_missing")
        return {
            "min_raters": int(cls._num(raw.get("min_raters", 3), "min_raters", minimum=2)),
            "min_consensus": cls._num(raw.get("min_consensus", 0.75), "min_consensus", minimum=0.5, maximum=1),
            "min_independent_groups": int(cls._num(raw.get("min_independent_groups", 2), "min_independent_groups", minimum=1)),
            "max_group_weight_share": cls._num(raw.get("max_group_weight_share", 0.60), "max_group_weight_share", minimum=0, maximum=1),
            "min_confidence": cls._num(raw.get("min_confidence", 0.50), "min_confidence", minimum=0, maximum=1),
            "min_calibration": cls._num(raw.get("min_calibration", 0.50), "min_calibration", minimum=0, maximum=1),
        }

    @classmethod
    def _rating(cls, raw: Any, index: int) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ConsensusError(f"rating_{index}_not_object")
        rater_id = str(raw.get("rater_id", "")).strip()
        label = str(raw.get("label", "")).strip()
        group = str(raw.get("source_group", "")).strip()
        provenance = str(raw.get("provenance_digest", "")).strip()
        if not rater_id:
            raise ConsensusError(f"rating_{index}_rater_id_missing")
        if not label:
            raise ConsensusError(f"rating_{index}_label_missing")
        if not group:
            raise ConsensusError(f"rating_{index}_source_group_missing")
        if not SHA256_RE.fullmatch(provenance):
            raise ConsensusError(f"rating_{index}_provenance_invalid")
        return {
            "rater_id": rater_id,
            "label": label,
            "source_group": group,
            "provenance_digest": provenance,
            "confidence": cls._num(raw.get("confidence"), f"rating_{index}_confidence", minimum=0, maximum=1),
            "calibration": cls._num(raw.get("calibration"), f"rating_{index}_calibration", minimum=0, maximum=1),
            "contaminated": bool(raw.get("contaminated", False)),
        }

    def evaluate(self, req: LabelConsensusFenceRequest) -> LabelConsensusFenceReceipt:
        reasons: list[str] = []
        if not str(req.subject_id or "").strip():
            reasons.append("subject_id_missing")
        if isinstance(req.budget, bool) or not isinstance(req.budget, (int, float)) or not math.isfinite(float(req.budget)) or float(req.budget) <= self.MIN_BUDGET:
            reasons.append("budget_non_positive_or_invalid")
        payload = req.payload if isinstance(req.payload, dict) else {}
        if not isinstance(req.payload, dict):
            reasons.append("payload_not_object")
        result: dict[str, Any] | None = None
        try:
            config = self._config(payload.get("config"))
            raw = payload.get("ratings")
            if not isinstance(raw, list) or not raw:
                raise ConsensusError("ratings_missing")
            ratings = [self._rating(row, i) for i, row in enumerate(raw)]
            if len({r["rater_id"] for r in ratings}) != len(ratings):
                raise ConsensusError("duplicate_rater_id")
            contaminated = [r["rater_id"] for r in ratings if r["contaminated"]]
            if contaminated:
                reasons.append("contaminated_rating_present")
            eligible = [r for r in ratings if not r["contaminated"] and r["confidence"] >= config["min_confidence"] and r["calibration"] >= config["min_calibration"]]
            if len(eligible) < config["min_raters"]:
                reasons.append("insufficient_eligible_raters")
            groups = {r["source_group"] for r in eligible}
            if len(groups) < config["min_independent_groups"]:
                reasons.append("insufficient_independent_provenance_groups")
            label_weight: dict[str, float] = defaultdict(float)
            group_weight: dict[str, float] = defaultdict(float)
            total_weight = 0.0
            for rating in eligible:
                weight = rating["confidence"] * rating["calibration"]
                label_weight[rating["label"]] += weight
                group_weight[rating["source_group"]] += weight
                total_weight += weight
            winner = None
            consensus = 0.0
            if total_weight > 0:
                winner = min(label_weight, key=lambda label: (-label_weight[label], label))
                consensus = label_weight[winner] / total_weight
                if consensus < config["min_consensus"]:
                    reasons.append("consensus_below_threshold")
                dominant_group_share = max(group_weight.values(), default=0.0) / total_weight
                if dominant_group_share > config["max_group_weight_share"]:
                    reasons.append("provenance_group_dominates_consensus")
            else:
                reasons.append("no_weighted_evidence")
            result = {
                "status": "QUARANTINE" if reasons else "PROMOTE",
                "label": winner if not reasons else None,
                "candidate_label": winner,
                "weighted_consensus": round(consensus, 12),
                "eligible_rater_count": len(eligible),
                "independent_group_count": len(groups),
                "contaminated_raters": contaminated,
                "label_weights": {k: round(v, 12) for k, v in sorted(label_weight.items())},
                "group_weights": {k: round(v, 12) for k, v in sorted(group_weight.items())},
                "evidence_digest": _digest([{k: r[k] for k in sorted(r)} for r in sorted(eligible, key=lambda x: x["rater_id"])]),
            }
        except ConsensusError as exc:
            reasons.append(str(exc))
        decision = Decision.REFUSE if reasons else Decision.ALLOW
        metrics = {"result": result}
        body = {"subject_id": req.subject_id, "decision": decision.value, "reasons": reasons, "metrics": metrics}
        return LabelConsensusFenceReceipt(decision, tuple(reasons or ["label_consensus_fence_passed"]), _digest(body), metrics)


Mechanism = LabelConsensusFence
