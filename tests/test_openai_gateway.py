from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from deep_research.models.config import ModelSettings
from deep_research.models.gateway import ModelGateway, ModelInvocationError
from deep_research.models.spend import SpendLimitError


class Result(BaseModel):
    value: int


def settings(model="gpt-5.4-mini"):
    return ModelSettings.model_validate({
        "targets": {"primary": {"provider": "openai", "model_id": model, "max_attempts": 1}},
        "roles": {"report": ["primary"]},
    })


def mock_client(monkeypatch, *, arguments='{"value": 42}', status="completed", usage=True):
    response = SimpleNamespace(
        status=status,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20) if usage else None,
        output=[SimpleNamespace(type="function_call", name="return_result", arguments=arguments)],
    )
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.responses.create.return_value = response
    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kwargs: client)
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["gpt-4.1-mini", "gpt-5.4-mini"])
async def test_native_responses_request_is_bounded_and_accounts_for_usage(
    tmp_path, monkeypatch, model,
):
    client = mock_client(monkeypatch)
    gateway = ModelGateway(settings(model), spend_ledger_path=tmp_path / "spend.sqlite")
    result = await gateway.generate_structured(
        role="report", prompt="Return JSON", system_prompt="Return result", output_type=Result,
    )
    assert result.value == 42
    kwargs = client.responses.create.call_args.kwargs
    assert kwargs["max_output_tokens"] == 4096
    assert kwargs["store"] is False
    assert kwargs["parallel_tool_calls"] is False
    assert kwargs["tool_choice"] == {"type": "function", "name": "return_result"}
    assert ("reasoning" in kwargs) == model.startswith("gpt-5")
    assert ("temperature" in kwargs) != model.startswith("gpt-5")
    assert gateway.usage_summary()["input_tokens"] == 100
    assert gateway.usage_summary()["reserved_usd"] == 0


@pytest.mark.asyncio
async def test_spend_limit_prevents_network_request(tmp_path, monkeypatch):
    client = mock_client(monkeypatch)
    gateway = ModelGateway(settings(), spend_limit_usd=0.00001,
                           spend_ledger_path=tmp_path / "spend.sqlite")
    with pytest.raises(SpendLimitError):
        await gateway.generate_structured(
            role="report", prompt="Test", system_prompt="Test", output_type=Result,
        )
    client.responses.create.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_output_still_counts_billed_tokens(tmp_path, monkeypatch):
    mock_client(monkeypatch, arguments='{"value": "not-an-integer"}')
    gateway = ModelGateway(settings(), spend_ledger_path=tmp_path / "spend.sqlite")
    with pytest.raises(ModelInvocationError):
        await gateway.generate_structured(
            role="report", prompt="Test", system_prompt="Test", output_type=Result,
        )
    assert gateway.usage_summary()["output_tokens"] == 20
    assert gateway.usage_summary()["estimated_cost_usd"] > 0


@pytest.mark.asyncio
async def test_missing_usage_retains_reservation(tmp_path, monkeypatch):
    mock_client(monkeypatch, usage=False)
    gateway = ModelGateway(settings(), spend_ledger_path=tmp_path / "spend.sqlite")
    await gateway.generate_structured(
        role="report", prompt="Test", system_prompt="Test", output_type=Result,
    )
    assert gateway.usage_summary()["reserved_usd"] > 0


def test_strict_decoding_preserves_open_dictionary_contracts():
    from deep_research.contracts.clarification import ClarificationDecision
    from deep_research.contracts.reporting import ReportDraft
    from deep_research.models.gateway import _output_schema

    schema, strict = _output_schema(ReportDraft)
    assert strict
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    schema, strict = _output_schema(ClarificationDecision)
    assert not strict
    assert schema == ClarificationDecision.model_json_schema()
