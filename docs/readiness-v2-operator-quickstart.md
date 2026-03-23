# Readiness V2 Operator Quickstart

## 1. What the current v2 operator surface supports
The current readiness v2 operator surface provides deterministic `bootstrap`, `update`, and `replay` execution through the package entrypoint `python -m ninjatradebuilder.readiness_v2`. It emits strict schema-backed JSON artifacts to stdout for the existing readiness v2 artifact set and fails closed on malformed JSON, unsupported contracts, incoherent watch updates, and schema-invalid outputs.

## 2. Exact invocation patterns for bootstrap, update, and replay
`bootstrap`
```powershell
python -m ninjatradebuilder.readiness_v2 bootstrap --packet path\to\packet.json
```

`update`
```powershell
python -m ninjatradebuilder.readiness_v2 update --prior-watch path\to\prior.watch.json --packet path\to\packet.json --evaluation-timestamp 2026-01-14T15:10:00Z
```

`replay`
```powershell
python -m ninjatradebuilder.readiness_v2 replay --packet path\to\bootstrap.packet.json --updates path\to\replay.updates.json
```

Optional artifact-file output remains available in each mode with `--artifact-file path\to\artifact.json`.

For multi-contract bundle inputs, add `--contract 6E|CL|ES|MGC|NQ|ZN` to select the supported contract packet to execute.

## 3. Supported contracts
The current operator surface supports `6E`, `CL`, `ES`, `MGC`, `NQ`, and `ZN`. Single-contract historical packet inputs are accepted directly. Multi-contract bundle inputs are accepted only when `--contract` selects one of those six supported readiness v2 contracts.

## 4. What remains intentionally out of scope
Legacy readiness v1 surfaces, `readiness_web.py`, Stage A-D pipeline behavior, prompt/provider behavior, contracts beyond `6E`, `CL`, `ES`, `MGC`, `NQ`, and `ZN`, new operator modes beyond `bootstrap`, `update`, and `replay`, and any Stage C routing or trade authorization behavior remain out of scope for the current readiness v2 operator surface.
