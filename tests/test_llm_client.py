import sys
from pathlib import Path
from types import SimpleNamespace

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts import validate_setup
from src.llm import client as llm_client


class _FakeKeyring:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_password(self, service, username):
        return self.mapping.get((service, username), "")


class _FakeOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_llm_client_uses_legacy_hybridrag_keyring_entries(monkeypatch):
    mapping = {
        ("hybridrag", "azure_api_key"): "sk-test-legacy-key",
        ("hybridrag", "azure_endpoint"): "https://api.openai.com/v1",
    }
    fake_keyring = _FakeKeyring(mapping)
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    monkeypatch.setattr(llm_client, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(llm_client, "AzureOpenAI", _FakeOpenAI)
    for var in [
        "HYBRIDRAG_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "HYBRIDRAG_API_ENDPOINT",
        "AZURE_OPENAI_ENDPOINT",
        "OPENAI_API_ENDPOINT",
        "OPENAI_BASE_URL",
        "HYBRIDRAG_API_PROVIDER",
    ]:
        monkeypatch.delenv(var, raising=False)

    client = llm_client.LLMClient()

    assert client.available is True
    assert client.provider == "openai"
    assert isinstance(client._client, _FakeOpenAI)
    assert client._client.kwargs["api_key"] == "sk-test-legacy-key"
    assert client._client.kwargs["base_url"] == "https://api.openai.com/v1"


def test_validate_setup_reports_legacy_hybridrag_keyring_key(monkeypatch):
    mapping = {
        ("hybridrag", "azure_api_key"): "sk-test-legacy-key",
    }
    fake_keyring = _FakeKeyring(mapping)
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    for var in [
        "HYBRIDRAG_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "HYBRIDRAG_API_ENDPOINT",
        "AZURE_OPENAI_ENDPOINT",
    ]:
        monkeypatch.delenv(var, raising=False)

    validate_setup.results.clear()
    validate_setup.check_api_credentials()

    api_key_records = [r for r in validate_setup.results if r["label"] == "API key"]
    assert len(api_key_records) == 1
    assert api_key_records[0]["level"] == validate_setup.PASS
    assert "keyring(hybridrag)" in api_key_records[0]["detail"]
