"""Unit tests for domain entities."""

from __future__ import annotations

import pytest

from app.domain.exceptions import InvalidMessagePayloadError
from app.domain.models import IncomingMessage


def test_ensure_has_action_returns_normalized_value():
    message = IncomingMessage(message_id="1", receipt_handle="rh", payload={"action": "  FAIL "})
    assert message.ensure_has_action() == "fail"


@pytest.mark.parametrize("payload", [{}, {"action": ""}, {"action": "   "}])
def test_ensure_has_action_raises_when_missing_or_empty(payload):
    message = IncomingMessage(message_id="1", receipt_handle="rh", payload=payload)
    with pytest.raises(InvalidMessagePayloadError):
        message.ensure_has_action()
