import asyncio
import copy
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from deep_research.models.config import ModelProvider, ModelSettings, ModelTarget
from deep_research.models.spend import SpendLedger, SpendLimitError

OutputT = TypeVar("OutputT", bound=BaseModel)
logger = logging.getLogger(__name__)

_MAX_ERROR_DETAIL_CHARS = 500
_OUTPUT_LIMIT_ERROR_TYPES = {
    "LengthFinishReasonError",
    "MaxTokensReachedException",
}
# Provider responses that will not change on retry: malformed requests, missing or revoked
# credentials, exhausted billing, unknown models. Rate limits and 5xx are deliberately absent.
_PROVIDER_REJECTION_ERROR_TYPES = {
    "AuthenticationError",
    "BadRequestError",
    "NotFoundError",
    "PermissionDeniedError",
    "UnprocessableEntityError",
}
_PROVIDER_REJECTION_MARKERS = (
    "credit balance",
    "invalid_request_error",
    "authentication_error",
    "permission_error",
    "not_found_error",
    "invalid api key",
    "invalid x-api-key",
    "accessdeniedexception",
    "unrecognizedclientexception",
    "expiredtokenexception",
    "invalidsignatureexception",
    "insufficient_quota",
    "validationexception",
    "resourcenotfoundexception",
)


class StructuredModelGateway(Protocol):
    async def generate_structured(
        self,
        *,
        role: str,
        prompt: str,
        output_type: type[OutputT],
        system_prompt: str,
    ) -> OutputT: ...


@dataclass(frozen=True)
class ModelAttemptFailure:
    target_name: str
    provider: ModelProvider
    model_id: str
    attempt: int
    max_attempts: int
    error_type: str
    message: str

    def summary(self) -> str:
        target = f"{self.target_name}[{self.provider.value}/{self.model_id}]"
        detail = f": {self.message}" if self.message else ""
        return (
            f"{target} attempt {self.attempt}/{self.max_attempts}: "
            f"{self.error_type}{detail}"
        )


class ModelInvocationError(RuntimeError):
    def __init__(self, role: str, failures: list[ModelAttemptFailure]) -> None:
        detail = "; ".join(failure.summary() for failure in failures)
        super().__init__(f"all model targets failed for role {role!r}: {detail}")
        self.role = role
        self.failures = tuple(failures)


