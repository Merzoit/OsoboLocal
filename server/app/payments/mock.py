from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from app.payments.terminal import SettlementReport, TerminalResult, TerminalUnreachable

MockScenario = Literal[
    "approved",
    "declined",
    "cancelled",
    "timeout_no_response",
    "unreachable",
]


class MockTerminal:
    """Configurable test double for ``PaymentTerminal``.

    Scenarios:
    - ``approved`` / ``declined`` / ``cancelled`` — definite outcomes.
    - ``timeout_no_response`` — command is considered sent; returns
      ``TerminalResult(status="unknown")``. Retrying ``sale`` is unsafe.
    - ``unreachable`` — raises ``TerminalUnreachable``; command never left;
      retrying ``sale`` is safe.
    """

    def __init__(self, scenario: MockScenario = "approved") -> None:
        self.scenario = scenario
        self.sent_references: list[str] = []
        self._results: dict[str, TerminalResult] = {}

    async def sale(self, amount: int, currency: str, reference: str) -> TerminalResult:
        if self.scenario == "unreachable":
            raise TerminalUnreachable("terminal unreachable; command not sent")

        # Command is considered delivered past this point.
        self.sent_references.append(reference)

        if self.scenario == "timeout_no_response":
            result = TerminalResult(
                status="unknown",
                error_code="timeout_no_response",
                raw_response={"amount": amount, "currency": currency, "reference": reference},
            )
            self._results[reference] = result
            return result

        if self.scenario == "approved":
            result = TerminalResult(
                status="approved",
                provider_txn_id=f"txn-{reference}",
                auth_code="AUTH01",
                card_last4="4242",
                card_scheme="visa",
                raw_response={"amount": amount, "currency": currency},
            )
        elif self.scenario == "declined":
            result = TerminalResult(
                status="declined",
                error_code="declined",
                raw_response={"amount": amount, "currency": currency},
            )
        else:  # cancelled
            result = TerminalResult(
                status="cancelled",
                error_code="cancelled",
                raw_response={"amount": amount, "currency": currency},
            )

        self._results[reference] = result
        return result

    async def status(self, reference: str) -> TerminalResult:
        if self.scenario == "unreachable":
            raise TerminalUnreachable("terminal unreachable; status not sent")
        if reference in self._results:
            return self._results[reference]
        return TerminalResult(status="unknown", error_code="not_found")

    async def refund(
        self, provider_txn_id: str, amount: int, reference: str
    ) -> TerminalResult:
        if self.scenario == "unreachable":
            raise TerminalUnreachable("terminal unreachable; refund not sent")
        return TerminalResult(
            status="approved",
            provider_txn_id=provider_txn_id,
            raw_response={"amount": amount, "reference": reference},
        )

    async def abort(self) -> None:
        return None

    async def end_of_day(self) -> SettlementReport:
        return SettlementReport(closed_at=datetime.now(UTC), totals={"approved": 0})
