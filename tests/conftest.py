import copy
import json
from types import SimpleNamespace

import pytest

from rfpcopilot.kb import build_kb
from rfpcopilot.pipeline import Pipeline

_KB = build_kb()


@pytest.fixture
def kb():
    return copy.deepcopy(_KB[0])


@pytest.fixture
def truth():
    return _KB[1]


@pytest.fixture
def pipeline(kb):
    return Pipeline(kb)


class FakeClaude:
    """Stands in for anthropic.Anthropic(): returns a canned JSON body and records each request."""

    def __init__(self, payload):
        self.payload, self.calls = payload, []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        body = self.payload(kwargs) if callable(self.payload) else self.payload
        text = body if isinstance(body, str) else json.dumps(body)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=900, output_tokens=120))


@pytest.fixture
def fake_claude():
    return FakeClaude
