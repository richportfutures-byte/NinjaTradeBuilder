from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from ninjatradebuilder.readiness_web import build_readiness_web_app

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "readiness"


def _start_response_capture() -> tuple[dict[str, Any], Any]:
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    return captured, start_response


def test_readiness_web_root_serves_basic_html_page() -> None:
    app = build_readiness_web_app(client_factory=lambda config: config)
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }
    response_capture, start_response = _start_response_capture()

    response_body = b"".join(app(environ, start_response)).decode("utf-8")

    assert response_capture["status"] == "200 OK"
    assert "<title>NinjaTradeBuilder Readiness</title>" in response_body
    assert 'id="runtime-input-text"' in response_body
    assert 'id="trigger-text"' in response_body
    assert 'id="response-output"' in response_body


def test_readiness_web_endpoint_executes_zn_fixture_path(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    runtime_inputs = json.loads((FIXTURES_DIR / "zn_runtime_inputs.valid.json").read_text())
    readiness_trigger = json.loads((FIXTURES_DIR / "zn_recheck_trigger.valid.json").read_text())
    expected_output = json.loads((FIXTURES_DIR / "zn_wait_for_trigger.expected.json").read_text())
    captured_adapter: dict[str, Any] = {}

    class FakeGeminiAdapter:
        def __init__(self, *, client, model, timeout_seconds=None, max_retries=0):
            captured_adapter["client"] = client
            captured_adapter["model"] = model

        def generate_structured(self, request):
            captured_adapter["prompt_id"] = request.prompt_id
            return expected_output

    monkeypatch.setattr("ninjatradebuilder.readiness_web.GeminiResponsesAdapter", FakeGeminiAdapter)

    app = build_readiness_web_app(client_factory=lambda config: config)
    request_body = json.dumps(
        {
            "runtime_inputs": runtime_inputs,
            "readiness_trigger": readiness_trigger,
        }
    ).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/readiness",
        "CONTENT_LENGTH": str(len(request_body)),
        "wsgi.input": io.BytesIO(request_body),
    }
    response_capture, start_response = _start_response_capture()

    response_body = b"".join(app(environ, start_response))

    assert response_capture["status"] == "200 OK"
    assert json.loads(response_body.decode("utf-8")) == expected_output
    assert captured_adapter["client"].api_key == "test-key"
    assert captured_adapter["prompt_id"] == 10