class ModelGateway:
    """Role-aware Strands model factory with whole-operation fallback.

    A failed attempt is discarded in full. Outputs are never combined across providers.
    """

    def __init__(
        self,
        settings: ModelSettings,
        agent_factory: Callable[..., Any] | None = None,
        *,
        spend_limit_usd: float = 17.0,
        spend_ledger_path: Path = Path(".data/openai-spend.sqlite"),
    ) -> None:
        self._settings = settings
        self._agent_factory = agent_factory
        self._spend_limit_usd = spend_limit_usd
        self._spend_ledger_path = spend_ledger_path
        self._ledger: SpendLedger | None = None
        self._call_ids: list[str] = []
        self.capture_outputs = False
        self.captured_outputs: list[dict[str, Any]] = []

    def usage_summary(self) -> dict[str, int | float]:
        if self._ledger is None:
            return dict(calls=0, input_tokens=0, output_tokens=0,
                        estimated_cost_usd=0.0, reserved_usd=0.0)
        return self._ledger.summary(self._call_ids)

    async def generate_structured(
        self,
        *,
        role: str,
        prompt: str,
        output_type: type[OutputT],
        system_prompt: str,
    ) -> OutputT:
        failures: list[ModelAttemptFailure] = []
        for target_name, target in self._settings.route_for(role):
            logger.info(
                "model route selected role=%s provider=%s model=%s",
                role,
                target.provider.value,
                target.model_id,
            )
            for attempt_index in range(target.max_attempts):
                try:
                    result = await asyncio.wait_for(
                        self._invoke(target, prompt, output_type, system_prompt),
                        timeout=target.timeout_seconds,
                    )
                    if self.capture_outputs:
                        self.captured_outputs.append({
                            "role": role, "model": target.model_id,
                            "output": result.model_dump(mode="json"),
                        })
                    return result
                except (Exception, asyncio.CancelledError) as exc:
                    if isinstance(exc, (asyncio.CancelledError, SpendLimitError)):
                        raise
                    failure = ModelAttemptFailure(
                        target_name=target_name,
                        provider=target.provider,
                        model_id=target.model_id,
                        attempt=attempt_index + 1,
                        max_attempts=target.max_attempts,
                        error_type=type(exc).__name__,
                        message=_safe_error_detail(exc),
                    )
                    failures.append(failure)
                    logger.warning(
                        "model invocation failed role=%s target=%s provider=%s model=%s "
                        "attempt=%s/%s error=%s detail=%s",
                        role,
                        target_name,
                        target.provider.value,
                        target.model_id,
                        failure.attempt,
                        failure.max_attempts,
                        failure.error_type,
                        failure.message or "<no detail>",
                    )
                    logger.debug("model invocation traceback", exc_info=True)
                    if isinstance(exc, ValidationError):
                        errors = [
                            {"path": item["loc"], "error": item["msg"]}
                            for item in exc.errors(include_url=False)
                        ]
                        prompt += (
                            "\nThe prior structured result failed schema validation. Correct "
                            "these fields in your complete result: " + json.dumps(errors)[:2000]
                        )
                    if is_output_limit_failure(failure) or is_provider_rejection_failure(
                        failure
                    ):
                        # Retrying the same target cannot help; fall through to the next one.
                        break
        raise ModelInvocationError(role, failures)

    async def _invoke(
        self,
        target: ModelTarget,
        prompt: str,
        output_type: type[OutputT],
        system_prompt: str,
    ) -> OutputT:
        if target.provider is ModelProvider.OPENAI and self._agent_factory is None:
            return await self._invoke_openai(target, prompt, output_type, system_prompt)
        agent_factory = self._agent_factory
        if agent_factory is None:
            from strands import Agent

            agent_factory = Agent

        agent = agent_factory(
            model=self._create_model(target),
            system_prompt=system_prompt,
            tools=[],
        )
        result = await agent.invoke_async(prompt, structured_output_model=output_type)
        structured = result.structured_output
        if isinstance(structured, output_type):
            return structured
        return output_type.model_validate(structured)

    async def _invoke_openai(
        self, target: ModelTarget, prompt: str, output_type: type[OutputT], system_prompt: str
    ) -> OutputT:
        """One forced function call per attempt, with no implicit agent or SDK retries."""
        from openai import AsyncOpenAI

        schema, strict = _output_schema(output_type)
        if self._ledger is None:
            self._ledger = SpendLedger(self._spend_ledger_path, self._spend_limit_usd)
        # A UTF-8 byte ceiling deliberately overestimates text tokens; overhead covers the
        # fixed message/tool envelope. Uncertain failures retain the entire reservation.
        input_bound = len((system_prompt + prompt + json.dumps(schema)).encode()) + 4096
        reservation = self._ledger.reserve(target.model_id, input_bound, target.max_tokens)
        self._call_ids.append(reservation)
        client_args: dict[str, Any] = {"timeout": target.timeout_seconds, "max_retries": 0}
        if target.api_key is not None:
            client_args["api_key"] = target.api_key.get_secret_value()
        if target.base_url:
            client_args["base_url"] = target.base_url
        sampling: dict[str, Any] = (
            {"reasoning": {"effort": target.reasoning_effort}}
            if target.model_id.startswith("gpt-5") else {"temperature": target.temperature}
        )
        async with AsyncOpenAI(**client_args) as client:
            response = await client.responses.create(
                model=target.model_id,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                tools=[{"type": "function",
                    "name": "return_result", "description": "Return the requested typed result.",
                    "parameters": schema, "strict": strict,
                }],
                tool_choice={"type": "function", "name": "return_result"},
                parallel_tool_calls=False,
                max_output_tokens=target.max_tokens,
                store=False,
                **sampling,
            )
        if response.usage is not None:
            self._ledger.settle(
                reservation, response.usage.input_tokens, response.usage.output_tokens
            )
        if response.status == "incomplete":
            raise ValueError("maximum token limit reached before structured output completed")
        calls = [item for item in response.output if item.type == "function_call"]
        if len(calls) != 1 or calls[0].name != "return_result":
            raise ValueError("OpenAI did not return the requested structured function call")
        return output_type.model_validate_json(calls[0].arguments)

    @staticmethod
    def _create_model(target: ModelTarget) -> Any:
        if target.provider is ModelProvider.BEDROCK:
            from botocore.config import Config as BotocoreConfig
            from strands.models import BedrockModel

            return BedrockModel(
                model_id=target.model_id,
                region_name=target.region,
                temperature=target.temperature,
                max_tokens=target.max_tokens,
                boto_client_config=BotocoreConfig(
                    connect_timeout=min(10, target.timeout_seconds),
                    read_timeout=target.timeout_seconds,
                    retries={"max_attempts": target.max_attempts, "mode": "standard"},
                ),
            )
        if target.provider is ModelProvider.OPENAI:
            from strands.models.openai import OpenAIModel

            client_args = {"timeout": target.timeout_seconds, "max_retries": 0}
            if target.api_key is not None:
                client_args["api_key"] = target.api_key.get_secret_value()
            if target.base_url:
                client_args["base_url"] = target.base_url
            return OpenAIModel(
                client_args=client_args,
                model_id=target.model_id,
                params={
                    "max_tokens": target.max_tokens,
                    "temperature": target.temperature,
                },
            )
        if target.provider is ModelProvider.ANTHROPIC:
            from strands.models.anthropic import AnthropicModel

            client_args = {"timeout": target.timeout_seconds, "max_retries": 0}
            if target.api_key is not None:
                client_args["api_key"] = target.api_key.get_secret_value()
            return AnthropicModel(
                client_args=client_args,
                model_id=target.model_id,
                max_tokens=target.max_tokens,
                params={"temperature": target.temperature},
            )
        raise AssertionError(f"unsupported model provider: {target.provider}")


