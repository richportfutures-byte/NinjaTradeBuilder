# NinjaTradeBuilder Operator Quickstart

## Purpose

This is the smallest supported local run path for the current branch.

It is intended for operator verification and smoke execution, not production automation.

## Prerequisites

- Python `3.11+`
- run from the repo root
- `GEMINI_API_KEY` set in the shell environment

Optional provider policy env vars:

- `NINJATRADEBUILDER_GEMINI_MODEL`
  Default: `gemini-3.1-pro-preview`
- `NINJATRADEBUILDER_GEMINI_TIMEOUT_SECONDS`
  Default: `20`
  Minimum: `10`
- `NINJATRADEBUILDER_GEMINI_MAX_RETRIES`
  Default: `1`
- `NINJATRADEBUILDER_GEMINI_RETRY_INITIAL_DELAY_SECONDS`
  Default: `1.0`
- `NINJATRADEBUILDER_GEMINI_RETRY_MAX_DELAY_SECONDS`
  Default: `4.0`

Install with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Canonical model

Use `gemini-3.1-pro-preview` for the current validated branch baseline.

## Operator path overview

Treat the workflow as two separate phases:

1. upstream packet compilation
2. runtime execution against the frozen packet

The current compiler slice supports `ES` only. It is deterministic for historical sessions, but it
still depends on a manual overlay for the fields that are not yet safe to derive from raw
historical bars.

## Phase 1: compile one ES historical packet

The compiler builds one frozen `historical_packet_v1` JSON file plus a provenance sidecar.

Copy-paste-safe compile command:

```bash
mkdir -p ./build
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ninjatradebuilder.packet_compiler.cli \
  --contract ES \
  --historical-input tests/fixtures/compiler/es_historical_input.valid.json \
  --overlay tests/fixtures/compiler/es_overlay.assisted.valid.json \
  --output ./build/es.packet.json
```

This writes:

- `./build/es.packet.json`
- `./build/es.packet.provenance.json`

The compiler currently derives and records provenance for:

- prior RTH high / low / close
- overnight high / low
- VWAP
- session range
- initial balance high / low / range
- weekly open
- a conservative overlay-assist subset:
  - `attached_visuals` defaults to all false when omitted
  - `major_higher_timeframe_levels`, `key_hvns`, `key_lvns`,
    `singles_excess_poor_high_low_notes`, and `cross_market_context` default to `null`
  - `data_quality_flags` defaults to `[]`

`initial balance` and `weekly open` are recorded in the provenance sidecar because the frozen
runtime packet schema does not have dedicated top-level fields for them.

Compiler-side integrity checks are strict and fail closed:

- `prior_rth_bars`, `overnight_bars`, and `current_rth_bars` must be non-empty, strictly
  timestamp-ascending, and free of duplicate timestamps
- `current_rth_bars` must all fall on one session date
- `prior_rth_bars` must represent a prior date relative to the current session
- `overnight_bars` must fall strictly between prior RTH and current RTH with no overlap
- `weekly_open_bar` must not be later than the first current RTH bar
- initial balance is derived from all `current_rth_bars` with
  `first_timestamp <= timestamp < first_timestamp + 60 minutes`, and the compiler requires at
  least two bars spanning at least 30 minutes inside that window

Still-manual ES overlay fields are:

- `challenge_state`
- `current_session_vah`, `current_session_val`, `current_session_poc`
- `previous_session_vah`, `previous_session_val`, `previous_session_poc`
- `avg_20d_session_range`
- `cumulative_delta`
- `current_volume_vs_average`
- `opening_type`
- `event_calendar_remainder`
- `breadth`
- `index_cash_tone`

They remain manual because they require external calendars, profile calculations, order-flow data,
cross-market context, or doctrine-sensitive interpretation that is not safely derivable from the
current historical bar inputs alone.

## Phase 1a: inspect the provenance artifact

Copy-paste-safe provenance inspection:

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

provenance = json.loads(Path("./build/es.packet.provenance.json").read_text())
print("compiler_schema:", provenance["compiler_schema"])
print("contract:", provenance["contract"])
print("derived_features:", sorted(provenance["derived_features"].keys()))
print("current_price_source:", provenance["field_provenance"]["market_packet.current_price"])
PY
```

## Phase 2: run the runtime CLI on the compiled packet

Copy-paste-safe runtime command:

```bash
export GEMINI_API_KEY=your_existing_key
mkdir -p ./logs
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ninjatradebuilder.cli \
  --packet ./build/es.packet.json \
  --audit-log ./logs/ninjatradebuilder.audit.jsonl
```

- If `--packet` points to a multi-contract bundle like `tests/fixtures/packets.valid.json`, add
  `--contract ES`.
- `--evaluation-timestamp` is optional. If omitted, the CLI uses `market_packet.timestamp`.
- `--model` is optional. The default is `gemini-3.1-pro-preview`.
- `--audit-log` is optional. When supplied, the CLI appends one JSON record per run.
- Gemini requests are bounded by the centralized timeout and retry env vars above.

Aggregate local audit logs with:

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ninjatradebuilder.audit_report \
  --audit-log ./logs/ninjatradebuilder.audit.jsonl
```

The report prints concise counts for:

- success vs failure
- termination_stage
- final_decision
- error_category
- requested_contract

Equivalent Python API form:

```python
import json
import os
from pathlib import Path

from google import genai

from ninjatradebuilder import run_pipeline, validate_historical_packet
from ninjatradebuilder.gemini_adapter import GeminiResponsesAdapter

packet = json.loads(Path("tests/fixtures/packets.valid.json").read_text())
es_packet = {
    "$schema": "historical_packet_v1",
    "challenge_state": packet["shared"]["challenge_state"],
    "attached_visuals": packet["shared"]["attached_visuals"],
    "contract_metadata": packet["contracts"]["ES"]["contract_metadata"],
    "market_packet": packet["contracts"]["ES"]["market_packet"],
    "contract_specific_extension": packet["contracts"]["ES"]["contract_specific_extension"],
}

validated_packet = validate_historical_packet(es_packet)
adapter = GeminiResponsesAdapter(
    client=genai.Client(api_key=os.environ["GEMINI_API_KEY"]),
    model="gemini-3.1-pro-preview",
)
result = run_pipeline(
    packet=validated_packet,
    evaluation_timestamp_iso=validated_packet.market_packet.timestamp.isoformat().replace("+00:00", "Z"),
    model_adapter=adapter,
)

print(result.termination_stage)
print(result.final_decision)
```

## What this path guarantees

- prompt-bound contract routing
- strict stage-by-stage schema validation
- fail-closed termination at the first valid no-go stage
- explicit final decision mapping at Stage D
- clear startup failure when `GEMINI_API_KEY` is missing
- bounded Gemini request policy with explicit timeout/retry behavior
- optional local JSONL audit record for operator debugging
- thin local aggregate audit report for recurring-run visibility

## What this path does not provide yet

- compiler support beyond `ES`
- automatic population of all overlay fields from a real market-data provider
- persistent audit sink beyond local JSONL operator logs
- broader structured observability beyond local file-based aggregation
- deployment-specific handler for Netlify or other serverless targets
