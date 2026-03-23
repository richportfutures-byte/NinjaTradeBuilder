# Readiness V2 Contract Adapter Notes

## 1. What adapter/registry boundary was added
Added a narrow readiness v2 contract-adapter registry in [src/ninjatradebuilder/readiness_v2/adapters.py](C:/Users/stuar/Documents/GitHub/NinjaTradeBuilder/src/ninjatradebuilder/readiness_v2/adapters.py) that defines the deterministic operations the operator harness needs: bootstrap from a validated packet, update an existing watch from a validated packet plus evaluation timestamp, and replay an ordered update sequence. The harness now resolves execution through `get_contract_adapter(...)` instead of calling ZN builders directly.

## 2. What behavior remains ZN-only
The registered adapter set remains `ZN` only. Bootstrap, update, and replay still delegate to the existing ZN deterministic builders and watch logic, the current artifact schemas and JSON outputs remain unchanged, and unsupported contracts fail closed at the registry boundary.

## 3. What remains intentionally deferred before adding another contract
No additional contract adapters, shared cross-contract normalization layer, contract-specific fixture packs beyond ZN, or broader abstraction over contract-specific trigger/value logic were added in this slice. The boundary is limited to the exact deterministic operations already exercised by the current ZN bootstrap, update, and replay paths.