def _safe_error_detail(exc: BaseException) -> str:
    """Keep provider diagnostics readable and bounded without logging request payloads."""
    detail = " ".join(str(exc).split())
    if len(detail) <= _MAX_ERROR_DETAIL_CHARS:
        return detail
    return f"{detail[: _MAX_ERROR_DETAIL_CHARS - 3]}..."


def _output_schema(output_type: type[BaseModel]) -> tuple[dict, bool]:
    """Use constrained decoding when the contract has no open-ended dictionary fields.

    ResearchBrief.definitions intentionally remains a map; that contract uses non-strict
    function calling plus Pydantic validation. Closed report/review/research schemas are strict.
    """
    original = output_type.model_json_schema()
    schema = copy.deepcopy(original)
    compatible = True

    def visit(value):
        nonlocal compatible
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                if isinstance(value.get("additionalProperties"), dict):
                    compatible = False
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    return (schema, True) if compatible else (original, False)


def is_output_limit_failure(failure: ModelAttemptFailure) -> bool:
    detail = failure.message.casefold()
    return failure.error_type in _OUTPUT_LIMIT_ERROR_TYPES or (
        "maximum token" in detail or "max token" in detail
    )


def is_output_limit_error(error: ModelInvocationError) -> bool:
    return bool(error.failures) and any(
        is_output_limit_failure(failure) for failure in error.failures
    )


def is_provider_rejection_failure(failure: ModelAttemptFailure) -> bool:
    detail = failure.message.casefold()
    return failure.error_type in _PROVIDER_REJECTION_ERROR_TYPES or any(
        marker in detail for marker in _PROVIDER_REJECTION_MARKERS
    )


def is_provider_rejection_error(error: ModelInvocationError) -> bool:
    """True when no configured target can succeed by retrying the same request.

    Every attempt must have been a deterministic rejection (or an output-limit stop); a single
    transient failure among the attempts keeps the error retryable.
    """
    return bool(error.failures) and all(
        is_provider_rejection_failure(failure) or is_output_limit_failure(failure)
        for failure in error.failures
    )
