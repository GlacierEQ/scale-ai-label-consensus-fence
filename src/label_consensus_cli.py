from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from label_consensus_fence import Decision, LabelConsensusFence, LabelConsensusFenceRequest


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def demo_payload() -> dict:
    return {
        "config": {"min_raters": 3, "min_consensus": 0.70, "min_independent_groups": 2, "max_group_weight_share": 0.70, "min_confidence": 0.50, "min_calibration": 0.50},
        "ratings": [
            {"rater_id": "r1", "label": "safe", "source_group": "panel-a", "provenance_digest": _sha("r1"), "confidence": 0.92, "calibration": 0.90},
            {"rater_id": "r2", "label": "safe", "source_group": "panel-b", "provenance_digest": _sha("r2"), "confidence": 0.89, "calibration": 0.91},
            {"rater_id": "r3", "label": "safe", "source_group": "panel-c", "provenance_digest": _sha("r3"), "confidence": 0.88, "calibration": 0.87},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote or quarantine a label using provenance-weighted consensus")
    parser.add_argument("--input", type=Path, help="JSON payload; defaults to a deterministic demo")
    parser.add_argument("--subject", default="label-demo")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text()) if args.input else demo_payload()
    receipt = LabelConsensusFence().evaluate(LabelConsensusFenceRequest(args.subject, payload, 1.0))
    print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    return 0 if receipt.decision is Decision.ALLOW else 2


if __name__ == "__main__":
    raise SystemExit(main())
