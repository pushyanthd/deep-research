"""Local, process-safe OpenAI spend reservations; no prompts or credentials are stored."""

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

# Standard, uncached USD / million tokens. Cached tokens are conservatively billed as input.
# https://developers.openai.com/api/docs/models/gpt-4.1 (and the corresponding mini pages)
PRICES = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5.4-mini": (0.75, 4.50),
}


class SpendLimitError(RuntimeError):
    """No paid request may start when its upper-bound reservation exceeds the budget."""


def price_for(model: str) -> tuple[float, float]:
    for name, prices in PRICES.items():
        if model == name or model.startswith(name + "-20"):
            return prices
    raise SpendLimitError(f"No verified token price configured for model {model!r}.")


class SpendLedger:
    def __init__(self, path: Path, limit_usd: float) -> None:
        if limit_usd <= 0:
            raise ValueError("spend limit must be positive")
        self.path = path
        self.limit_usd = limit_usd
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, model TEXT, "
                "reserved REAL, cost REAL, input_tokens INTEGER, output_tokens INTEGER)"
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, model: str, input_bound: int, output_bound: int) -> str:
        input_price, output_price = price_for(model)
        amount = (input_bound * input_price + output_bound * output_price) / 1_000_000
        call_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute("SELECT COALESCE(SUM(COALESCE(cost, reserved)), 0) FROM calls")
            if used.fetchone()[0] + amount > self.limit_usd:
                raise SpendLimitError("OpenAI spend limit reached; request was not sent.")
            db.execute(
                "INSERT INTO calls VALUES (?, ?, ?, NULL, 0, 0)",
                (call_id, model, amount),
            )
        return call_id

    def settle(self, call_id: str, input_tokens: int, output_tokens: int) -> None:
        with self._connect() as db:
            model = db.execute("SELECT model FROM calls WHERE id = ?", (call_id,)).fetchone()[0]
            ip, op = price_for(model)
            cost = (input_tokens * ip + output_tokens * op) / 1_000_000
            db.execute(
                "UPDATE calls SET cost = ?, input_tokens = ?, output_tokens = ? WHERE id = ?",
                (cost, input_tokens, output_tokens, call_id),
            )

    def summary(self, call_ids: list[str] | None = None) -> dict[str, int | float]:
        where = ""
        params = []
        if call_ids is not None:
            where = " WHERE id IN (" + ",".join("?" for _ in call_ids) + ")"
            params = call_ids
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(input_tokens), 0), "
                "COALESCE(SUM(output_tokens), 0), COALESCE(SUM(cost), 0), "
                "COALESCE(SUM(CASE WHEN cost IS NULL THEN reserved ELSE 0 END), 0) FROM calls"
                + where, params,
            ).fetchone()
        return dict(zip(
            ("calls", "input_tokens", "output_tokens", "estimated_cost_usd", "reserved_usd"),
            row, strict=True,
        ))
