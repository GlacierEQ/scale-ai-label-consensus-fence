# Label Consensus Fence

Independent GlacierEQ portfolio implementation aligned to **Scale AI** operating themes.

> **Not affiliated.** This repository is not affiliated with, endorsed by, employed by, or deployed at Scale AI. No proprietary access, production deployment, customer impact, or company partnership is claimed.

## Purpose

Prevent evaluation labels from becoming truth merely because several correlated or contaminated raters repeated the same answer.

## Implemented fence

`LabelConsensusFence` promotes a label only when the evidence clears multiple independent gates:

- every rater has a machine-verifiable provenance digest;
- duplicate rater identities fail closed;
- contaminated ratings force quarantine;
- low-confidence or poorly calibrated raters are excluded from eligible consensus;
- a minimum number of eligible raters is required;
- a minimum number of independent provenance groups is required;
- no single provenance group may dominate the weighted evidence;
- weighted consensus must clear the configured threshold.

Rater weight is `confidence × calibration`. The result is either `PROMOTE` with the winning label or `QUARANTINE` with exact reason codes. Receipts include label/group weights and a deterministic evidence digest.

## Run

```bash
python -m pytest -q
python scripts/operate.py
```

Build and install:

```bash
python -m pip install build
python -m build
python -m pip install dist/*.whl
label-consensus-fence
```

## Proof surface

- `src/label_consensus_fence.py` — provenance-weighted consensus/quarantine engine
- `src/label_consensus_cli.py` — installable execution surface
- `tests/test_label_consensus_fence.py` — consensus, contamination, independence and provenance behavior
- `tests/test_adversarial.py` — fail-closed adversarial coverage
- `.github/workflows/tests.yml` — tests + cold-start + wheel build/install + installed CLI
- `machine/` — existing Helix control-plane and promotion surfaces remain preserved

## Current boundary

The mechanism consumes normalized rater/provenance observations. It does not claim Scale AI infrastructure access or production labeling performance. The next depth step is a benchmark-contamination simulator and multi-reader evaluation adapter that generates these provenance receipts from controlled experiments.
