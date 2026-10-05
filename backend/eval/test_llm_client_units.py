import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.llm_client import (
    call_llm,
    extract_json_from_llm,
    AuthenticationError,
    RateLimitExhaustedError,
    InvalidRequestError,
    telemetry_tracker,
    ReportTelemetryTracker
)

print("--- TEST A.1: Missing Credentials Raises AuthenticationError ---")
with patch("backend.agents.llm_client.settings") as mock_settings:
    mock_settings.GROQ_API_KEY = ""
    with patch("os.getenv", return_value=""):
        import backend.agents.llm_client as client_mod
        client_mod._groq_client = None
        try:
            call_llm("test prompt")
            assert False, "Expected AuthenticationError for missing key"
        except AuthenticationError as e:
            print("[PASS] Caught AuthenticationError for missing credentials:", e)

print("\n--- TEST A.2: 401 Unauthorized Does NOT Retry ---")
mock_groq = MagicMock()
mock_groq.chat.completions.create.side_effect = Exception("Error 401: Unauthorized - invalid api key")
with patch("backend.agents.llm_client.get_groq_client", return_value=mock_groq):
    try:
        call_llm("test prompt", max_retries=3)
        assert False, "Expected AuthenticationError"
    except AuthenticationError:
        assert mock_groq.chat.completions.create.call_count == 1, f"Expected 1 call, got {mock_groq.chat.completions.create.call_count}"
        print("[PASS] 401 exited immediately without retries (call count = 1).")

print("\n--- TEST A.3: 400 Bad Request Does NOT Retry ---")
mock_groq = MagicMock()
mock_groq.chat.completions.create.side_effect = Exception("Error 400: invalid_request_error - model not found")
with patch("backend.agents.llm_client.get_groq_client", return_value=mock_groq):
    try:
        call_llm("test prompt", max_retries=3)
        assert False, "Expected InvalidRequestError"
    except InvalidRequestError:
        assert mock_groq.chat.completions.create.call_count == 1
        print("[PASS] 400 exited immediately without retries (call count = 1).")

print("\n--- TEST A.4: Daily TPD 429 Quota Exhaustion Fails Immediately ---")
mock_groq = MagicMock()
mock_groq.chat.completions.create.side_effect = Exception("Error code: 429 - Rate limit reached on tokens per day (TPD): Limit 200000, Used 200000. try again in 14m30.0s")
with patch("backend.agents.llm_client.get_groq_client", return_value=mock_groq):
    try:
        call_llm("test prompt", max_retries=2)
        assert False, "Expected RateLimitExhaustedError"
    except RateLimitExhaustedError as e:
        assert mock_groq.chat.completions.create.call_count <= 2
        print("[PASS] Quota exhaustion detected, fast-failed without unbounded looping (call count <= 2). Reset sec:", e.reset_seconds)

print("\n--- TEST A.5: Telemetry Records Tokens and Logical Calls ---")
mock_groq = MagicMock()
mock_resp = MagicMock()
mock_resp.choices = [MagicMock(message=MagicMock(content='{"status": "ok"}'))]
mock_resp.usage = MagicMock(prompt_tokens=45, completion_tokens=15)
mock_groq.chat.completions.create.return_value = mock_resp

with patch("backend.agents.llm_client.get_groq_client", return_value=mock_groq):
    res = call_llm("give me json", run_id="test_run_001", component="synthesis")
    parsed = extract_json_from_llm(res)
    assert parsed == {"status": "ok"}
    metrics = telemetry_tracker.get_run_metrics("test_run_001")
    assert metrics["logical_calls"] == 1
    assert metrics["prompt_tokens"] == 45
    assert metrics["completion_tokens"] == 15
    assert metrics["total_tokens"] == 60
    assert metrics["calls_by_component"]["synthesis"] == 1
    print("[PASS] Telemetry recorded correctly:", metrics)

print("\nALL LLM CLIENT UNIT TESTS PASSED!")
