# Readiness V2 RC Hardening Notes

## 1. What was hardened
- Removed the remaining hardcoded supported-contract list from the readiness v2 harness bundle-selection error path so the operator surface now derives that message from the registered contract set.
- Tightened operator-surface help coverage so each subcommand help path is checked for the full six-contract set.
- Hardened the smoke runner so it explicitly covers all six supported contracts with deterministic operator invocations instead of leaving one contract implied.

## 2. What six-contract behavior is now explicitly covered by tests/smoke paths
- Unit and fixture tests cover bootstrap, update, replay, schema validation, routing, continuity, provenance, and fail-closed behavior across `ZN`, `ES`, `NQ`, `CL`, `MGC`, and `6E`.
- Operator-surface golden tests cover bootstrap, update, and replay invocation paths with strict JSON output for all six contracts.
- The direct smoke path now runs one deterministic operator invocation for each supported contract: `ZN`, `ES`, `NQ`, `CL`, `MGC`, and `6E`.

## 3. What remains intentionally out of scope before a broader release
- No legacy readiness v1 surfaces were modified or bridged into readiness v2.
- No new harness modes, product surfaces, trigger families, or routing targets were added.
- No scheduler, persistence, web-surface, or provider/LLM behavior was introduced in this hardening slice.
