from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

TerminalStatus = Literal["approved", "declined", "cancelled", "unknown"]


class TerminalUnreachable(Exception):
    """The sale/status/refund command never left the host (or never reached the terminal).

    Distinguishes *unreachable* from *timeout_no_response*:
    - ``TerminalUnreachable`` — command was not delivered; a retry of ``sale`` is safe
      from a double-charge perspective (no request was sent with this reference).
    - ``TerminalResult(status="unknown")`` after timeout — command was sent, but no
      reply arrived; ``sale`` must NOT be retried automatically; use ``status(reference)``.
    """


@dataclass(slots=True)
class TerminalResult:
    status: TerminalStatus
    provider_txn_id: str | None = None
    auth_code: str | None = None
    card_last4: str | None = None
    card_scheme: str | None = None
    error_code: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SettlementReport:
    closed_at: datetime
    totals: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentTerminal(Protocol):
    async def sale(self, amount: int, currency: str, reference: str) -> TerminalResult: ...

    async def status(self, reference: str) -> TerminalResult: ...

    async def refund(
        self, provider_txn_id: str, amount: int, reference: str
    ) -> TerminalResult: ...

    async def abort(self) -> None: ...

    async def end_of_day(self) -> SettlementReport: ...
