# DEV_UP_INSTRUCTIONS — implementation record

**Repository:** `GlacierEQ/scale-ai-label-consensus-fence`  
**Independent company lens:** Scale AI  
**Innovation:** Label Consensus Fence

## Mission

Promote labels only when independently sourced, calibrated evidence clears a contamination-resistant consensus fence.

## Implemented

The generic scaffold has been replaced by a provenance-weighted consensus/quarantine engine.

`src/label_consensus_fence.py` now:

- requires valid SHA-256 provenance receipts per rater;
- rejects duplicate identities;
- quarantines contaminated evidence;
- filters low-confidence and poorly calibrated raters;
- requires minimum eligible-rater and independent-provenance-group counts;
- detects one-group domination of weighted consensus;
- computes deterministic confidence × calibration label weights;
- promotes only above the configured consensus threshold;
- emits explicit reason codes and evidence digests.

`src/label_consensus_cli.py` and `scripts/operate.py` execute the mechanism directly. The project is packaged with the `label-consensus-fence` console command.

## Verification contract

Behavioral tests cover valid promotion, ambiguous quarantine, contamination, duplicate raters, invalid provenance, confidence/calibration filtering, correlated source groups, and evidence-digest sensitivity. Existing adversarial coverage remains active.

CI must pass tests, cold-start, wheel build/install and installed CLI execution before Helix promotion evidence can be minted.

## Truth boundary

No Scale AI affiliation, proprietary access, production deployment, customer impact, or company partnership is claimed. Benchmark-contamination and multi-reader adapters remain further depth steps.
