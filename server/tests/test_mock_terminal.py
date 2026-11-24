from __future__ import annotations

import asyncio

import pytest
from app.payments.mock import MockTerminal
from app.payments.terminal import TerminalUnreachable


def test_mock_approved() -> None:
    terminal = MockTerminal("approved")
    result = asyncio.run(terminal.sale(100, "EUR", "ref-a"))
    assert result.status == "approved"
    assert result.provider_txn_id is not None
    assert "ref-a" in terminal.sent_references


def test_mock_declined() -> None:
    result = asyncio.run(MockTerminal("declined").sale(100, "EUR", "ref-d"))
    assert result.status == "declined"


def test_mock_cancelled() -> None:
    result = asyncio.run(MockTerminal("cancelled").sale(100, "EUR", "ref-c"))
    assert result.status == "cancelled"


def test_mock_timeout_no_response() -> None:
    """Command left the host; result is unknown — do not retry sale."""
    terminal = MockTerminal("timeout_no_response")
    result = asyncio.run(terminal.sale(100, "EUR", "ref-t"))
    assert result.status == "unknown"
    assert result.error_code == "timeout_no_response"
    assert "ref-t" in terminal.sent_references


def test_mock_unreachable() -> None:
    """Command never left; TerminalUnreachable means retrying sale is safe."""
    terminal = MockTerminal("unreachable")
    with pytest.raises(TerminalUnreachable):
        asyncio.run(terminal.sale(100, "EUR", "ref-u"))
    assert terminal.sent_references == []
